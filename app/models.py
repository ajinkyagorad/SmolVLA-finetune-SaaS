import uuid
import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from cryptography.fernet import Fernet

# Initialize SQLAlchemy
db = SQLAlchemy()

class EncryptionUtils:
    """Utility class for encrypting and decrypting sensitive data."""
    
    @staticmethod
    def initialize(key):
        """Initialize the Fernet cipher with the provided key."""
        if not key:
            raise ValueError("Encryption key is required")
        return Fernet(key)
    
    @staticmethod
    def encrypt(cipher, data):
        """Encrypt data using the Fernet cipher."""
        if not data:
            return None
        return cipher.encrypt(data.encode())
    
    @staticmethod
    def decrypt(cipher, encrypted_data):
        """Decrypt data using the Fernet cipher."""
        if not encrypted_data:
            return None
        return cipher.decrypt(encrypted_data).decode()


class User(db.Model, UserMixin):
    """User model for authentication and storing encrypted tokens."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    encrypted_hf_token = db.Column(db.LargeBinary)
    encrypted_wandb_api_key = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationship with TrainingJob
    training_jobs = db.relationship('TrainingJob', backref='user', lazy='dynamic')
    
    @property
    def password(self):
        """Prevent password from being accessed."""
        raise AttributeError('Password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        """Check if password matches."""
        return check_password_hash(self.password_hash, password)
    
    def set_hf_token(self, cipher, token):
        """Encrypt and store Hugging Face token."""
        self.encrypted_hf_token = EncryptionUtils.encrypt(cipher, token)
    
    def get_hf_token(self, cipher):
        """Decrypt and return Hugging Face token."""
        return EncryptionUtils.decrypt(cipher, self.encrypted_hf_token)
    
    def set_wandb_api_key(self, cipher, api_key):
        """Encrypt and store Weights & Biases API key."""
        self.encrypted_wandb_api_key = EncryptionUtils.encrypt(cipher, api_key)
    
    def get_wandb_api_key(self, cipher):
        """Decrypt and return Weights & Biases API key."""
        return EncryptionUtils.decrypt(cipher, self.encrypted_wandb_api_key)
    
    def __repr__(self):
        return f'<User {self.username}>'


class TrainingJob(db.Model):
    """Model for tracking SmolVLA training jobs."""
    
    __tablename__ = 'training_jobs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dataset_repo_id = db.Column(db.String(128), nullable=False)
    output_repo_id = db.Column(db.String(128), nullable=False)
    steps = db.Column(db.Integer, default=1000)
    status = db.Column(db.String(20), default='QUEUED')  # QUEUED, RUNNING, COMPLETED, FAILED
    start_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    end_time = db.Column(db.DateTime)
    log_output = db.Column(db.Text)
    model_url = db.Column(db.String(256))
    
    def __repr__(self):
        return f'<TrainingJob {self.id} - {self.status}>'
    
    def to_dict(self):
        """Convert job to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'dataset_repo_id': self.dataset_repo_id,
            'output_repo_id': self.output_repo_id,
            'steps': self.steps,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'model_url': self.model_url
        }
