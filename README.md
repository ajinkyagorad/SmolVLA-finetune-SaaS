# SmolVLA Training SaaS

A secure, scalable SaaS platform for fine-tuning SmolVLA models using GPU-accelerated training on Kubernetes.

## Overview

SmolVLA Training SaaS is a web application that allows users to fine-tune [lerobot/smolvla](https://huggingface.co/lerobot/smolvla) models on their own Hugging Face datasets. The platform provides:

- User authentication with secure token storage
- Asynchronous GPU-accelerated training jobs
- Job status tracking and monitoring
- Automatic model upload to Hugging Face Hub
- Kubernetes deployment with GPU support

## Architecture

The application consists of the following components:

- **Web Application**: Flask-based web interface for user interaction
- **Database**: PostgreSQL for storing user data and job information
- **Task Queue**: Celery with Redis for managing asynchronous training jobs
- **Workers**: GPU-enabled Celery workers for running training tasks
- **Storage**: Persistent Volume Claims for training outputs and database
- **Deployment**: Kubernetes manifests for orchestrating all components

## Prerequisites

- Docker
- Kubernetes cluster with GPU nodes (NVIDIA A100 recommended)
- kubectl configured to access your cluster
- Persistent storage provider supporting ReadWriteMany access mode
- Domain name for ingress (optional)

## Local Development

### Setup Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/smolvla-training-saas.git
   cd smolvla-training-saas
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   export FLASK_APP=app
   export FLASK_ENV=development
   export FLASK_SECRET_KEY=your-secret-key
   export DATABASE_USER=postgres
   export DATABASE_PASSWORD=postgres
   export DATABASE_HOST=localhost
   export DATABASE_NAME=smolvladb
   export SQLALCHEMY_DATABASE_URI=postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}/${DATABASE_NAME}
   export CELERY_BROKER_URL=redis://localhost:6379/0
   export CELERY_RESULT_BACKEND=redis://localhost:6379/0
   export ENCRYPTION_KEY=your-fernet-encryption-key
   export UPLOAD_FOLDER=/path/to/training/outputs
   ```

   Generate a Fernet encryption key:
   ```python
   from cryptography.fernet import Fernet
   key = Fernet.generate_key()
   print(key.decode())
   ```

5. Set up PostgreSQL and Redis locally (or use Docker):
   ```bash
   # Using Docker
   docker run -d --name postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=smolvladb -p 5432:5432 postgres:13-alpine
   docker run -d --name redis -p 6379:6379 redis:6-alpine
   ```

6. Initialize the database:
   ```bash
   flask shell
   ```
   ```python
   from app import db
   db.create_all()
   exit()
   ```

### Run Locally

1. Run the Flask application:
   ```bash
   flask run
   ```

2. Run Celery worker (in a separate terminal):
   ```bash
   celery -A app.celery worker --loglevel=info
   ```

## Building the Docker Image

1. Build the Docker image:
   ```bash
   docker build -t your-registry/smolvla-training-saas:latest .
   ```

2. Push to your registry:
   ```bash
   docker push your-registry/smolvla-training-saas:latest
   ```

## Kubernetes Deployment

1. Update the image name in the Kubernetes manifests:
   ```bash
   sed -i 's|your-registry/smolvla-training-saas:latest|your-actual-registry/smolvla-training-saas:latest|g' kubernetes/*.yaml
   ```

2. Create Kubernetes secrets:
   ```bash
   # Generate base64 encoded values
   echo -n "your-flask-secret-key" | base64
   echo -n "your-database-password" | base64
   echo -n "your-encryption-key" | base64
   
   # Update the values in kubernetes/01-secrets.yaml
   # Then apply:
   kubectl apply -f kubernetes/01-secrets.yaml
   ```

3. Deploy the application:
   ```bash
   kubectl apply -f kubernetes/
   ```

4. Verify the deployment:
   ```bash
   kubectl get pods
   kubectl get services
   kubectl get ingress
   ```

## Usage

1. Access the application at your configured domain or service endpoint.
2. Register a new user account.
3. Add your Hugging Face token in the profile page.
4. Submit a training job with your dataset repository ID.
5. Monitor the job status on the dashboard.
6. Access your trained model on Hugging Face Hub once training is complete.

## Training Requirements

- Dataset must be in a format compatible with SmolVLA training.
- User must have write access to the output repository on Hugging Face.
- Training steps should be between 100 and 10000.

## Monitoring and Scaling

- Scale workers by adjusting the replicas in `kubernetes/09-worker-deployment.yaml`.
- Monitor GPU usage with Kubernetes metrics or NVIDIA DCGM exporter.
- Check logs with:
  ```bash
  kubectl logs -l app=smolvla-webapp
  kubectl logs -l app=smolvla-worker
  ```

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
