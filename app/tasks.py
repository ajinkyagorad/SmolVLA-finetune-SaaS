import os
import subprocess
import logging
import shutil
import yaml
import re
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

def sanitize_string(s):
    """
    Sanitize a string by removing NUL characters and other problematic characters
    that might cause database issues.
    
    Args:
        s (str): The string to sanitize
        
    Returns:
        str: The sanitized string
    """
    if not isinstance(s, str):
        return s
    
    # Remove NUL (0x00) characters
    s = s.replace('\x00', '')
    
    # Replace other potentially problematic control characters
    s = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F]', '', s)
    
    return s

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
        
        # Set up output directory for training results with timestamp to ensure uniqueness
        import time
        timestamp = int(time.time())
        output_dir = Path(os.environ.get('UPLOAD_FOLDER', '/app/training_outputs')) / f"{job_id}_{timestamp}"
        #output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['HF_TOKEN'] = hf_token
        if wandb_api_key:
            env['WANDB_API_KEY'] = wandb_api_key
        
        # Create CLI arguments for SmolVLA's dot-notation format based on Google Colab example
        # Instead of using a config file, we'll pass these directly to the command
        # Note: Removed policy.name as it's not a valid field for SmolVLAConfig
        cli_args = [
            f"--policy.path=lerobot/smolvla_base",  # Use type instead of path
            f"--dataset.repo_id={job.dataset_repo_id}",
            f"--batch_size=16",
            f"--steps={job.steps}",
            f"--output_dir={str(output_dir)}",
            f"--job_name={job.id}",  # Use job.id instead of job.name
            f"--policy.device=cuda",
            f"--wandb.enable={'true' if wandb_api_key is not None else 'false'}"
        ]
        
        # Add optional parameters
        cli_args.extend([
            "--log_freq=10",
            "--save_checkpoint=true",
            "--save_freq=500",
            f"--optimizer.lr=2e-5",
            "--scheduler.type=cosine_decay_with_warmup",
            f"--scheduler.num_warmup_steps={int(job.steps * 0.03)}",
            f"--scheduler.num_decay_steps={job.steps - int(job.steps * 0.03)}",
            "--scheduler.peak_lr=2e-5",
            "--scheduler.decay_lr=0"
        ])
        
        # Construct the training command with direct CLI arguments
        command = [
            "python", "-m", "lerobot.scripts.train"
        ] + cli_args
        
        # Log the command (for debugging)
        logger.info(f"Training command for job {job_id}: {' '.join(command)}")
        
        # Create a temporary directory for storing logs and command file
        # This avoids creating the output_dir which the training script expects to create itself
        temp_dir = Path(os.environ.get('UPLOAD_FOLDER', '/app/training_outputs')) / f"temp_{job_id}_{timestamp}"
        if not temp_dir.exists():
            temp_dir.mkdir(parents=True)
        
        # Write command to a file for reference in the temp directory
        command_path = temp_dir / "train_command.txt"
        with open(command_path, 'w') as f:
            f.write(' '.join(command))
        
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
        
        # Store logs - keep full stderr for debugging but limit stdout if needed
        max_stdout_size = 50000  # Increased maximum characters to store for stdout
        # Always store the full stderr for error diagnosis
        # Sanitize stdout and stderr to remove NUL characters before saving to database
        sanitized_stdout = sanitize_string(stdout[:max_stdout_size])
        sanitized_stderr = sanitize_string(stderr)
        
        log_output = f"STDOUT:\n{sanitized_stdout}"
        if len(stdout) > max_stdout_size:
            log_output += "\n...(stdout truncated)..."
        
        # Always include the full stderr for debugging
        log_output += f"\n\nSTDERR:\n{sanitized_stderr}"
        
        # Save the full log output
        job.log_output = log_output
        
        # Also write complete logs to a file for reference (in temp directory)
        log_file = temp_dir / "training_log.txt"
        with open(log_file, 'w') as f:
            f.write(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}")
        
        # Check if training was successful
        if process.returncode != 0:
            job.status = 'FAILED'
            job.end_time = datetime.utcnow()
            db.session.commit()
            # Log the full error for debugging
            logger.error(f"Training failed for job {job_id}")
            # Return a more concise error message but ensure we have the full logs saved
            error_summary = stderr[-1000:] if len(stderr) > 1000 else stderr
            # Sanitize the error summary before returning
            sanitized_error = sanitize_string(error_summary)
            return {'status': 'failed', 'error': sanitized_error, 'log_file': str(log_file), 'temp_dir': str(temp_dir)}
        
        # Find the best checkpoint directory - now the output_dir should exist since the training script created it
        if not output_dir.exists():
            job.status = 'FAILED'
            job.end_time = datetime.utcnow()
            job.log_output = sanitize_string(job.log_output + f"\nOutput directory {output_dir} was not created by training script.")
            db.session.commit()
            logger.error(f"Output directory not created for job {job_id}")
            return {'status': 'failed', 'error': 'Output directory not created', 'temp_dir': str(temp_dir)}
            
        # Look for checkpoints in the output directory
        checkpoints = list(output_dir.glob("checkpoint-*"))
        if not checkpoints:
            job.status = 'FAILED'
            job.end_time = datetime.utcnow()
            job.log_output = sanitize_string(job.log_output + "\nNo checkpoints found in output directory.")
            db.session.commit()
            logger.error(f"No checkpoints found for job {job_id}")
            return {'status': 'failed', 'error': 'No checkpoints found', 'temp_dir': str(temp_dir)}
        
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
            error_msg = sanitize_string(str(e))
            logger.error(f"Error uploading model to Hugging Face Hub: {error_msg}")
            job.log_output = sanitize_string(job.log_output + f"\nError uploading model: {error_msg}")
            job.status = 'COMPLETED_WITH_ERRORS'
            job.end_time = datetime.utcnow()
            db.session.commit()
            return {'status': 'completed_with_errors', 'error': error_msg}
        
        # Update job status to COMPLETED
        job.status = 'COMPLETED'
        job.end_time = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Training completed successfully for job {job_id}")
        return {
            'status': 'completed',
            'model_url': job.model_url,
            'temp_dir': str(temp_dir)
        }
        
    except Exception as e:
        logger.exception(f"Unexpected error in train_smolvla task for job {job_id}: {e}")
        
        # Get the temp_dir if it was created
        temp_dir_str = None
        try:
            if 'temp_dir' in locals() and temp_dir.exists():
                temp_dir_str = str(temp_dir)
        except Exception:
            pass
            
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
        
        return {'status': 'failed', 'error': str(e), 'temp_dir': temp_dir_str}
