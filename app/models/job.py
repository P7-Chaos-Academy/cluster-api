"""Data models for API requests and responses."""
from dataclasses import dataclass, field


@dataclass
class JobCreateRequest:
    """Model for job creation request."""
    prompt: str
    n_predict: int = 128
    temperature: float = 0.0

    def __post_init__(self):
        """Validate the request after initialization."""
        self.validate()

    def validate(self):
        """Validate the job creation request."""
        errors = []

        if not isinstance(self.prompt, str) or not self.prompt.strip():
            errors.append("Prompt must be a non-empty string.")
        if not isinstance(self.n_predict, int) or self.n_predict <= 0:
            errors.append("n_predict must be a positive integer.")
        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 1.0):
            errors.append("temperature must be a float between 0.0 and 1.0.")

        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")