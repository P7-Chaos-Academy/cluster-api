"""Background service to watch Kubernetes jobs and store results in SQLite."""
import logging
import threading
import json
from typing import Optional
from kubernetes import client, watch
from kubernetes.client.rest import ApiException

from app.config.config import get_config
from app.repositories.job_repository import job_repository

logger = logging.getLogger(__name__)


class JobWatcherService:
    """Service to watch Kubernetes jobs and persist results."""

    def __init__(self):
        self.config = get_config()
        self.core_v1 = None
        self.batch_v1 = None
        self.watcher_thread = None
        self.should_stop = False
        self.repository = job_repository

    def _save_job_result(self, job_name: str, namespace: str, 
                        status: str, logs: Optional[str] = None,
                        pod_name: Optional[str] = None,
                        error_message: Optional[str] = None):
        """Save job result using the repository."""
        # Extract prompt and result from logs if available
        prompt = None
        result = None
        if logs:
            try:
                # Parse JSON response from llama.cpp
                log_json = json.loads(logs)
                result = log_json.get('content', logs)
                prompt = log_json.get('prompt', None)
            except json.JSONDecodeError:
                result = logs
        
        # Use repository to save
        self.repository.save_job_result(
            job_name=job_name,
            namespace=namespace,
            status=status,
            prompt=prompt,
            result=result,
            pod_name=pod_name,
            error_message=error_message
        )

    def _get_job_logs(self, job_name: str, namespace: str) -> Optional[str]:
        """Get logs from job's pod."""
        try:
            # Find pod associated with job
            label_selector = f"job-name={job_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )

            if not pods.items:
                return None

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Get pod logs
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace
            )
            
            return logs

        except ApiException as e:
            logger.warning(f"Could not get logs for {job_name}: {e.reason}")
            return None

    def _watch_jobs(self):
        """Watch Kubernetes jobs in the prompts namespace."""
        namespace = self.config.DEFAULT_NAMESPACE
        w = watch.Watch()
        
        logger.info(f"Starting job watcher for namespace: {namespace}")
        
        try:
            for event in w.stream(
                self.batch_v1.list_namespaced_job,
                namespace=namespace,
                timeout_seconds=0  # Infinite watch
            ):
                if self.should_stop:
                    logger.info("Job watcher stopping...")
                    break

                event_type = event['type']
                job = event['object']
                job_name = job.metadata.name
                
                logger.debug(f"Job event: {event_type} - {job_name}")

                # Only care about jobs with our scheduler
                scheduler_name = getattr(job.spec.template.spec, 'scheduler_name', None)
                if scheduler_name != 'llama-scheduler':
                    continue

                # Check if job completed (succeeded or failed)
                status = job.status
                
                if status.succeeded and status.succeeded > 0:
                    logger.info(f"Job {job_name} succeeded, fetching logs...")
                    logs = self._get_job_logs(job_name, namespace)
                    self._save_job_result(
                        job_name=job_name,
                        namespace=namespace,
                        status='succeeded',
                        logs=logs
                    )
                    
                elif status.failed and status.failed > 0:
                    logger.info(f"Job {job_name} failed")
                    logs = self._get_job_logs(job_name, namespace)
                    self._save_job_result(
                        job_name=job_name,
                        namespace=namespace,
                        status='failed',
                        logs=logs,
                        error_message="Job failed"
                    )

        except Exception as e:
            logger.error(f"Job watcher error: {e}")
            if not self.should_stop:
                # Restart watcher after error
                logger.info("Restarting job watcher in 5 seconds...")
                threading.Timer(5.0, self._watch_jobs).start()

    def start(self):
        """Start the background job watcher."""
        if self.watcher_thread and self.watcher_thread.is_alive():
            logger.warning("Job watcher already running")
            return

        # Initialize Kubernetes clients
        from kubernetes import config
        try:
            import os
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                config.load_incluster_config()
            else:
                config.load_kube_config()
            
            self.batch_v1 = client.BatchV1Api()
            self.core_v1 = client.CoreV1Api()
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

        self.should_stop = False
        self.watcher_thread = threading.Thread(
            target=self._watch_jobs,
            daemon=True,
            name="JobWatcher"
        )
        self.watcher_thread.start()
        logger.info("Job watcher started")

    def stop(self):
        """Stop the background job watcher."""
        self.should_stop = True
        if self.watcher_thread:
            self.watcher_thread.join(timeout=5)
        logger.info("Job watcher stopped")


# Global service instance
job_watcher_service = JobWatcherService()