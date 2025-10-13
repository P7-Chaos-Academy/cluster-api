# Installation and Setup Guide

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install flask flask-restx kubernetes PyYAML marshmallow
   ```

2. **Or install from requirements.txt:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python run.py
   ```

4. **Access the API:**
   - API Documentation (Swagger UI): http://localhost:5000/docs/
   - Health Check: http://localhost:5000/
   - API Base: http://localhost:5000/api/v1/

## Project Structure

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
│   │   └── job_models.py        # Request/Response models
│   └── services/
│       ├── __init__.py
│       └── kubernetes_service.py # Kubernetes operations
├── requirements.txt
├── setup.py
├── run.py                       # Application entry point
├── README.md                    # Updated documentation
└── INSTALL.md                   # This file
```

## Environment Variables

Set these environment variables to configure the API:

- `DEBUG`: Enable debug mode (default: False)
- `HOST`: Host to bind to (default: 0.0.0.0)
- `PORT`: Port to listen on (default: 5000)
- `DEFAULT_NAMESPACE`: Default Kubernetes namespace (default: default)
- `LOG_LEVEL`: Logging level (default: INFO)

## Docker Setup (Optional)

Create a Dockerfile for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
```

## API Features

- ✅ **Layered Architecture**: Controllers, Services, Models
- ✅ **Swagger Documentation**: Auto-generated API docs at `/docs/`
- ✅ **Input Validation**: Marshmallow schemas for request validation
- ✅ **Error Handling**: Proper HTTP status codes and error messages
- ✅ **Configuration Management**: Environment-based configuration
- ✅ **Kubernetes Integration**: Both in-cluster and external kubeconfig support