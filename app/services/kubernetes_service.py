"""Kubernetes service layer for job operations."""

import os
import logging
from typing import Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import uuid

from app.models.job import (
    JobCreateRequest,
    JobResponse,
)
from app.config.config import get_config

logger = logging.getLogger(__name__)


class KubernetesService:
    """Service class for Kubernetes operations."""

    def __init__(self):
        """Initialize the Kubernetes service."""
        self.batch_v1 = None
        self.core_v1 = None
        self.config = get_config()
        self._init_kubernetes_client()

    def _init_kubernetes_client(self):
        """Initialize Kubernetes client based on environment."""
        try:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                # Running inside cluster
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes configuration")
            else:
                # Running outside cluster
                config.load_kube_config()
                logger.info("Loaded kubeconfig from local environment")

            self.batch_v1 = client.BatchV1Api()
            self.core_v1 = client.CoreV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    def _build_llama_curl_command(self, job_request: JobCreateRequest) -> str:
        """Build the curl command for LLaMA completion request."""
        json_data = {
            "prompt": job_request.prompt,
            "n_predict": job_request.n_predict,
            "ignore_eos": True,
            "temperature": job_request.temperature,
        }

        # Escape quotes in JSON for shell command
        import json

        json_str = json.dumps(json_data).replace('"', '\\"')

        return (
            "curl --request POST "
            "--url http://$HOST_IP:8080/completion "
            '--header "Content-Type: application/json" '
            f'--data "{json_str}"'
        )

    def _build_container_spec(self, job_request: JobCreateRequest) -> Dict:
        """Build the container specification."""
        container_name = str(uuid.uuid4())[:8]

        return {
            "name": container_name,
            "image": "curlimages/curl:8.9.1",
            "env": [{"name": "PROMPT", "value": job_request.prompt}],
            "command": ["sh", "-c", self._build_llama_curl_command(job_request)],
        }

    def _build_pod_spec(self, job_request: JobCreateRequest) -> Dict:
        """Build the pod specification."""
        pod_spec = {
            "schedulerName": "llama-scheduler",
            "hostNetwork": True,
            "restartPolicy": "Never",
            "containers": [self._build_container_spec(job_request)],
        }

        if job_request.node_selector:
            pod_spec["nodeSelector"] = job_request.node_selector

        return pod_spec

    def _build_job_manifest(self, job_request: JobCreateRequest) -> Dict:
        """Build the complete job manifest."""
        labels = job_request.labels or {"app": job_request.name}

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": job_request.name},
            "spec": {
                "template": {
                    "metadata": {"labels": labels},
                    "spec": self._build_pod_spec(job_request),
                },
                "backoffLimit": job_request.backoff_limit,
            },
        }

    def create_job(self, job_request: JobCreateRequest) -> Dict:
        """Create a Kubernetes job."""
        if not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = job_request.namespace or self.config.DEFAULT_NAMESPACE
        job_manifest = self._build_job_manifest(job_request)

        try:
            response = self.batch_v1.create_namespaced_job(
                body=job_manifest, namespace=namespace
            )

            logger.info(f"Created job {job_request.name} in namespace {namespace}")

            return JobResponse(
                status="success",
                job_name=response.metadata.name,
                namespace=response.metadata.namespace,
                uid=response.metadata.uid,
                creation_timestamp=response.metadata.creation_timestamp.isoformat(),
            )
        except ApiException as e:
            logger.error(f"Failed to create job {job_request.name}: {e}")
            if e.status == 409:
                raise Exception(
                    f"Job '{job_request.name}' already exists in namespace '{namespace}'. "
                    "Use a different name or delete the existing job first."
                )
            raise Exception(f"Kubernetes API error: {e.reason}")

    def get_job_logs(self, job_name: str, namespace: Optional[str] = None) -> Dict[str, str]:
        """Get logs from the pod(s) associated with a job."""
        if not self.core_v1 or not self.batch_v1:
            raise Exception("Kubernetes client not initialized")

        namespace = namespace or self.config.DEFAULT_NAMESPACE

        try:
            # First, verify the job exists
            job = self.batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
            
            # Get pods associated with this job
            label_selector = f"job-name={job_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )

            if not pods.items:
                return {
                    "job_name": job_name,
                    "namespace": namespace,
                    "status": "no_pods",
                    "message": "No pods found for this job yet",
                    "logs": ""
                }

            # Get logs from the first pod (jobs typically have one pod)
            pod = pods.items[0]
            pod_name = pod.metadata.name
            pod_status = pod.status.phase

            # Check if pod has completed or is running
            if pod_status in ["Pending", "Unknown"]:
                return {
                    "job_name": job_name,
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "status": pod_status.lower(),
                    "message": f"Pod is {pod_status}, logs not yet available",
                    "logs": ""
                }

            try:
                # Get logs from the pod
                logs = self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=1000  # Limit to last 1000 lines
                )

                return {
                    "job_name": job_name,
                    "namespace": namespace,
                    "pod_name": pod_name,
                    "status": pod_status.lower(),
                    "logs": logs
                }
            except ApiException as log_err:
                if log_err.status == 400:
                    # Pod exists but containers haven't started yet
                    return {
                        "job_name": job_name,
                        "namespace": namespace,
                        "pod_name": pod_name,
                        "status": "starting",
                        "message": "Pod containers are still starting",
                        "logs": ""
                    }
                raise

        except ApiException as e:
            if e.status == 404:
                raise Exception(f"Job '{job_name}' not found in namespace '{namespace}'")
            logger.error(f"Failed to get logs for job {job_name}: {e}")
            raise Exception(f"Kubernetes API error: {e.reason}")

# Global service instance
kubernetes_service = KubernetesService()
