"""Background service to watch Kubernetes jobs and store results in SQLite."""

import logging
import threading
import json
from typing import Optional
from kubernetes import client, watch
from kubernetes.client.rest import ApiException

from app.config.config import get_config
from app.repositories.job_repository import job_repository
from app.services.prometheus_service import prometheus_service
from app.services.kubernetes_service import kubernetes_service
from app.services.node_service import node_service

logger = logging.getLogger(__name__)


class JobWatcherService:
    """Service to watch Kubernetes jobs and persist results."""

    def __init__(self):
        self.config = get_config()
        self.core_v1 = None
        self.batch_v1 = None
        self.watcher_thread = None
        self.polling_thread = None
        self.should_stop = False
        self.repository = job_repository
        self.kubernetes_service = kubernetes_service
        self.node_service = node_service

    def _parse_curl_output(self, logs: str) -> Optional[str]:
        """Parse curl output to extract JSON response, removing progress lines."""
        if not logs:
            return None

        # Curl progress output uses \r (carriage return) for updating the same line
        # Split by newlines and filter out lines with \r (progress lines)
        lines = logs.split("\n")
        json_lines = []

        for line in lines:
            # Skip lines with carriage returns (curl progress)
            if "\r" in line:
                # Take only the last part after the final \r
                parts = line.split("\r")
                last_part = parts[-1].strip()
                if last_part and last_part.startswith("{"):
                    json_lines.append(last_part)
            elif line.strip().startswith("{"):
                json_lines.append(line.strip())

        # Join all JSON lines
        json_str = "\n".join(json_lines)
        return json_str if json_str else logs

    def _get_pod_info(self, job_name: str, namespace: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Get pod information for a job.
        
        Returns:
            Tuple of (pod_name, node_name, started_at, completed_at)
        """
        try:
            label_selector = f"job-name={job_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            if not pods.items:
                return None, None, None, None

            pod = pods.items[0]
            pod_name = pod.metadata.name
            node_name = pod.spec.node_name
            
            # Get start and completion times from pod status
            started_at = None
            completed_at = None
            
            if pod.status.container_statuses:
                container_status = pod.status.container_statuses[0]
                if container_status.state.terminated:
                    terminated = container_status.state.terminated
                    if terminated.started_at:
                        started_at = terminated.started_at.isoformat()
                    if terminated.finished_at:
                        completed_at = terminated.finished_at.isoformat()
            
            return pod_name, node_name, started_at, completed_at
            
        except ApiException as e:
            logger.warning(f"Could not get pod info for {job_name}: {e.reason}")
            return None, None, None, None

    def _save_job_result(
        self,
        job_name: str,
        namespace: str,
        status: str,
        logs: Optional[str] = None,
        pod_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Save job result using the repository."""
        # Extract prompt and result from logs if available
        prompt = None
        result = None
        if logs:
            try:
                clean_logs = self._parse_curl_output(logs)

                # Parse JSON response from llama.cpp
                log_json = json.loads(clean_logs)
                result = log_json.get("content", "").strip()
                prompt = log_json.get("prompt", None)

                if not result:
                    result = clean_logs

            except json.JSONDecodeError:
                result = self._parse_curl_output(logs) or logs

        # Get pod information (node, timestamps)
        pod_name_fetched, node_name, started_at, completed_at = self._get_pod_info(job_name, namespace)
        
        # Use fetched pod_name if not provided
        if not pod_name:
            pod_name = pod_name_fetched
        
        # Calculate duration and power consumption
        duration_seconds = None
        power_consumed_wh = None
        
        if started_at and completed_at and node_name:
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                duration_seconds = (end_dt - start_dt).total_seconds()
                
                # Query Prometheus for power consumption
                power_consumed_wh = prometheus_service.get_power_consumption(
                    node_name=node_name,
                    start_time=started_at,
                    end_time=completed_at
                )
            except Exception as e:
                logger.error(f"Failed to calculate duration/power for {job_name}: {e}")

        # Use repository to save (token_count not passed, preserves initial value from job creation)
        self.repository.save_job_result(
            job_name=job_name,
            namespace=namespace,
            status=status,
            prompt=prompt,
            result=result,
            pod_name=pod_name,
            node_name=node_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            power_consumed_wh=power_consumed_wh,
            error_message=error_message,
        )

    def _get_job_logs(self, job_name: str, namespace: str) -> Optional[str]:
        """Get logs from job's pod."""
        try:
            # Find pod associated with job
            label_selector = f"job-name={job_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            if not pods.items:
                return None

            pod = pods.items[0]
            pod_name = pod.metadata.name

            # Get pod logs
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name, namespace=namespace
            )

            return logs

        except ApiException as e:
            logger.warning(f"Could not get logs for {job_name}: {e.reason}")
            return None

    def _sync_existing_jobs(self):
        """Sync existing completed jobs that may have been missed.
        
        This method polls Kubernetes for completed jobs and saves any
        that aren't already in the database. It's called:
        1. On startup to catch jobs completed while service was down
        2. Periodically as a backup to the watch mechanism
        """
        namespace = self.config.DEFAULT_NAMESPACE
        
        try:
            logger.debug(f"Checking for completed jobs in namespace: {namespace}")
            
            # List all jobs in the namespace
            jobs = self.batch_v1.list_namespaced_job(namespace=namespace)
            
            synced_count = 0
            for job in jobs.items:
                job_name = job.metadata.name
                
                # Only care about jobs with our scheduler
                scheduler_name = getattr(job.spec.template.spec, "scheduler_name", None)
                if scheduler_name != "llama-scheduler":
                    continue
                
                # Check if already in database
                existing = self.repository.get_job_result(job_name, namespace)
                
                # Check if job is completed
                status = job.status
                
                if status.succeeded and status.succeeded > 0:
                    # If job exists but missing new fields, update it
                    if existing and (
                        existing.get('node_name') is None or 
                        existing.get('started_at') is None or 
                        existing.get('power_consumed_wh') is None
                    ):
                        logger.info(f"Updating existing job with new fields: {job_name}")
                        logs = self._get_job_logs(job_name, namespace)
                        self._save_job_result(
                            job_name=job_name,
                            namespace=namespace,
                            status="succeeded",
                            logs=logs,
                        )
                        synced_count += 1
                    elif not existing:
                        # New job, record it
                        logger.info(f"Found unrecorded completed job: {job_name}")
                        logs = self._get_job_logs(job_name, namespace)
                        self._save_job_result(
                            job_name=job_name,
                            namespace=namespace,
                            status="succeeded",
                            logs=logs,
                        )
                        synced_count += 1
                    
                elif status.failed and status.failed > 0:
                    # If job exists but missing new fields, update it
                    if existing and (
                        existing.get('node_name') is None or 
                        existing.get('started_at') is None
                    ):
                        logger.info(f"Updating existing failed job with new fields: {job_name}")
                        logs = self._get_job_logs(job_name, namespace)
                        self._save_job_result(
                            job_name=job_name,
                            namespace=namespace,
                            status="failed",
                            logs=logs,
                            error_message="Job failed",
                        )
                        synced_count += 1
                    elif not existing:
                        # New job, record it
                        logger.info(f"Found unrecorded failed job: {job_name}")
                        logs = self._get_job_logs(job_name, namespace)
                        self._save_job_result(
                            job_name=job_name,
                            namespace=namespace,
                            status="failed",
                            logs=logs,
                            error_message="Job failed",
                        )
                        synced_count += 1
            
            if synced_count > 0:
                logger.info(f"Synced {synced_count} completed jobs")
            
        except Exception as e:
            logger.error(f"Error syncing existing jobs: {e}", exc_info=True)
    
    def _polling_loop(self):
        """Periodically poll for completed jobs as a backup to the watch mechanism.
        
        This ensures we don't miss jobs if the watch silently fails or times out.
        Runs every 30 seconds to check for any completed jobs not yet in the database.
        """
        import time
        
        logger.info("Starting polling loop for completed jobs")
        
        while not self.should_stop:
            try:
                # Sleep first to avoid immediate poll on startup (sync already ran)
                time.sleep(30)  # Poll every 30 seconds
                
                if not self.should_stop:
                    self._sync_existing_jobs()
                    
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                # Continue polling even if one iteration fails
                if not self.should_stop:
                    time.sleep(5)  # Brief pause before retry
        
        logger.info("Polling loop stopped")

    def _watch_jobs(self):
        """Watch Kubernetes jobs in the prompts namespace."""
        namespace = self.config.DEFAULT_NAMESPACE
        w = watch.Watch()

        logger.info(f"Starting job watcher for namespace: {namespace}")

        try:
            # Use a timeout for the watch stream to force periodic reconnections
            # This prevents silent watch failures and ensures we don't miss events
            for event in w.stream(
                self.batch_v1.list_namespaced_job,
                namespace=namespace,
                timeout_seconds=300,  # Reconnect every 5 minutes
            ):
                if self.should_stop:
                    logger.info("Job watcher stopping...")
                    break

                event_type = event["type"]
                job = event["object"]
                job_name = job.metadata.name
                node_name = self._get_pod_info(job_name, namespace)[1]

                logger.debug(f"Job event: {event_type} - {job_name}")

                # Only care about jobs with our scheduler
                scheduler_name = getattr(job.spec.template.spec, "scheduler_name", None)
                if scheduler_name != "llama-scheduler":
                    continue

                # Check if job completed (succeeded or failed)
                status = job.status

                if status.succeeded and status.succeeded > 0:
                    logger.info(f"Job {job_name} succeeded, fetching logs...")
                    logs = self._get_job_logs(job_name, namespace)
                    self._save_job_result(
                        job_name=job_name,
                        namespace=namespace,
                        status="succeeded",
                        logs=logs,
                    )
                    
                    try:
                        _, node_name, _, _ = self._get_pod_info(job_name, namespace)
                        if node_name is not None and node_name != "None" and node_name != "":
                            node_speed = self.node_service.get_node_speed(node_name)
                            logger.info(f"Node '{node_name}' speed: {node_speed} tokens/second")
                            self.kubernetes_service.node_annotator(node_name, "tokens-per-second", str(node_speed))
                        else:
                            logger.debug(f"Skipping node annotation for {job_name}: node_name is {node_name}")
                    except Exception as e:
                        logger.warning(f"Failed to update node annotation for {job_name}: {e}")

                elif status.failed and status.failed > 0:
                    logger.info(f"Job {job_name} failed")
                    logs = self._get_job_logs(job_name, namespace)
                    self._save_job_result(
                        job_name=job_name,
                        namespace=namespace,
                        status="failed",
                        logs=logs,
                        error_message="Job failed",
                    )

            # If we exit the loop normally (timeout), restart the watcher
            if not self.should_stop:
                logger.info("Watch stream ended normally, reconnecting...")
                self._watch_jobs()

        except Exception as e:
            logger.error(f"Job watcher error: {e}", exc_info=True)
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

            if os.getenv("KUBERNETES_SERVICE_HOST"):
                config.load_incluster_config()
            else:
                config.load_kube_config()

            self.batch_v1 = client.BatchV1Api()
            self.core_v1 = client.CoreV1Api()

        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

        # Sync any jobs that completed while the service was down
        try:
            logger.info("Performing initial sync of completed jobs...")
            self._sync_existing_jobs()
        except Exception as e:
            logger.error(f"Failed to sync existing jobs: {e}")

        self.should_stop = False
        
        # Start the watch-based watcher (fast response when it works)
        self.watcher_thread = threading.Thread(
            target=self._watch_jobs, daemon=True, name="JobWatcher"
        )
        self.watcher_thread.start()
        logger.info("Job watcher (event-based) started")
        
        # Start the polling-based backup (ensures we never miss jobs)
        self.polling_thread = threading.Thread(
            target=self._polling_loop, daemon=True, name="JobPoller"
        )
        self.polling_thread.start()
        logger.info("Job poller (backup) started")

    def stop(self):
        """Stop the background job watcher and poller."""
        self.should_stop = True
        
        if self.watcher_thread:
            self.watcher_thread.join(timeout=5)
            
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
            
        logger.info("Job watcher and poller stopped")


# Global service instance
job_watcher_service = JobWatcherService()
