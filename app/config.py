import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    """Base configuration class for the SmolVLA Training SaaS application."""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-replace-in-production')
    
    # Database configuration
    DATABASE_USER = os.environ.get('DATABASE_USER', 'postgres')
    DATABASE_PASSWORD = os.environ.get('DATABASE_PASSWORD', 'postgres')
    DATABASE_HOST = os.environ.get('DATABASE_HOST', 'postgres-service')
    DATABASE_NAME = os.environ.get('DATABASE_NAME', 'smolvladb')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_URI',
        f'postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}/{DATABASE_NAME}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Celery configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis-service/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis-service/0')
    
    # Training output directory
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/training_outputs')
    
    # Encryption key for sensitive data
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    
    # Default training parameters
    DEFAULT_TRAINING_STEPS = 1000
    
    # Maximum concurrent training jobs (should match worker replicas)
    MAX_CONCURRENT_JOBS = 4


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Get configuration based on environment
def get_config():
    """Return the appropriate configuration object based on the environment."""
    config_name = os.environ.get('FLASK_CONFIG', 'default')
    return config_dict.get(config_name, config_dict['default'])
