#!/usr/bin/env python3
"""Initialize the SQLite database for job results."""
import os
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database(db_path='/app/data/cluster.db'):
    """Initialize SQLite database schema."""
    db_dir = os.path.dirname(db_path)
    
    try:
        # Ensure directory exists
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Ensured database directory exists: {db_dir}")
        
        # Connect and create schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create main table
        cursor.execute('''
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
        ''')
        
        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_job_completed 
            ON job_results(completed_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_job_status 
            ON job_results(status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_job_name 
            ON job_results(job_name, namespace)
        ''')
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Tables created: {tables}")
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM job_results")
        count = cursor.fetchone()[0]
        logger.info(f"Current row count: {count}")
        
        conn.close()
        logger.info(f"Database initialized successfully at {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


if __name__ == '__main__':
    # Get database path from environment or use default
    db_path = os.getenv('DATABASE_PATH', '/app/data/cluster.db')
    logger.info(f"Initializing database at: {db_path}")
    
    success = init_database(db_path)
    exit(0 if success else 1)
