import sqlite3
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class NodeRepository:
    """Repository for managing cluster node metadata."""
    
    def __init__(self, db_path: str = '/app/data/cluster.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the nodes table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create nodes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL UNIQUE,
                ip_address TEXT NOT NULL,
                gpio_pin INTEGER,
                node_type TEXT DEFAULT 'jetson',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_node_by_name(self, node_name: str) -> Optional[Dict]:
        """Get node information by node name."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM nodes WHERE node_name = ?',
            (node_name,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_nodes(self) -> List[Dict]:
        """Get all nodes."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM nodes ORDER BY node_name')
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def upsert_node(self, node_name: str, ip_address: str, gpio_pin: Optional[int] = None, 
                    node_type: str = 'jetson', description: Optional[str] = None) -> None:
        """Insert or update a node."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO nodes (node_name, ip_address, gpio_pin, node_type, description, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(node_name) DO UPDATE SET
                    ip_address = excluded.ip_address,
                    gpio_pin = excluded.gpio_pin,
                    node_type = excluded.node_type,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
            ''', (node_name, ip_address, gpio_pin, node_type, description))
            
            conn.commit()
            logger.info("Upserted node: %s (%s)", node_name, ip_address)
        except Exception as e:
            logger.error("Failed to upsert node %s: %s", node_name, e)

            conn.rollback()
            raise
        finally:
            conn.close()
    
    def delete_node(self, node_name: str) -> bool:
        """Delete a node by name."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM nodes WHERE node_name = ?', (node_name,))
            conn.commit()
            deleted = cursor.rowcount > 0
            
            if deleted:
                logger.info("Deleted node: %s", node_name)
            else:
                logger.warning("Node not found for deletion: %s", node_name)
            
            return deleted
        except Exception as e:
            logger.error("Failed to delete node %s: %s", node_name, e)
            conn.rollback()
            raise
        finally:
            conn.close()


# Global instance
node_repository = NodeRepository()
