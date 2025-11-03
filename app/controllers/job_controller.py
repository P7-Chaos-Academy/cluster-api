"""Job controller with Flask-RESTX for API documentation."""

import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from dataclasses import asdict

from app.models.job import JobCreateRequest
from app.services.kubernetes_service import kubernetes_service
from app.config.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Create namespace for jobs
api = Namespace("jobs", description="Kubernetes job operations")

# Define API models for Swagger documentation
job_create_model = api.model(
    "JobCreate",
    {
        "prompt": fields.String(
            description="Prompt to ask the LLM", example="Hello world!"
        ),
        "n_predict": fields.Integer(
            description="Number of tokens to predict (will default to 128)", example=128
        ),
        "temperature": fields.Float(
            description="Sampling temperature (How hot tempered the clanker will be) (will default to 0)",
            example=0.7,
        ),
    },
)

job_response_model = api.model(
    "JobResponse",
    {
        "status": fields.String(
            description="Status of the operation", example="success"
        ),
        "job_name": fields.String(
            description="Name of the created job", example="llama-job-abc123"
        ),
        "namespace": fields.String(
            description="Kubernetes namespace", example="default"
        ),
        "uid": fields.String(
            description="Unique identifier",
            example="550e8400-e29b-41d4-a716-446655440000",
        ),
        "creation_timestamp": fields.String(
            description="Creation timestamp", example="2025-11-03T12:00:00Z"
        ),
    },
)

error_model = api.model(
    "Error",
    {"error": fields.String(description="Error message", example="Invalid request")},
)

job_logs_model = api.model('JobLogs', {
    'job_name': fields.String(description='Name of the job', example='llama-job-abc123'),
    'namespace': fields.String(description='Kubernetes namespace', example='prompts'),
    'pod_name': fields.String(description='Pod name', example='llama-job-abc123-xyz12'),
    'status': fields.String(description='Pod status', example='succeeded'),
    'logs': fields.String(description='Job output logs', example='{"content": "Hello from LLaMA!"}'),
    'message': fields.String(description='Status message', example='')
})

@api.route('/')
class JobList(Resource):
    """Job list operations."""

    @api.doc("create_job")
    @api.expect(job_create_model, validate=True)
    @api.marshal_with(job_response_model, code=200)
    @api.response(400, "Validation error", error_model)
    @api.response(500, "Internal server error", error_model)
    def post(self):
        """Create a new Kubernetes job."""
        try:
            data = request.get_json()
            if not data:
                api.abort(400, error="Request body must be JSON")

            job_request = JobCreateRequest(
                prompt=data.get("prompt"),
                n_predict=data.get("n_predict", 128),
                temperature=data.get("temperature", 0.0),
            )

            result = kubernetes_service.create_job(job_request)
            return asdict(result), 201

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            api.abort(400, error=str(e))
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            api.abort(500, error=str(e))

@api.route('/<string:job_name>/logs')
@api.param('job_name', 'The job name')
class JobLogs(Resource):
    """Job logs operations."""
    @api.doc('get_job_logs')
    @api.marshal_with(job_logs_model, code=200)
    @api.response(404, 'Job not found', error_model)
    @api.response(500, 'Internal server error', error_model)
    def get(self, job_name):
        """Get logs/output from a Kubernetes job."""
        try:
            namespace = request.args.get('namespace', config.DEFAULT_NAMESPACE)
            result = kubernetes_service.get_job_logs(job_name, namespace)
            return result, 200

        except Exception as e:
            logger.error(f"Error getting job logs: {e}")
            if "not found" in str(e).lower():
                api.abort(404, error=str(e))
            api.abort(500, error=str(e))
