# SmolVLA Training SaaS Bug Log

This document tracks significant bugs and their solutions in the SmolVLA Training SaaS system.

## Docker Compose Issues

### ContainerConfig Error (Fixed: June 15, 2025)

**Issue**: When attempting to start containers with `docker-compose up -d worker`, the following error occurred:
```
ERROR: for worker  'ContainerConfig'
Traceback (most recent call last):
  File "docker-compose", line 3, in <module>
  ...
  File "compose/service.py", line 1579, in get_container_data_volumes
KeyError: 'ContainerConfig'
```

**Root Cause**: This error was related to either:
1. A bug in docker-compose v1.29.2 when handling volume bindings
2. Possible corruption in Docker's volume metadata
3. Conflicts between multiple docker-compose files

**Solution**:
1. Removed `docker-compose.override.yml` to eliminate potential volume binding conflicts
2. Upgraded to Docker Compose V2 (plugin-based version)
3. Restarted the Docker daemon to clear any corrupted state

**Commands Used**:
```bash
# Install Docker Compose V2
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Restart Docker daemon
sudo systemctl restart docker

# Start services with new compose
docker compose up -d
```

## Training Script Issues

### Module Path Error (Fixed: June 15, 2025)

**Issue**: Training jobs failed with the error `No module named train`

**Root Cause**: The Celery task was using an incorrect module path in the command construction.

**Solution**: Updated the module path in `app/tasks.py` to use the correct path:
```python
# From
"python", "-m", "train"
# To
"python", "-m", "lerobot.scripts.train"
```

### Parameter Format Error (Fixed: June 15, 2025)

**Issue**: Training jobs failed with a `draccus.utils.DecodingError` stating that fields like `name` are not valid for `SmolVLAConfig`.

**Root Cause**: The SmolVLA training script expects parameters in a specific dot-notation format (e.g., `--policy.path=lerobot/smolvla_base`) rather than the nested YAML configuration we were providing.

**Solution**: Updated `app/tasks.py` to construct CLI arguments in the correct format, based on the Google Colab example:
```python
cli_args = [
    f"--policy.path=lerobot/smolvla_base",
    f"--dataset.repo_id={job.dataset_repo_id}",
    f"--batch_size=8",
    f"--steps={job.steps}",
    # ... other parameters
]
```

## Log Truncation Issues

### Truncated Error Logs (Fixed: June 15, 2025)

**Issue**: Error logs from failed training jobs were being truncated to 10,000 characters, making it difficult to diagnose issues.

**Root Cause**: The `train_smolvla` task in `app/tasks.py` had a hardcoded limit for log capture.

**Solution**: Enhanced logging to:
1. Store full stderr without truncation
2. Increase stdout limit to 50,000 characters
3. Save complete logs to a `training_log.txt` file in the output directory

## Development Workflow Issues

### Local Development vs Production (Fixed: June 15, 2025)

**Issue**: Worker service in docker-compose was using a pre-built image, making it difficult to test local code changes.

**Root Cause**: The docker-compose.yml file was configured to use `smolvla-training-saas:latest` instead of building from local code.

**Solution**:
1. Updated docker-compose.yml to build the worker service from the local context
2. Established a git branching workflow with separate 'dev' and 'deploy' branches
3. Development changes are made on the 'dev' branch, tested locally, then merged to 'deploy' for production
