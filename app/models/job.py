"""Data models for API requests and responses."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Union
import re


@dataclass
class JobCreateRequest:
    """Model for job creation request."""
    name: str
    image: str
    command: Optional[Union[str, List[str]]] = None
    namespace: Optional[str] = None
    node_selector: Optional[Dict[str, str]] = None
    backoff_limit: int = 1
    labels: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Validate the request after initialization."""
        self.validate()

    def validate(self):
        """Validate the job creation request."""
        errors = []

        # Validate name
        if not self.name:
            errors.append("Field 'name' is required")
        elif not self._is_valid_k8s_name(self.name):
            errors.append("Invalid job name: must consist of lowercase letters, numbers, and hyphens, and must start and end with alphanumeric characters")

        # Validate image
        if not self.image:
            errors.append("Field 'image' is required")

        # Validate namespace
        if self.namespace and not self._is_valid_k8s_name(self.namespace):
            errors.append("Invalid namespace: must consist of lowercase letters, numbers, and hyphens")

        # Validate backoff_limit
        if not isinstance(self.backoff_limit, int) or self.backoff_limit < 0:
            errors.append("backoffLimit must be a non-negative integer")

        # Validate command
        if self.command is not None:
            if not isinstance(self.command, (str, list)):
                errors.append("command must be a string or array of strings")
            elif isinstance(self.command, list) and not all(isinstance(cmd, str) for cmd in self.command):
                errors.append("command array must contain only strings")

        # Validate labels
        if self.labels:
            if not isinstance(self.labels, dict):
                errors.append("labels must be an object")
            else:
                for key, value in self.labels.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        errors.append("label keys and values must be strings")

        # Validate node_selector
        if self.node_selector:
            if not isinstance(self.node_selector, dict):
                errors.append("nodeSelector must be an object")
            else:
                for key, value in self.node_selector.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        errors.append("nodeSelector keys and values must be strings")

        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")

    @staticmethod
    def _is_valid_k8s_name(name: str) -> bool:
        """Check if name follows Kubernetes naming conventions."""
        if not name or len(name) > 63:
            return False
        return bool(re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name))


@dataclass
class JobResponse:
    """Model for job response."""
    status: str
    job_name: str
    namespace: str
    uid: Optional[str] = None
    creation_timestamp: Optional[str] = None


@dataclass
class JobStatusResponse:
    """Model for job status response."""
    job_name: str
    namespace: str
    active: int = 0
    succeeded: int = 0
    failed: int = 0
    completion_time: Optional[str] = None
    start_time: Optional[str] = None
    conditions: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class JobListResponse:
    """Model for job list response."""
    namespace: str
    jobs: List[Dict] = field(default_factory=list)
    total: int = 0


@dataclass
class ErrorResponse:
    """Model for error response."""
    error: str
    details: Optional[List[str]] = None