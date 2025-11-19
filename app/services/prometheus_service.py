"""Service for querying Prometheus metrics."""

import logging
import requests
from typing import Optional
from datetime import datetime
from app.config.config import get_config
from app.repositories.node_repository import node_repository

logger = logging.getLogger(__name__)


class PrometheusService:
    """Service for querying Prometheus metrics."""

    def __init__(self):
        self.config = get_config()
        self.prometheus_url = getattr(
            self.config, "PROMETHEUS_URL", "http://prometheus-server.default.svc.cluster.local"
        )
        # Cache for node name to IP mappings
        self._node_ip_cache = {}
        self._k8s_core_v1 = None
    
    def _get_node_ip(self, node_name: str) -> Optional[str]:
        """Get the IP address for a node name from the nodes table."""
        # Check cache first
        if node_name in self._node_ip_cache:
            return self._node_ip_cache[node_name]
        
        try:
            # Query the nodes table
            node_info = node_repository.get_node_by_name(node_name)
            
            if node_info and node_info.get('ip_address'):
                ip_address = node_info['ip_address']
                self._node_ip_cache[node_name] = ip_address
                logger.debug(f"Found IP {ip_address} for node {node_name} in database")
                return ip_address
            
            # Fallback: try to get from Kubernetes API
            logger.info(f"Node {node_name} not in database, querying Kubernetes API")
            
            # Initialize Kubernetes client if needed
            if not self._k8s_core_v1:
                from kubernetes import client, config as k8s_config
                import os
                
                if os.getenv("KUBERNETES_SERVICE_HOST"):
                    k8s_config.load_incluster_config()
                else:
                    k8s_config.load_kube_config()
                
                self._k8s_core_v1 = client.CoreV1Api()
            
            # Get node details from Kubernetes
            node = self._k8s_core_v1.read_node(name=node_name)
            
            # Extract IP address from node addresses
            for address in node.status.addresses:
                if address.type == "InternalIP":
                    ip_address = address.address
                    self._node_ip_cache[node_name] = ip_address
                    
                    # Save to database for future use
                    node_repository.upsert_node(
                        node_name=node_name,
                        ip_address=ip_address,
                        node_type='unknown'
                    )
                    logger.info(f"Added node {node_name} with IP {ip_address} to database")
                    
                    return ip_address
            
            logger.warning(f"No InternalIP found for node {node_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get IP for node {node_name}: {e}")
            return None

    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse ISO timestamp to Unix timestamp."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp_str}: {e}")
            return None

    def get_power_consumption(
        self, 
        node_name: str, 
        start_time: str, 
        end_time: str
    ) -> Optional[float]:
        """
        Query Prometheus for power consumption during a time range.
        
        Args:
            node_name: Name of the node (e.g., 'nano1', 'nano2')
            start_time: ISO format timestamp (e.g., '2025-11-19T08:47:58Z')
            end_time: ISO format timestamp (e.g., '2025-11-19T08:48:17Z')
            
        Returns:
            Power consumed in watt-hours, or None if query fails
        """
        try:
            # Parse timestamps
            start_ts = self._parse_timestamp(start_time)
            end_ts = self._parse_timestamp(end_time)
            
            if not start_ts or not end_ts:
                return None
                
            duration_seconds = end_ts - start_ts
            
            if duration_seconds <= 0:
                logger.warning(f"Invalid time range: {start_time} to {end_time}")
                return None
            
            # Get the IP address for the node
            node_ip = self._get_node_ip(node_name)
            if not node_ip:
                logger.warning(f"Could not resolve IP for node {node_name}")
                return None
            
            # Query Prometheus for average power during the time range
            # The instance label in Prometheus uses IP:port format
            metric_queries = [
                # Try with IP:port (most likely format)
                f'avg_over_time(jetson_pom_5v_in_watts{{instance=~"{node_ip}:.*"}}[{int(duration_seconds)}s])',
                # Try exact IP:9100 (common exporter port)
                f'avg_over_time(jetson_pom_5v_in_watts{{instance="{node_ip}:9100"}}[{int(duration_seconds)}s])',
                # Try just IP
                f'avg_over_time(jetson_pom_5v_in_watts{{instance="{node_ip}"}}[{int(duration_seconds)}s])',
                # Fallback to node name attempts
                f'avg_over_time(jetson_pom_5v_in_watts{{node="{node_name}"}}[{int(duration_seconds)}s])',
                f'avg_over_time(jetson_pom_5v_in_watts{{instance="{node_name}"}}[{int(duration_seconds)}s])',
            ]
            
            results = None
            successful_query = None
            
            for query in metric_queries:
                try:
                    params = {
                        'query': query,
                        'time': end_ts  # Query at end time
                    }
                    
                    response = requests.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params=params,
                        timeout=10
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if data['status'] == 'success':
                        query_results = data.get('data', {}).get('result', [])
                        if query_results:
                            results = query_results
                            successful_query = query
                            break
                except Exception as e:
                    logger.debug(f"Query failed: {query} - {e}")
                    continue
            
            if not results:
                logger.warning(
                    f"No power data found for {node_name} between {start_time} and {end_time}. "
                    f"Tried queries: {', '.join(metric_queries[:2])}"
                )
                return None
                
            # Extract average power in watts
            avg_power_watts = float(results[0]['value'][1])
            
            # Convert to watt-hours (power * time in hours)
            duration_hours = duration_seconds / 3600.0
            power_consumed_wh = avg_power_watts * duration_hours
            
            logger.info(
                f"Power consumption for {node_name}: {avg_power_watts:.2f}W avg "
                f"over {duration_seconds:.1f}s = {power_consumed_wh:.4f}Wh (query: {successful_query})"
            )
            
            return power_consumed_wh
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query Prometheus: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calculating power consumption: {e}", exc_info=True)
            return None


# Global service instance
prometheus_service = PrometheusService()
