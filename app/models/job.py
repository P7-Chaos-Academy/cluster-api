"""Data models for API requests and responses."""
from dataclasses import dataclass, field


@dataclass
class JobCreateRequest:
    """Model for job creation request."""

    prompt: str
    n_predict: int = 128
    temperature: float = 0.0
    namespace: str = 'prompts'
    name: str = None
    labels: dict = None
    node_selector: dict = None
    backoff_limit: int = 4

    def __post_init__(self):
        """Validate the request after initialization."""
        # Generate a unique job name if not provided
        if not self.name:
            import uuid
            import time
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            self.name = f"llama-job-{timestamp}-{unique_id}"
        
        self.validate()

    def validate(self):
        """Validate the job creation request."""
        errors = []

        if not isinstance(self.prompt, str) or not self.prompt.strip():
            errors.append("Prompt must be a non-empty string.")
        if not isinstance(self.n_predict, int) or self.n_predict <= 0:
            errors.append("n_predict must be a positive integer.")
        if not isinstance(self.temperature, (int, float)) or not (
            0.0 <= self.temperature <= 1.0
            ):
            errors.append("temperature must be a float between 0.0 and 1.0.")
        if not isinstance(self.namespace, str) or not self.namespace.strip():
            errors.append("namespace must be a non-empty string.")
        if not isinstance(self.name, str) or not self.name.strip():
            errors.append("name must be a non-empty string.")
        if self.backoff_limit < 0:
            errors.append("backoff_limit must be non-negative.")

        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")

@dataclass
class JobResponse:
    """Model for job creation response."""
    status: str
    job_name: str
    namespace: str
    uid: str
    creation_timestamp: str


@dataclass
class JobStatusResponse:
    """Model for job status response."""
    job_name: str
    namespace: str
    active: int
    succeeded: int
    failed: int
    completion_time: str = None
    start_time: str = None
    conditions: list = field(default_factory=list)


@dataclass
class JobListResponse:
    """Model for job list response."""
    namespace: str
    jobs: list
    total: int
