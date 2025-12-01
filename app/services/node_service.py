import logging
from app.repositories.job_repository import job_repository


logger = logging.getLogger(__name__)

class NodeService:
    """Service class for managing cluster nodes."""

    def __init__(self):
        """Initialize the Node service."""
        self.job_repository = job_repository

    def get_node_speed(self, node_name: str) -> float:
        """Retrieve the speed of the specified node."""
        node_speed = self.job_repository.get_node_speed(node_name)
        if node_speed is None:
            raise ValueError(f"Node '{node_name}' not found")

        return node_speed
    

node_service = NodeService()