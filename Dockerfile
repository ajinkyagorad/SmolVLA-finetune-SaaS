FROM  pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    bzip2 \
    ca-certificates \
    build-essential \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Install system libstdc++6 and copy to conda lib directory
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    && cp /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /opt/conda/lib/ \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Create app directory
WORKDIR /app

# Clone and install lerobot with smolvla dependencies
RUN git clone https://github.com/huggingface/lerobot.git /tmp/lerobot && \
    cd /tmp/lerobot && \
    pip install -e . && \
    pip install -e ".[smolvla]" && \
    cd /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Update Hugging Face libraries
RUN pip install -U huggingface_hub datasets
# Install newer libstdc++ from conda-forge
RUN conda install -c conda-forge libstdcxx-ng
# Copy application code
COPY app/ ./app/
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Create directory for training outputs
RUN mkdir -p /app/training_outputs && chmod 777 /app/training_outputs

# Expose port for Gunicorn
EXPOSE 8000

# Set default command to run the Flask app with Gunicorn
# For Celery workers, this will be overridden in the Kubernetes deployment
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
