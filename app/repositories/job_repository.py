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
                        node_name TEXT,
                        status TEXT NOT NULL,
                        prompt TEXT,
                        result TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        duration_seconds REAL,
                        power_consumed_wh REAL,
                        token_count INTEGER,
                        error_message TEXT,
                        UNIQUE(job_name, namespace)
                    )
                """
                )
                
                # Add new columns if they don't exist (for existing databases)
                try:
                    cursor.execute("ALTER TABLE job_results ADD COLUMN node_name TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                    
                try:
                    cursor.execute("ALTER TABLE job_results ADD COLUMN started_at TIMESTAMP")
                except sqlite3.OperationalError:
                    pass
                    
                try:
                    cursor.execute("ALTER TABLE job_results ADD COLUMN duration_seconds REAL")
                except sqlite3.OperationalError:
                    pass
                    
                try:
                    cursor.execute("ALTER TABLE job_results ADD COLUMN power_consumed_wh REAL")
                except sqlite3.OperationalError:
                    pass
                    
                try:
                    cursor.execute("ALTER TABLE job_results ADD COLUMN token_count INTEGER")
                except sqlite3.OperationalError:
                    pass

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

            logger.info("Database initialized successfully at %s", self.db_path)

        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
            raise

    def save_job_result(
        self,
        job_name: str,
        namespace: str,
        status: str,
        prompt: Optional[str] = None,
        result: Optional[str] = None,
        pod_name: Optional[str] = None,
        node_name: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        power_consumed_wh: Optional[float] = None,
        token_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Save or update a job result.
        
        Uses INSERT OR REPLACE which will:
        - Insert a new row if job doesn't exist
        - Update existing row if job exists (based on UNIQUE constraint on job_name, namespace)
        
        Note: When updating, only provided (non-None) values will overwrite existing data.
        The created_at timestamp is preserved on updates.

        Args:
            job_name: Name of the Kubernetes job
            namespace: Kubernetes namespace
            status: Job status (pending, running, succeeded, failed, etc.)
            prompt: Optional prompt text sent to the job
            result: Optional result/output from the job
            pod_name: Optional pod name
            node_name: Optional name of node where job ran
            started_at: Optional timestamp when job started
            completed_at: Optional timestamp when job completed
            duration_seconds: Optional job duration in seconds
            power_consumed_wh: Optional power consumed in watt-hours
            token_count: Optional number of tokens generated
            error_message: Optional error message if job failed

        Returns:
            bool: True if save was successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if job already exists to decide between INSERT and UPDATE
                cursor.execute(
                    "SELECT id, created_at FROM job_results WHERE job_name = ? AND namespace = ?",
                    (job_name, namespace)
                )
                existing = cursor.fetchone()
                
                if existing:
                    fields = {
                        "status": status,
                        "prompt": prompt,
                        "result": result,
                        "pod_name": pod_name,
                        "node_name": node_name,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "duration_seconds": duration_seconds,
                        "power_consumed_wh": power_consumed_wh,
                        "token_count": token_count,
                        "error_message": error_message
                    }

                    update_parts = []
                    values = []
                    for col, val in fields.items():
                        if val is not None:
                            update_parts.append(f"{col} = ?")
                            values.append(val)

                    # Safety: if nothing to update (shouldn't happen because status is required), skip
                    if update_parts:
                        values.extend([job_name, namespace])
                        cursor.execute(
                            f"""
                            UPDATE job_results
                            SET {', '.join(update_parts)}
                            WHERE job_name = ? AND namespace = ?
                            """,
                            values,
                        )
                    logger.info("Updated job %s with status %s", job_name, status)
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO job_results 
                        (job_name, namespace, pod_name, node_name, status, prompt, result, 
                         started_at, completed_at, duration_seconds, power_consumed_wh, token_count, error_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_name,
                            namespace,
                            pod_name,
                            node_name,
                            status,
                            prompt,
                            result,
                            started_at,
                            completed_at,
                            duration_seconds,
                            power_consumed_wh,
                            token_count,
                            error_message,
                        ),
                    )
                    logger.info("Created job %s with status %s", job_name, status)

            return True

        except sqlite3.OperationalError as e:
            logger.error("Database locked or unavailable: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to save job result: %s", e)
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
                    SELECT id, job_name, namespace, pod_name, node_name, status, 
                           prompt, result, created_at, started_at, completed_at, 
                           duration_seconds, power_consumed_wh, token_count, error_message
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
            logger.error("Error fetching job result: %s", e)
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
                    SELECT id, job_name, namespace, pod_name, node_name, status, 
                           prompt, result, created_at, started_at, completed_at, 
                           duration_seconds, power_consumed_wh, token_count, error_message
                    FROM job_results
                    ORDER BY completed_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error("Error fetching all job results: %s", e)
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
                    SELECT id, job_name, namespace, pod_name, node_name, status, 
                           prompt, result, created_at, started_at, completed_at, 
                           duration_seconds, power_consumed_wh, error_message
                    FROM job_results
                    WHERE status = ?
                    ORDER BY completed_at DESC
                    LIMIT ?
                """,
                    (status, limit),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error("Error fetching jobs by status: %s", e)
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

            logger.info("Deleted result for job %s in namespace %s", job_name, namespace)
            return True

        except Exception as e:
            logger.error("Error deleting job result: %s", e)
            return False

    def clear_all_job_results(self) -> tuple[bool, int]:
        """
        Delete ALL job results from the database.

        Returns:
            tuple: (success: bool, count: int) - Success status and number of records deleted
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get count before deletion
                cursor.execute("SELECT COUNT(*) FROM job_results")
                count = cursor.fetchone()[0]

                # Delete all records
                cursor.execute("DELETE FROM job_results")

                # Reset auto-increment counter
                cursor.execute(
                    'DELETE FROM sqlite_sequence WHERE name="job_results"'
                )

            logger.warning(
                "Cleared all job results from database (%d records deleted)", count
            )
            return True, count

        except Exception as e:
            logger.error("Error clearing all job results: %s", e)
            return False, 0

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
            logger.error("Error getting job count: %s", e)
            return 0

    def get_statistics(self, node_name: str) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary containing statistics about job results
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total count of jobs for this node
                cursor.execute("SELECT COUNT(*) FROM job_results WHERE node_name = ?", (node_name,))
                total = cursor.fetchone()[0]

                # Calculate average time per token using the token_count field
                cursor.execute(
                    """
                    SELECT AVG(duration_seconds / token_count) as avg_seconds_per_token
                    FROM job_results
                    WHERE node_name = ? 
                    AND token_count IS NOT NULL 
                    AND duration_seconds IS NOT NULL
                    AND token_count > 0
                """,
                    (node_name,),
                )
                row = cursor.fetchone()
                avg_seconds_per_token = row[0] if row and row[0] is not None else 0

                return {
                    "total_jobs": total,
                    "avg_seconds_per_token": avg_seconds_per_token,
                }

        except Exception as e:
            logger.error("Error getting statistics: %s", e)
            return {
            "total_jobs": 0,
            "avg_seconds_per_token": 0,
            }


# Global repository instance
job_repository = JobRepository()
