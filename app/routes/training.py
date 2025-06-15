from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user

from ..models import db, TrainingJob
from ..tasks import train_smolvla

# Create Blueprint
training = Blueprint('training', __name__)

@training.route('/train', methods=['GET', 'POST'])
@login_required
def train():
    """Handle training form submission."""
    # Check if user has HF token
    if not current_user.encrypted_hf_token:
        flash('You need to add your Hugging Face token in your profile before training.', 'warning')
        return redirect(url_for('auth.profile'))
    
    if request.method == 'POST':
        # Get form data
        dataset_repo_id = request.form.get('dataset_repo_id')
        output_repo_id = request.form.get('output_repo_id')
        steps = request.form.get('steps', 1000)
        
        # Validate inputs
        if not dataset_repo_id:
            flash('Dataset repository ID is required.', 'danger')
            return render_template('train_form.html')
        
        if not output_repo_id:
            flash('Output repository ID is required.', 'danger')
            return render_template('train_form.html')
        
        try:
            steps = int(steps)
            if steps < 100 or steps > 10000:
                flash('Steps must be between 100 and 10000.', 'danger')
                return render_template('train_form.html')
        except ValueError:
            flash('Steps must be a number.', 'danger')
            return render_template('train_form.html')
        
        # Create new training job
        job = TrainingJob(
            user_id=current_user.id,
            dataset_repo_id=dataset_repo_id,
            output_repo_id=output_repo_id,
            steps=steps,
            status='QUEUED'
        )
        
        db.session.add(job)
        db.session.commit()
        
        # Get decrypted tokens
        cipher = current_app.cipher
        hf_token = current_user.get_hf_token(cipher)
        wandb_api_key = current_user.get_wandb_api_key(cipher)
        
        # Submit Celery task
        train_smolvla.delay(job.id, hf_token, wandb_api_key)
        
        flash(f'Training job submitted! Job ID: {job.id}', 'success')
        return redirect(url_for('training.jobs'))
    
    return render_template('train_form.html')


@training.route('/jobs')
@login_required
def jobs():
    """Display user's training jobs."""
    jobs = TrainingJob.query.filter_by(user_id=current_user.id)\
                          .order_by(TrainingJob.start_time.desc()).all()
    
    return render_template('jobs_list.html', jobs=jobs)


@training.route('/jobs/<job_id>')
@login_required
def job_detail(job_id):
    """Display details for a specific job."""
    job = TrainingJob.query.get_or_404(job_id)
    
    # Check if job belongs to current user
    if job.user_id != current_user.id:
        flash('You do not have permission to view this job.', 'danger')
        return redirect(url_for('training.jobs'))
    
    return render_template('job_detail.html', job=job)


@training.route('/api/jobs/<job_id>')
@login_required
def job_status(job_id):
    """API endpoint to get job status for AJAX updates."""
    job = TrainingJob.query.get_or_404(job_id)
    
    # Check if job belongs to current user
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify(job.to_dict())
