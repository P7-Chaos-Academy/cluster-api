"""Job controller with Flask-RESTX for API documentation."""
import logging
from flask import request
from flask_restx import Namespace, Resource, fields
from dataclasses import asdict

from app.models.job import JobCreateRequest, ErrorResponse
from app.services.kubernetes_service import kubernetes_service
from app.config.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Create namespace for jobs
api = Namespace('jobs', description='Kubernetes job operations')

# Define API models for Swagger documentation
job_create_model = api.model('JobCreate', {
    'name': fields.String(required=True, description='Job name (must follow Kubernetes naming conventions)', example='hello-nano'),
    'image': fields.String(required=True, description='Container image', example='busybox'),
    'command': fields.Raw(description='Command to run (string or array of strings)', example=['echo', 'Hello World!']),
    'namespace': fields.String(description='Kubernetes namespace', example='default'),
    'nodeSelector': fields.Raw(description='Node selector constraints', example={'hardware': 'jetson'}),
    'backoffLimit': fields.Integer(description='Job retry limit', default=1, example=1),
    'labels': fields.Raw(description='Custom labels for the job', example={'app': 'my-app'})
})

job_response_model = api.model('JobResponse', {
    'status': fields.String(description='Operation status', example='success'),
    'job_name': fields.String(description='Created job name', example='hello-nano'),
    'namespace': fields.String(description='Job namespace', example='default'),
    'uid': fields.String(description='Job UID', example='123e4567-e89b-12d3-a456-426614174000'),
    'creation_timestamp': fields.String(description='Job creation timestamp', example='2025-10-13T09:00:00Z')
})

job_status_model = api.model('JobStatus', {
    'job_name': fields.String(description='Job name', example='hello-nano'),
    'namespace': fields.String(description='Job namespace', example='default'),
    'active': fields.Integer(description='Number of active pods', example=0),
    'succeeded': fields.Integer(description='Number of succeeded pods', example=1),
    'failed': fields.Integer(description='Number of failed pods', example=0),
    'completion_time': fields.String(description='Job completion timestamp', example='2025-10-13T09:01:00Z'),
    'start_time': fields.String(description='Job start timestamp', example='2025-10-13T09:00:00Z'),
    'conditions': fields.List(fields.Raw(description='Job conditions'))
})

job_list_model = api.model('JobList', {
    'namespace': fields.String(description='Namespace', example='default'),
    'total': fields.Integer(description='Total number of jobs', example=5),
    'jobs': fields.List(fields.Raw(description='List of jobs'))
})

job_exists_model = api.model('JobExists', {
    'exists': fields.Boolean(description='Whether job exists', example=True),
    'job_name': fields.String(description='Job name', example='hello-nano'),
    'namespace': fields.String(description='Job namespace', example='default')
})

delete_response_model = api.model('DeleteResponse', {
    'status': fields.String(description='Operation status', example='success'),
    'message': fields.String(description='Operation message', example='Job deleted successfully')
})

error_model = api.model('Error', {
    'error': fields.String(description='Error message', example='Validation failed'),
    'details': fields.List(fields.String, description='Error details', example=['Field name is required'])
})


@api.route('/')
class JobList(Resource):
    """Job list operations."""

    @api.doc('list_jobs')
    @api.param('namespace', 'Kubernetes namespace', default='default')
    @api.marshal_with(job_list_model)
    @api.response(500, 'Internal server error', error_model)
    def get(self):
        """List all jobs in a namespace."""
        try:
            namespace = request.args.get('namespace', config.DEFAULT_NAMESPACE)
            result = kubernetes_service.list_jobs(namespace)
            return asdict(result)
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            api.abort(500, error=str(e))

    @api.doc('create_job')
    @api.expect(job_create_model, validate=True)
    @api.marshal_with(job_response_model, code=201)
    @api.response(400, 'Validation error', error_model)
    @api.response(500, 'Internal server error', error_model)
    def post(self):
        """Create a new Kubernetes job."""
        try:
            data = request.get_json()
            if not data:
                api.abort(400, error="Request body must be JSON")

            # Create and validate job request
            job_request = JobCreateRequest(
                name=data.get('name'),
                image=data.get('image'),
                command=data.get('command'),
                namespace=data.get('namespace'),
                node_selector=data.get('nodeSelector'),
                backoff_limit=data.get('backoffLimit', 1),
                labels=data.get('labels')
            )

            result = kubernetes_service.create_job(job_request)
            return asdict(result), 201

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            api.abort(400, error=str(e))
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            api.abort(500, error=str(e))


@api.route('/<string:job_name>')
class Job(Resource):
    """Individual job operations."""

    @api.doc('get_job_status')
    @api.param('namespace', 'Kubernetes namespace', default='default')
    @api.marshal_with(job_status_model)
    @api.response(404, 'Job not found', error_model)
    @api.response(500, 'Internal server error', error_model)
    def get(self, job_name):
        """Get the status of a specific job."""
        try:
            namespace = request.args.get('namespace', config.DEFAULT_NAMESPACE)
            result = kubernetes_service.get_job_status(job_name, namespace)
            return asdict(result)
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            if "not found" in str(e).lower():
                api.abort(404, error=str(e))
            api.abort(500, error=str(e))

    @api.doc('delete_job')
    @api.param('namespace', 'Kubernetes namespace', default='default')
    @api.marshal_with(delete_response_model)
    @api.response(404, 'Job not found', error_model)
    @api.response(500, 'Internal server error', error_model)
    def delete(self, job_name):
        """Delete a specific job."""
        try:
            namespace = request.args.get('namespace', config.DEFAULT_NAMESPACE)
            result = kubernetes_service.delete_job(job_name, namespace)
            return result
        except Exception as e:
            logger.error(f"Error deleting job: {e}")
            if "not found" in str(e).lower():
                api.abort(404, error=str(e))
            api.abort(500, error=str(e))


@api.route('/<string:job_name>/exists')
class JobExists(Resource):
    """Check if job exists."""

    @api.doc('check_job_exists')
    @api.param('namespace', 'Kubernetes namespace', default='default')
    @api.marshal_with(job_exists_model)
    @api.response(500, 'Internal server error', error_model)
    def get(self, job_name):
        """Check if a job exists."""
        try:
            namespace = request.args.get('namespace', config.DEFAULT_NAMESPACE)
            result = kubernetes_service.job_exists(job_name, namespace)
            return result
        except Exception as e:
            logger.error(f"Error checking job existence: {e}")
            api.abort(500, error=str(e))