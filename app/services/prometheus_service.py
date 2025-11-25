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
                logger.debug("Found IP %s for node %s in database", ip_address, node_name)
                return ip_address

            logger.warning("Node %s not found in database", node_name)
            return None

        except Exception as e:
            logger.error("Failed to get IP for node %s: %s", node_name, e)
            return None

    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse ISO timestamp to Unix timestamp."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception as e:
            logger.error("Failed to parse timestamp %s: %s", timestamp_str, e)
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
                logger.warning("Invalid time range: %s to %s", start_time, end_time)
                return None

            # Get the IP address for the node
            node_ip = self._get_node_ip(node_name)
            if not node_ip:
                logger.warning("Could not resolve IP for node %s", node_name)
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
                    logger.debug("Query failed: %s - %s", query, e)
                    continue

            if not results:
                logger.warning(
                    "No power data found for %s between %s and %s. "
                    "Tried queries: %s", node_name, start_time, end_time, ', '.join(metric_queries[:2])
                )
                return None

            # Extract average power in watts
            avg_power_watts = float(results[0]['value'][1])

            # Convert to watt-hours (power * time in hours)
            duration_hours = duration_seconds / 3600.0
            power_consumed_wh = avg_power_watts * duration_hours

            logger.info(
                "Power consumption for %s: %.2fW avg over %.1fs = %.4fWh (query: %s)",
                node_name, avg_power_watts, duration_seconds, power_consumed_wh, successful_query
            )

            return power_consumed_wh

        except requests.exceptions.RequestException as e:
            logger.error("Failed to query Prometheus: %s", e)
            return None
        except Exception as e:
            logger.error("Error calculating power consumption: %s", e, exc_info=True)
            return None


# Global service instance
prometheus_service = PrometheusService()
