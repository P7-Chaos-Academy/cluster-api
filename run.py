#!/usr/bin/env python3
"""Main entry point for the Kubernetes Job API."""
import logging

from app.app import create_app
from app.config.config import get_config

logger = logging.getLogger(__name__)


def main():
    """Run the Flask application."""
    # Create the Flask app
    app = create_app()
    config = get_config()
    
    # Log startup information
    logger.info(f"Starting {config.API_TITLE} v{config.API_VERSION}")
    logger.info(f"Server will run on {config.HOST}:{config.PORT}")
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"Swagger documentation available at: http://{config.HOST}:{config.PORT}/docs/")
    
    # Run the application
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )


if __name__ == '__main__':
    main()