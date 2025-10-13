"""Kubernetes service layer for job operations."""
import logging
from typing import Dict, List, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.models.job import JobCreateRequest, JobResponse, JobStatusResponse, JobListResponse
from app.config.config import get_config

logger = logging.getLogger(__name__)


class KubernetesService:
    """Service class for Kubernetes operations."""

    def __init__(self):
        """Initialize the Kubernetes service."""
        self.batch_v1 = None
        self.config = get_config()
        self._init_kubernetes_client()

    def _init_kubernetes_client(self):
        """Initialize Kubernetes client based on environment."""
        try:
            import os
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                # Running inside cluster
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes configuration")
            else:
                # Running outside cluster
                config.load_kube_config()
                logger.info("Loaded kubeconfig from local environment")
            
            self.batch_v1 = client.BatchV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    def create_job(self, job_request: JobCreateRequest) -> JobResponse:
        """Create a Kubernetes job."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = job_request.namespace or self.config.DEFAULT_NAMESPACE

        # Build container spec
        container_spec = {
            "name": job_request.name,
            "image": job_request.image
        }

        if job_request.command:
            if isinstance(job_request.command, str):
                container_spec["command"] = job_request.command.split()
            elif isinstance(job_request.command, list):
                container_spec["command"] = job_request.command

        # Build pod spec
        pod_spec = {
            "containers": [container_spec],
            "restartPolicy": "Never"
        }

        if job_request.node_selector:
            pod_spec["nodeSelector"] = job_request.node_selector

        # Build labels
        labels = job_request.labels or {"app": job_request.name}

        # Build job manifest
        job_manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": job_request.name},
            "spec": {
                "template": {
                    "metadata": {"labels": labels},
                    "spec": pod_spec
                },
                "backoffLimit": job_request.backoff_limit
            }
        }

        try:
            response = self.batch_v1.create_namespaced_job(
                body=job_manifest,
                namespace=namespace
            )
            
            logger.info(f"Created job {job_request.name} in namespace {namespace}")
            
            return JobResponse(
                status="success",
                job_name=response.metadata.name,
                namespace=response.metadata.namespace,
                uid=response.metadata.uid,
                creation_timestamp=response.metadata.creation_timestamp.isoformat()
            )
        except ApiException as e:
            logger.error(f"Failed to create job {job_request.name}: {e}")
            if e.status == 409:
                raise Exception(f"Job '{job_request.name}' already exists in namespace '{namespace}'. Use a different name or delete the existing job first.")
            raise Exception(f"Kubernetes API error: {e.reason}")

    def get_job_status(self, job_name: str, namespace: Optional[str] = None) -> JobStatusResponse:
        """Get the status of a Kubernetes job."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = namespace or self.config.DEFAULT_NAMESPACE

        try:
            response = self.batch_v1.read_namespaced_job_status(
                name=job_name,
                namespace=namespace
            )

            status = response.status
            conditions = []
            if status.conditions:
                conditions = [
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason or "",
                        "message": condition.message or ""
                    } for condition in status.conditions
                ]

            return JobStatusResponse(
                job_name=response.metadata.name,
                namespace=response.metadata.namespace,
                active=status.active or 0,
                succeeded=status.succeeded or 0,
                failed=status.failed or 0,
                completion_time=status.completion_time.isoformat() if status.completion_time else None,
                start_time=status.start_time.isoformat() if status.start_time else None,
                conditions=conditions
            )
        except ApiException as e:
            if e.status == 404:
                raise Exception(f"Job {job_name} not found in namespace {namespace}")
            logger.error(f"Failed to get job status for {job_name}: {e}")
            raise Exception(f"Kubernetes API error: {e.reason}")

    def list_jobs(self, namespace: Optional[str] = None) -> JobListResponse:
        """List all jobs in a namespace."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = namespace or self.config.DEFAULT_NAMESPACE

        try:
            response = self.batch_v1.list_namespaced_job(namespace=namespace)

            jobs = []
            for job in response.items:
                status = job.status
                jobs.append({
                    "name": job.metadata.name,
                    "namespace": job.metadata.namespace,
                    "creation_timestamp": job.metadata.creation_timestamp.isoformat(),
                    "active": status.active or 0,
                    "succeeded": status.succeeded or 0,
                    "failed": status.failed or 0,
                    "completion_time": status.completion_time.isoformat() if status.completion_time else None
                })

            return JobListResponse(
                namespace=namespace,
                jobs=jobs,
                total=len(jobs)
            )
        except ApiException as e:
            logger.error(f"Failed to list jobs: {e}")
            raise Exception(f"Kubernetes API error: {e.reason}")

    def delete_job(self, job_name: str, namespace: Optional[str] = None) -> Dict[str, str]:
        """Delete a Kubernetes job."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = namespace or self.config.DEFAULT_NAMESPACE

        try:
            # Check if job exists first
            try:
                self.batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
            except ApiException as e:
                if e.status == 404:
                    raise Exception(f"Job '{job_name}' not found in namespace '{namespace}'")
                raise

            # Delete the job
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                body=client.V1DeleteOptions(
                    propagation_policy='Background'  # Also delete pods
                )
            )

            logger.info(f"Deleted job {job_name} in namespace {namespace}")
            return {
                "status": "success",
                "message": f"Job '{job_name}' deleted from namespace '{namespace}'"
            }
        except ApiException as e:
            logger.error(f"Failed to delete job {job_name}: {e}")
            raise Exception(f"Kubernetes API error: {e.reason}")

    def job_exists(self, job_name: str, namespace: Optional[str] = None) -> Dict[str, any]:
        """Check if a job exists."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = namespace or self.config.DEFAULT_NAMESPACE

        try:
            self.batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
            return {
                "exists": True,
                "job_name": job_name,
                "namespace": namespace
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "exists": False,
                    "job_name": job_name,
                    "namespace": namespace
                }
            raise Exception(f"Kubernetes API error: {e.reason}")


# Global service instance
kubernetes_service = KubernetesService()