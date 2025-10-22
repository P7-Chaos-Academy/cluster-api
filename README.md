# Kubernetes Job API

A professionally structured REST API for creating and managing Kubernetes jobs with Swagger documentation and layered architecture.

## 🚀 Features

- **Layered Architecture**: Proper separation of controllers, services, and models
- **Swagger Documentation**: Auto-generated API documentation at `/docs/`
- **Input Validation**: Marshmallow schemas for robust request validation
- **Error Handling**: Comprehensive error handling with proper HTTP status codes
- **Configuration Management**: Environment-based configuration
- **Kubernetes Integration**: Support for both in-cluster and external kubeconfig
- **Professional Structure**: Follows Flask best practices
- **GPIO Hardware Support**: Dual backend (RPi.GPIO or lgpio) automatically selects the best driver on Raspberry Pi hardware

## 📁 Project Structure

```
py-test/
├── app/
│   ├── __init__.py
│   ├── app.py                    # Flask application factory
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py            # Configuration management
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── job_controller.py    # REST API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   └── job_models.py        # Request/Response schemas
│   └── services/
│       ├── __init__.py
│       └── kubernetes_service.py # Kubernetes operations
├── requirements.txt
├── setup.py
├── run.py                       # Application entry point
├── README.md
└── INSTALL.md
```

## 🛠 Installation & Deployment

### Option 1: Docker (Recommended)
The easiest way to run the API is using Docker:

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t k8s-job-api .
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api
```

### Option 2: Local Python Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

### Option 3: Development with Docker
```bash
# Run development mode with live reload
docker-compose --profile dev up -d k8s-job-api-dev
```

## 🏃 Access the Application

The API will be available at:
- **Swagger UI**: http://localhost:5000/docs/
- **API Base**: http://localhost:5000/api/v1/
- **Health Check**: http://localhost:5000/

## 🔧 Kubernetes Cluster Integration

The API can work with Kubernetes clusters in multiple ways:

### 1. **External Cluster Access (Development)**
When running outside a Kubernetes cluster (your local machine):

```bash
# Docker automatically mounts your kubeconfig
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api
```

**Requirements:**
- `kubectl` configured and working on your machine
- Valid kubeconfig file in `~/.kube/config`
- Network access to your Kubernetes API server

### 2. **In-Cluster Deployment (Production)**
When deployed inside a Kubernetes cluster:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: k8s-job-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: k8s-job-api
  template:
    metadata:
      labels:
        app: k8s-job-api
    spec:
      serviceAccountName: k8s-job-api  # Required for job creation
      containers:
      - name: k8s-job-api
        image: k8s-job-api:latest
        ports:
        - containerPort: 5000
        env:
        - name: DEBUG
          value: "false"
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: k8s-job-api
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-job-api
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: k8s-job-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: k8s-job-api
subjects:
- kind: ServiceAccount
  name: k8s-job-api
  namespace: default
```

**Automatic Detection:**
The API automatically detects its environment:
- **Outside cluster**: Uses `~/.kube/config`
- **Inside cluster**: Uses service account token

### 3. **Raspberry Pi / Edge Deployment**
Perfect for edge computing scenarios like Raspberry Pi and Jetson devices. Follow the GPIO guidance below before invoking hardware endpoints.

## 🧲 GPIO Node Activation

The API exposes `POST /api/v1/nodes/<pin>` to pulse a Raspberry Pi GPIO pin for 0.3 seconds. Hardware access now supports both the legacy `RPi.GPIO` driver and the newer `lgpio` bindings, letting the service run on Raspberry Pi 5 kernels that only provide `/dev/gpiochip*`.

### Runtime dependencies
- Python wheel `lgpio` (added to `requirements.txt`) — supplies libgpiod bindings.
- Optional: `RPi.GPIO` remains installed for backwards compatibility when gpiomem is available.

### Host preparation checklist
1. **Kernel**: Use the Raspberry Pi Foundation kernel or any build that exposes `/dev/gpiomem0` and `/dev/gpiochip0`.
2. **Symlink**: Ensure `/dev/gpiomem` points to `/dev/gpiomem0` (e.g. `sudo ln -sf /dev/gpiomem0 /dev/gpiomem`).
3. **Permissions**: Add the provided udev rules (or equivalent) so the container user can access the gpio group.

### Kubernetes deployment hints
- Mount the required device nodes into the pod:
  ```yaml
        volumeMounts:
          - name: gpiochip0
            mountPath: /dev/gpiochip0
          - name: gpiomem
            mountPath: /dev/gpiomem
          - name: devicetree
            mountPath: /proc/device-tree
            readOnly: true
      volumes:
        - name: gpiochip0
          hostPath:
            path: /dev/gpiochip0
            type: CharDevice
        - name: gpiomem
          hostPath:
            path: /dev/gpiomem
            type: CharDevice
        - name: devicetree
          hostPath:
            path: /proc/device-tree
            type: Directory
  ```
