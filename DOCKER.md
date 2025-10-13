# Docker Deployment Guide

## 🐳 Docker Files Overview

This project includes the following Docker-related files:

- `Dockerfile` - Multi-stage build with security best practices
- `.dockerignore` - Excludes unnecessary files from Docker context
- `docker-compose.yml` - Production and development services
- `.gitignore` - Git version control exclusions

## 🏗️ Building the Docker Image

### Basic Build
```bash
docker build -t k8s-job-api .
```

### Build with Version Tag
```bash
docker build -t k8s-job-api:v1.0.0 .
```

### Build with Build Args (if needed)
```bash
docker build --build-arg PYTHON_VERSION=3.11 -t k8s-job-api .
```

## 🚀 Running with Docker

### Quick Start
```bash
# Run the container
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api
```

### With Environment Variables
```bash
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  -e DEFAULT_NAMESPACE=production \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api
```

### Access the API
- Swagger UI: http://localhost:5000/docs/
- Health Check: http://localhost:5000/
- API: http://localhost:5000/api/v1/

## 🐙 Docker Compose

### Production Deployment
```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f k8s-job-api

# Stop the service
docker-compose down
```

### Development Mode
```bash
# Start development service with live reload
docker-compose --profile dev up -d k8s-job-api-dev

# Access development API on port 5001
# http://localhost:5001/docs/
```

## 🔧 Configuration

### Environment Variables
Set these in your `docker-compose.yml` or pass with `-e`:

```yaml
environment:
  - DEBUG=false
  - HOST=0.0.0.0
  - PORT=5000
  - DEFAULT_NAMESPACE=default
  - LOG_LEVEL=INFO
```

### Kubernetes Configuration
The container expects kubeconfig to be mounted:

#### For External Cluster Access:
```bash
-v ~/.kube:/home/appuser/.kube:ro
```

#### For In-Cluster Deployment:
No volume mount needed - will use service account automatically.

## 🏭 Production Deployment

### Docker Swarm
```yaml
version: '3.8'
services:
  k8s-job-api:
    image: k8s-job-api:v1.0.0
    ports:
      - "5000:5000"
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
    environment:
      - DEBUG=false
      - LOG_LEVEL=WARNING
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: k8s-job-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: k8s-job-api
  template:
    metadata:
      labels:
        app: k8s-job-api
    spec:
      containers:
      - name: k8s-job-api
        image: k8s-job-api:v1.0.0
        ports:
        - containerPort: 5000
        env:
        - name: DEBUG
          value: "false"
        - name: LOG_LEVEL
          value: "INFO"
```

## 🔍 Health Checks

The Dockerfile includes a health check that verifies the API is responding:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/')" || exit 1
```

Check container health:
```bash
docker ps  # STATUS will show (healthy) or (unhealthy)
```

## 🛡️ Security Features

The Docker image includes security best practices:

- **Non-root user**: Runs as `appuser`
- **Minimal base image**: Uses `python:3.11-slim`
- **No cached packages**: `PIP_NO_CACHE_DIR=1`
- **Read-only kubeconfig**: Mounted with `:ro` flag
- **Proper file permissions**: `chown` for app directory

## 📊 Monitoring

### View Logs
```bash
# Docker
docker logs k8s-job-api -f

# Docker Compose
docker-compose logs -f k8s-job-api
```

### Resource Usage
```bash
# View container stats
docker stats k8s-job-api
```

## 🔄 Updates and Rollbacks

### Update to New Version
```bash
# Build new version
docker build -t k8s-job-api:v1.1.0 .

# Update docker-compose.yml with new tag
# Then restart
docker-compose up -d
```

### Rollback
```bash
# Change back to previous version in docker-compose.yml
# Then restart
docker-compose up -d
```

## 🧹 Cleanup

### Remove Containers
```bash
docker-compose down
docker rm k8s-job-api
```

### Remove Images
```bash
docker rmi k8s-job-api
```

### Clean Up Everything
```bash
docker system prune -a
```