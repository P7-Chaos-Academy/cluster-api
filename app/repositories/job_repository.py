"""Repository for job results database operations."""

import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from app.config.config import get_config

logger = logging.getLogger(__name__)


class JobRepository:
    """Repository for managing job results in SQLite."""

    def __init__(self):
        self.config = get_config()
        self.db_path = getattr(self.config, "DATABASE_PATH", "/app/data/cluster.db")
        self.db_dir = getattr(self.config, "DATABASE_DIR", "/app/data")
        self._init_database()

    @contextmanager
    def _get_connection(self, timeout: float = 10.0):
        """Context manager for database connections."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=timeout)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_database(self):
        """Initialize SQLite database schema."""
        try:
            # Ensure directory exists
            os.makedirs(self.db_dir, exist_ok=True)
            logger.info(f"Ensured database directory exists: {self.db_dir}")

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create main table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS job_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_name TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        pod_name TEXT,
                        status TEXT NOT NULL,
                        prompt TEXT,
                        result TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT,
                        UNIQUE(job_name, namespace)
                    )
                """
                )

                # Create indexes for faster queries
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_job_completed 
                    ON job_results(completed_at DESC)
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_job_status 
                    ON job_results(status)
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_job_name 
                    ON job_results(job_name, namespace)
                """
                )

            logger.info(f"Database initialized successfully at {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_job_result(
        self,
        job_name: str,
        namespace: str,
        status: str,
        prompt: Optional[str] = None,
        result: Optional[str] = None,
        pod_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Save or update a job result.

        Args:
            job_name: Name of the Kubernetes job
            namespace: Kubernetes namespace
            status: Job status (succeeded, failed, etc.)
            prompt: Optional prompt text sent to the job
            result: Optional result/output from the job
            pod_name: Optional pod name
            error_message: Optional error message if job failed

        Returns:
            bool: True if save was successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO job_results 
                    (job_name, namespace, pod_name, status, prompt, result, 
                     completed_at, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        job_name,
                        namespace,
                        pod_name,
                        status,
                        prompt,
                        result,
                        datetime.now().isoformat(),
                        error_message,
                    ),
                )

            logger.info(f"Saved result for job {job_name} with status {status}")
            return True

        except sqlite3.OperationalError as e:
            logger.error(f"Database locked or unavailable: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to save job result: {e}")
            return False

    def get_job_result(self, job_name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific job result.

        Args:
            job_name: Name of the job
            namespace: Kubernetes namespace

        Returns:
            Dictionary containing job result or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, job_name, namespace, pod_name, status, 
                           prompt, result, created_at, completed_at, error_message
                    FROM job_results
                    WHERE job_name = ? AND namespace = ?
                """,
                    (job_name, namespace),
                )

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Error fetching job result: {e}")
            return None

    def get_all_job_results(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all job results with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of job result dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, job_name, namespace, pod_name, status, 
                           prompt, result, created_at, completed_at, error_message
                    FROM job_results
                    ORDER BY completed_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching all job results: {e}")
            return []

    def get_jobs_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get job results filtered by status.

        Args:
            status: Job status to filter by (succeeded, failed, etc.)
            limit: Maximum number of results to return

        Returns:
            List of job result dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, job_name, namespace, pod_name, status, 
                           prompt, result, created_at, completed_at, error_message
                    FROM job_results
                    WHERE status = ?
                    ORDER BY completed_at DESC
                    LIMIT ?
                """,
                    (status, limit),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error fetching jobs by status: {e}")
            return []

    def delete_job_result(self, job_name: str, namespace: str) -> bool:
        """
        Delete a specific job result.

        Args:
            job_name: Name of the job
            namespace: Kubernetes namespace

        Returns:
            bool: True if deletion was successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    DELETE FROM job_results
                    WHERE job_name = ? AND namespace = ?
                """,
                    (job_name, namespace),
                )

            logger.info(f"Deleted result for job {job_name} in namespace {namespace}")
            return True

        except Exception as e:
            logger.error(f"Error deleting job result: {e}")
            return False

    def get_job_count(self) -> int:
        """
        Get total count of job results in database.

        Returns:
            int: Total number of job results
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM job_results")
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error getting job count: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary containing statistics about job results
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total count
                cursor.execute("SELECT COUNT(*) FROM job_results")
                total = cursor.fetchone()[0]

                # Count by status
                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM job_results
                    GROUP BY status
                """
                )
                status_counts = {
                    row["status"]: row["count"] for row in cursor.fetchall()
                }

                # Most recent job
                cursor.execute(
                    """
                    SELECT completed_at
                    FROM job_results
                    ORDER BY completed_at DESC
                    LIMIT 1
                """
                )
                recent = cursor.fetchone()
                most_recent = recent["completed_at"] if recent else None

                return {
                    "total_jobs": total,
                    "status_counts": status_counts,
                    "most_recent_completion": most_recent,
                }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_jobs": 0,
                "status_counts": {},
                "most_recent_completion": None,
            }


# Global repository instance
job_repository = JobRepository()
