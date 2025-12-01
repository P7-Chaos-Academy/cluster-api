import logging
from app.repositories.job_repository import job_repository


logger = logging.getLogger(__name__)

class NodeService:
    """Service class for managing cluster nodes."""

    def __init__(self):
        """Initialize the Node service."""
        self.job_repository = job_repository
        self.node_repository = node_repository

    def get_node_speed(self, node_name: str) -> float:
        """Retrieve the speed of the specified node."""
        node_speed = self.job_repository.get_node_speed(node_name)

        # Chreck if the node exists before declaring it not found
        if node_speed is None:
            node = self.node_repository.get_node_by_name(node_name)
            if node is None:
                raise ValueError(f"Node '{node_name}' not found.")
            
            return 0.0 # Default speed for shceduler to prioritize populating this node
            

        return node_speed
    
    def get_all_node_speeds(self) -> dict:
        """
        Retrieve speeds for all nodes.
        """

        node_speeds = self.job_repository.get_all_node_speeds()
        
        all_nodes = self.node_repository.get_all_nodes()
        
        # Similarly assigning 0.0 for nodes without job history
        result = {}
        for node in all_nodes:
            node_name = node['node_name']
            if node_name in node_speeds:
                result[node_name] = node_speeds[node_name]
            else:
                result[node_name] = 0.0
        
        return result
    

node_service = NodeService()