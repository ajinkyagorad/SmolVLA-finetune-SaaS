#!/bin/bash
set -e

echo "=== SmolVLA Training SaaS Deployment Script ==="
echo "Extracting project archive..."
mkdir -p smolvla
unzip -o smolvla-project.zip -d smolvla
cd smolvla

echo "=== Installing Docker and Docker Compose ==="
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

echo "=== Creating docker-compose.yml ==="
cat > docker-compose.yml << 'EOL'
version: '3'

services:
  postgres:
    image: postgres:13-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgrespassword
      - POSTGRES_DB=smolvladb
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:6-alpine
    restart: always

  webapp:
    image: smolvla-training-saas:latest
    command: gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
    environment:
      - FLASK_APP=app
      - FLASK_ENV=production
      - FLASK_SECRET_KEY=example-flask-secret-key-replace-in-production
      - DATABASE_USER=postgres
      - DATABASE_PASSWORD=postgrespassword
      - DATABASE_HOST=postgres
      - DATABASE_NAME=smolvladb
      - SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgrespassword@postgres/smolvladb
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - ENCRYPTION_KEY=example-encryption-key-replace-in-production
      - UPLOAD_FOLDER=/training-output
    volumes:
      - training-output:/training-output
    ports:
      - "80:5000"
    depends_on:
      - postgres
      - redis
    restart: always

  worker:
    image: smolvla-training-saas:latest
    command: celery -A app.celery worker --loglevel=info --concurrency=1
    environment:
      - DATABASE_USER=postgres
      - DATABASE_PASSWORD=postgrespassword
      - DATABASE_HOST=postgres
      - DATABASE_NAME=smolvladb
      - SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgrespassword@postgres/smolvladb
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - ENCRYPTION_KEY=example-encryption-key-replace-in-production
      - UPLOAD_FOLDER=/training-output
    volumes:
      - training-output:/training-output
    depends_on:
      - postgres
      - redis
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: always

volumes:
  postgres-data:
  training-output:
EOL

echo "=== Building Docker image ==="
sudo docker build -t smolvla-training-saas:latest .

echo "=== Starting services ==="
sudo docker-compose up -d

echo "=== Checking service status ==="
sudo docker-compose ps

echo "=== Deployment complete ==="
echo "You can access the web application at http://$(hostname -I | awk '{print $1}')"
echo "To view logs: sudo docker-compose logs -f webapp"
