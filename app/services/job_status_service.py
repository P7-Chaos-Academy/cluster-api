"""Service for getting job status from Kubernetes."""

import os
import logging
from typing import List, Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.config.config import get_config

logger = logging.getLogger(__name__)


class JobStatusService:
    """Service to get job status from Kubernetes."""

    def __init__(self):
        self.core_v1 = None
        self.config = get_config()
        self._init_kubernetes_client()

    def _init_kubernetes_client(self):
        """Initialize Kubernetes client based on environment."""
        try:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes configuration")
            else:
                config.load_kube_config()
                logger.info("Loaded kubeconfig from local environment")

            self.core_v1 = client.CoreV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")

    def get_all_job_statuses(self, namespace: Optional[str] = None) -> List[Dict]:
        """
        Get status for all jobs from Kubernetes.

        Status can be:
        - finished: Job completed successfully
        - failed: Job failed
        - running: Job is currently running on a node
        - pending: Job created but not yet scheduled/running
        """
        namespace = namespace or self.config.DEFAULT_NAMESPACE
        statuses = []

        if not self.core_v1:
            return statuses

        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector="job-name",
            )

            for pod in pods.items:
                if pod.spec.scheduler_name != "llama-scheduler":
                    continue

                job_name = pod.metadata.labels.get("job-name", "")
                node_name = pod.spec.node_name
                phase = pod.status.phase

                statuses.append({
                    "job_name": job_name,
                    "status": phase.lower(),
                    "node_name": node_name,
                    "namespace": namespace,
                })

        except ApiException as e:
            logger.error(f"Failed to get Kubernetes jobs: {e}")

        return statuses


# Global service instance
job_status_service = JobStatusService()
