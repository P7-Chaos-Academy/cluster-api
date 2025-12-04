"""Service for aggregating job status from Kubernetes, Redis, and database."""

import os
import logging
from typing import List, Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import redis

from app.config.config import get_config
from app.repositories.job_repository import job_repository

logger = logging.getLogger(__name__)


class JobStatusService:
    """Service to aggregate job status from multiple sources."""

    def __init__(self):
        self.core_v1 = None
        self.batch_v1 = None
        self.redis_client = None
        self.config = get_config()
        self._init_kubernetes_client()
        self._init_redis_client()

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
            self.batch_v1 = client.BatchV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")

    def _init_redis_client(self):
        """Initialize Redis client for queue access."""
        try:
            redis_host = os.getenv(
                "REDIS_HOST", "redis.cluster-namespace.svc.cluster.local"
            )
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _get_enqueued_jobs(self) -> Dict[str, List[str]]:
        """Get all enqueued jobs from Redis, organized by node."""
        enqueued = {}
        if not self.redis_client:
            return enqueued

        try:
            # Get all keys (node names) from Redis
            # The scheduler uses node names as keys for per-node queues
            keys = self.redis_client.keys("*")
            for key in keys:
                key_type = self.redis_client.type(key)
                if key_type == "list":
                    items = self.redis_client.lrange(key, 0, -1)
                    if items:
                        enqueued[key] = items
        except Exception as e:
            logger.error(f"Failed to get enqueued jobs from Redis: {e}")

        return enqueued

    def _get_kubernetes_jobs(self, namespace: str) -> List[Dict]:
        """Get current job/pod states from Kubernetes."""
        k8s_jobs = []
        if not self.core_v1 or not self.batch_v1:
            return k8s_jobs

        try:
            # Get all pods scheduled by llama-scheduler
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector="job-name",
            )

            for pod in pods.items:
                # Only consider pods from llama-scheduler
                if pod.spec.scheduler_name != "llama-scheduler":
                    continue

                job_name = pod.metadata.labels.get("job-name", "")
                node_name = pod.spec.node_name
                phase = pod.status.phase

                k8s_jobs.append({
                    "job_name": job_name,
                    "pod_name": pod.metadata.name,
                    "node_name": node_name,
                    "phase": phase,
                })

        except ApiException as e:
            logger.error(f"Failed to get Kubernetes jobs: {e}")

        return k8s_jobs

    def get_all_job_statuses(self, namespace: Optional[str] = None) -> List[Dict]:
        """
        Get status for all jobs from all sources.

        Status can be:
        - finished: Job completed successfully
        - failed: Job failed
        - enqueued: Job is waiting in Redis queue
        - running: Job is currently running on a node
        - pending: Job created but not yet scheduled/running
        """
        namespace = namespace or self.config.DEFAULT_NAMESPACE
        statuses = []
        seen_jobs = set()

        # 1. Get running/pending jobs from Kubernetes
        k8s_jobs = self._get_kubernetes_jobs(namespace)
        for job in k8s_jobs:
            job_name = job["job_name"]
            phase = job["phase"]

            if phase == "Running":
                status = "running"
            elif phase == "Pending":
                status = "pending"
            elif phase == "Succeeded":
                status = "finished"
            elif phase == "Failed":
                status = "failed"
            else:
                status = phase.lower()

            statuses.append({
                "job_name": job_name,
                "status": status,
                "node_name": job["node_name"],
                "namespace": namespace,
            })
            seen_jobs.add(job_name)

        # 2. Get enqueued jobs from Redis
        enqueued_jobs = self._get_enqueued_jobs()
        for node_name, job_list in enqueued_jobs.items():
            for job_info in job_list:
                # Format is "pod_name:namespace"
                parts = job_info.split(":")
                if len(parts) >= 2:
                    pod_name = parts[0]
                    job_namespace = parts[1]

                    # Extract job name from pod name (remove random suffix)
                    # Pod names are like: llama-job-abc123-xyz12
                    job_name = "-".join(pod_name.rsplit("-", 1)[:-1]) if "-" in pod_name else pod_name

                    if job_name not in seen_jobs and job_namespace == namespace:
                        statuses.append({
                            "job_name": job_name,
                            "status": "enqueued",
                            "node_name": node_name,
                            "namespace": job_namespace,
                        })
                        seen_jobs.add(job_name)

        # 3. Get finished/failed jobs from database that aren't already tracked
        try:
            db_jobs = job_repository.get_all_job_results(limit=1000, offset=0)
            for job in db_jobs:
                job_name = job.get("job_name")
                if job_name and job_name not in seen_jobs:
                    db_status = job.get("status", "").lower()

                    if db_status in ["succeeded", "completed"]:
                        status = "finished"
                    elif db_status == "failed":
                        status = "failed"
                    else:
                        status = db_status

                    statuses.append({
                        "job_name": job_name,
                        "status": status,
                        "node_name": job.get("node_name"),
                        "namespace": job.get("namespace", namespace),
                    })
                    seen_jobs.add(job_name)
        except Exception as e:
            logger.error(f"Failed to get job history from database: {e}")

        return statuses


# Global service instance
job_status_service = JobStatusService()