- The service automatically prefers `lgpio` and falls back to `RPi.GPIO` if it fails; check the startup log for `Using lgpio backend for GPIO operations.`
- If the endpoint returns 503, confirm the pod can see `/dev/gpiomem` and `/proc/device-tree`, then redeploy after fixing the mounts.

Perfect for edge computing scenarios like your Jetson setup:

```bash
# Build for ARM architecture (if cross-compiling)
docker buildx build --platform linux/arm64 -t k8s-job-api:arm64 .

# Run on your Raspberry Pi/Jetson
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api:arm64
```

## 📚 API Documentation

### Interactive Swagger Documentation
Visit http://localhost:5000/docs/ for the complete interactive API documentation.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/docs/` | Swagger UI documentation |
| `POST` | `/api/v1/jobs` | Create a new job |
| `GET` | `/api/v1/jobs` | List all jobs |
| `GET` | `/api/v1/jobs/{name}` | Get job status |
| `DELETE` | `/api/v1/jobs/{name}` | Delete a job |
| `GET` | `/api/v1/jobs/{name}/exists` | Check if job exists |

## 🔧 Configuration

Configure the API using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | Enable debug mode |
| `HOST` | `0.0.0.0` | Host to bind to |
| `PORT` | `5000` | Port to listen on |
| `DEFAULT_NAMESPACE` | `default` | Default Kubernetes namespace |
| `LOG_LEVEL` | `INFO` | Logging level |

## 📝 Usage Examples

### Create a Job (Your Original Use Case)
```bash
# Create a job targeting your Jetson hardware
curl -X POST http://localhost:5000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-nano",
    "image": "busybox",
    "command": ["echo", "Hello from Nano!"],
    "nodeSelector": {"hardware": "jetson"},
    "labels": {"app": "hello"}
  }'
```

**Response:**
```json
{
  "status": "success",
  "job_name": "hello-nano",
  "namespace": "default",
  "uid": "abc123...",
  "creation_timestamp": "2025-10-13T09:00:00Z"
}
```

### Check Job Status
```bash
curl http://localhost:5000/api/v1/jobs/hello-nano
```

**Response:**
```json
{
  "job_name": "hello-nano",
  "namespace": "default",
  "active": 0,
  "succeeded": 1,
  "failed": 0,
  "completion_time": "2025-10-13T09:01:30Z",
  "start_time": "2025-10-13T09:01:00Z",
  "conditions": [
    {
      "type": "Complete",
      "status": "True",
      "reason": "JobComplete",
      "message": "Job completed successfully"
    }
  ]
}
```

### List All Jobs
```bash
curl http://localhost:5000/api/v1/jobs
```

### Advanced Examples

#### GPU Workload (for ML/AI)
```bash
curl -X POST http://localhost:5000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpu-training",
    "image": "tensorflow/tensorflow:latest-gpu",
    "command": ["python", "-c", "import tensorflow as tf; print(tf.config.list_physical_devices(\"GPU\"))"],
    "nodeSelector": {"accelerator": "nvidia-tesla"},
    "labels": {"type": "ml-training", "priority": "high"}
  }'
```

#### Batch Processing Job
```bash
curl -X POST http://localhost:5000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "data-processor",
    "image": "python:3.11",
    "command": ["python", "-c", "print(\"Processing data batch...\")"],
    "backoffLimit": 3,
    "labels": {"component": "batch-processor"}
  }'
```

### Delete a Job
```bash
curl -X DELETE http://localhost:5000/api/v1/jobs/hello-nano
```

### Check if Job Exists
```bash
curl http://localhost:5000/api/v1/jobs/hello-nano/exists
```

## 🏗 Architecture

### Controllers Layer (`app/controllers/`)
- Handles HTTP requests and responses
- Input validation using Marshmallow schemas
- Swagger documentation with Flask-RESTX

### Services Layer (`app/services/`)
- Business logic and Kubernetes operations
- Error handling and logging
- Reusable service methods

### Models Layer (`app/models/`)
- Request/response data schemas
- Input validation rules
- Swagger model definitions

### Configuration (`app/config/`)
- Environment-based configuration
- Default values and validation
- Centralized config management

## 🐳 Docker Deployment

### Quick Start with Docker Compose
```bash
# Production deployment
docker-compose up -d

# Development with live reload
docker-compose --profile dev up -d k8s-job-api-dev
```

### Manual Docker Commands
```bash
# Build the image
docker build -t k8s-job-api .

# Run with kubeconfig mounting (for external cluster access)
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api

# Run with custom configuration
docker run -d \
  --name k8s-job-api \
  -p 5000:5000 \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  -e DEFAULT_NAMESPACE=production \
  -v ~/.kube:/home/appuser/.kube:ro \
  k8s-job-api
```

