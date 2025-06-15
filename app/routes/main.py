from flask import Blueprint, render_template
from flask_login import login_required, current_user

from ..models import TrainingJob

# Create Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Landing page."""
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing recent jobs and stats."""
    # Get user's recent training jobs
    recent_jobs = TrainingJob.query.filter_by(user_id=current_user.id)\
                                  .order_by(TrainingJob.start_time.desc())\
                                  .limit(5).all()
    
    # Count jobs by status
    queued_count = TrainingJob.query.filter_by(user_id=current_user.id, status='QUEUED').count()
    running_count = TrainingJob.query.filter_by(user_id=current_user.id, status='RUNNING').count()
    completed_count = TrainingJob.query.filter_by(user_id=current_user.id, status='COMPLETED').count()
    failed_count = TrainingJob.query.filter_by(user_id=current_user.id, status='FAILED').count()
    
    return render_template(
        'dashboard.html',
        recent_jobs=recent_jobs,
        queued_count=queued_count,
        running_count=running_count,
        completed_count=completed_count,
        failed_count=failed_count
    )
