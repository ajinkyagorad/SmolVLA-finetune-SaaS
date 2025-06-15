import os
from flask import Flask
from flask_login import LoginManager
from celery import Celery

from .config import get_config
from .models import db, User, EncryptionUtils

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# Initialize Celery
celery = Celery(__name__)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))

def create_app(config_name=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Initialize encryption
    if not app.config.get('ENCRYPTION_KEY'):
        app.logger.warning("ENCRYPTION_KEY not set. Sensitive data will not be properly secured.")
    else:
        app.cipher = EncryptionUtils.initialize(app.config['ENCRYPTION_KEY'])
    
    # Register blueprints
    from .routes.auth import auth as auth_blueprint
    from .routes.main import main as main_blueprint
    from .routes.training import training as training_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(training_blueprint)
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app

def create_celery(app=None):
    """Configure Celery instance."""
    app = app or create_app()
    
    # Configure Celery
    celery.conf.broker_url = app.config['CELERY_BROKER_URL']
    celery.conf.result_backend = app.config['CELERY_RESULT_BACKEND']
    
    # Subclass task to include app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    return celery

# Create the Flask application instance
app = create_app()

# Configure Celery
celery_app = create_celery(app)