### Docker Features
- ✅ **Security**: Runs as non-root user
- ✅ **Health Checks**: Built-in container health monitoring  
- ✅ **Multi-arch**: Supports ARM64 for Raspberry Pi/Jetson
- ✅ **Optimized**: Minimal image size with layer caching

### Verify Deployment
```bash
# Check container status
docker ps

# View logs
docker logs k8s-job-api -f

# Test health endpoint
curl http://localhost:5000/
```

## 🔄 Migration from Original Script

Your original single-file script has been transformed into a production-ready application:

### **Before (k8s-job.py):**
```python
# Hardcoded job creation
job_manifest = {
    "metadata": {"name": "hello-nano"},
    "spec": {
        "template": {
            "spec": {
                "containers": [{
                    "name": "hello",
                    "image": "busybox",
                    "command": ["echo", "Hello from Nano!"]
                }],
                "nodeSelector": {"hardware": "jetson"}
            }
        }
    }
}

# Direct execution
batch_v1.create_namespaced_job(body=job_manifest, namespace="default")
```

### **After (Dockerized API):**
```bash
# Same result via REST API
docker-compose up -d

curl -X POST http://localhost:5000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hello-nano",
    "image": "busybox",
    "command": ["echo", "Hello from Nano!"],
    "nodeSelector": {"hardware": "jetson"}
  }'
```

### **Improvements:**
- ✅ **RESTful API**: HTTP endpoints instead of script execution
- ✅ **Docker Support**: Containerized deployment with docker-compose
- ✅ **Swagger Documentation**: Interactive API docs at `/docs/`
- ✅ **Cluster Integration**: Works both inside and outside K8s clusters
- ✅ **Error Handling**: Proper validation and conflict resolution
- ✅ **Security**: Non-root execution, read-only volume mounts
- ✅ **Monitoring**: Health checks and structured logging
- ✅ **Scalability**: Multiple instances, load balancing ready

### **Production Benefits:**
- **Automation**: API can be called from CI/CD pipelines
- **Integration**: Easy integration with other microservices
- **Monitoring**: Built-in health checks and logging
- **Security**: RBAC permissions, service accounts
- **Scalability**: Horizontal scaling with replicas

## 🔧 Troubleshooting

### Common Docker Issues

#### Permission Denied
```bash
# If you get permission errors, ensure Docker is running and your user is in docker group
sudo usermod -aG docker $USER
newgrp docker
```

#### Port Already in Use
```bash
# Check what's using port 5000
sudo lsof -i :5000

# Use a different port
docker run -p 5001:5000 k8s-job-api
```

### Kubernetes Connection Issues

#### "Kubernetes client not initialized"
**Cause**: kubeconfig not found or invalid
**Solution**:
```bash
# Verify kubectl works
kubectl cluster-info

# Check kubeconfig location
ls -la ~/.kube/config

# Ensure Docker can access kubeconfig
docker run --rm -v ~/.kube:/tmp/.kube k8s-job-api ls -la /tmp/.kube
```

#### "Job already exists" (409 Conflict)
**Cause**: Job names must be unique
**Solutions**:
```bash
# Option 1: Delete existing job
curl -X DELETE http://localhost:5000/api/v1/jobs/hello-nano

# Option 2: Use unique name with timestamp
curl -X POST http://localhost:5000/api/v1/jobs \
  -d '{"name": "hello-nano-'$(date +%s)'", "image": "busybox"}'
```

#### RBAC Permission Errors (In-Cluster)
**Cause**: Service account lacks permissions
**Solution**: Apply proper RBAC configuration:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-job-api
rules:
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list", "delete"]
```

### Debugging

#### View API Logs
```bash
# Docker logs
docker logs k8s-job-api -f

# Docker Compose logs  
docker-compose logs -f k8s-job-api

# Filter for errors only
docker logs k8s-job-api 2>&1 | grep ERROR
```

#### Test Kubernetes Connectivity
```bash
# Test from inside container
docker exec -it k8s-job-api python -c "
from kubernetes import client, config
config.load_kube_config()
print('Connection successful!')
"
```

#### Health Check Status
```bash
# Check container health
docker inspect k8s-job-api | grep Health -A 10

# Manual health check
curl http://localhost:5000/ && echo "API is healthy"
```

### Performance Tuning

#### For High Job Creation Volume
```yaml
# docker-compose.yml
environment:
  - LOG_LEVEL=WARNING  # Reduce log verbosity
  - WORKERS=4          # If using gunicorn

# Scale replicas
docker-compose up --scale k8s-job-api=3
```

For more detailed troubleshooting, see `DOCKER.md`.