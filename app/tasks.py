import os
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path

from celery import shared_task
from huggingface_hub import HfApi, upload_folder

from .models import db, TrainingJob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='train_smolvla')
def train_smolvla(self, job_id, hf_token, wandb_api_key=None):
    """
    Celery task to train a SmolVLA model.
    
    Args:
        job_id (str): The ID of the training job in the database
        hf_token (str): Decrypted Hugging Face token
        wandb_api_key (str, optional): Decrypted Weights & Biases API key
    
    Returns:
        dict: Status and result information
    """
    try:
        # Get the job from the database
        job = TrainingJob.query.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in database")
            return {'status': 'failed', 'error': 'Job not found'}
        
        # Update job status to RUNNING
        job.status = 'RUNNING'
        db.session.commit()
        
        # Create output directory
        output_dir = Path(os.environ.get('UPLOAD_FOLDER', '/app/training_outputs')) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['HF_TOKEN'] = hf_token
        if wandb_api_key:
            env['WANDB_API_KEY'] = wandb_api_key
        
        # Construct the training command
        # This is based on lerobot's training script for SmolVLA
        command = [
            "python", "-m", "lerobot.scripts.train",
            "--model", "smolvla_base",
            "--dataset", job.dataset_repo_id,
            "--output_dir", str(output_dir),
            "--num_train_epochs", "3",
            "--max_steps", str(job.steps),
            "--per_device_train_batch_size", "8",
            "--gradient_accumulation_steps", "4",
            "--learning_rate", "2e-5",
            "--warmup_ratio", "0.03",
            "--lr_scheduler_type", "cosine",
            "--logging_steps", "10",
            "--save_strategy", "steps",
            "--save_steps", "500",
            "--save_total_limit", "3",
            "--report_to", "wandb" if wandb_api_key else "none"
        ]
        
        # Log the command (but mask sensitive tokens)
        logger.info(f"Running training command for job {job_id}")
        
        # Execute the training process
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Capture output
        stdout, stderr = process.communicate()
        
        # Store logs (truncate if too large)
        max_log_size = 10000  # Maximum characters to store
        log_output = f"STDOUT:\n{stdout[:max_log_size]}\n\nSTDERR:\n{stderr[:max_log_size]}"
        if len(stdout) > max_log_size or len(stderr) > max_log_size:
            log_output += "\n...(truncated)..."
        
        job.log_output = log_output
        
        # Check if training was successful
        if process.returncode != 0:
            job.status = 'FAILED'
            job.end_time = datetime.utcnow()
            db.session.commit()
            logger.error(f"Training failed for job {job_id}: {stderr}")
            return {'status': 'failed', 'error': stderr}
        
        # Find the best checkpoint directory
        checkpoints = list(output_dir.glob("checkpoint-*"))
        if not checkpoints:
            job.status = 'FAILED'
            job.end_time = datetime.utcnow()
            job.log_output += "\nNo checkpoints found after training."
            db.session.commit()
            logger.error(f"No checkpoints found for job {job_id}")
            return {'status': 'failed', 'error': 'No checkpoints found'}
        
        # Sort checkpoints by step number and get the latest
        latest_checkpoint = sorted(checkpoints, key=lambda x: int(x.name.split('-')[1]))[-1]
        
        # Upload the model to Hugging Face Hub
        logger.info(f"Uploading model to Hugging Face Hub: {job.output_repo_id}")
        try:
            api = HfApi(token=hf_token)
            
            # Create the repository if it doesn't exist
            try:
                api.create_repo(
                    repo_id=job.output_repo_id,
                    repo_type="model",
                    private=True,
                    exist_ok=True
                )
            except Exception as e:
                logger.warning(f"Error creating repo {job.output_repo_id}: {e}")
            
            # Upload the model files
            upload_folder(
                folder_path=str(latest_checkpoint),
                repo_id=job.output_repo_id,
                repo_type="model",
                token=hf_token
            )
            
            # Set the model URL
            job.model_url = f"https://huggingface.co/{job.output_repo_id}"
            
        except Exception as e:
            logger.error(f"Error uploading model to Hugging Face Hub: {e}")
            job.log_output += f"\nError uploading model: {str(e)}"
            job.status = 'COMPLETED_WITH_ERRORS'
            job.end_time = datetime.utcnow()
            db.session.commit()
            return {'status': 'completed_with_errors', 'error': str(e)}
        
        # Update job status to COMPLETED
        job.status = 'COMPLETED'
        job.end_time = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Training completed successfully for job {job_id}")
        return {
            'status': 'completed',
            'model_url': job.model_url
        }
        
    except Exception as e:
        logger.exception(f"Unexpected error in train_smolvla task for job {job_id}: {e}")
        
        # Update job status to FAILED
        try:
            job = TrainingJob.query.get(job_id)
            if job:
                job.status = 'FAILED'
                job.end_time = datetime.utcnow()
                job.log_output = f"Unexpected error: {str(e)}"
                db.session.commit()
        except Exception as db_error:
            logger.error(f"Error updating job status: {db_error}")
        
        return {'status': 'failed', 'error': str(e)}
