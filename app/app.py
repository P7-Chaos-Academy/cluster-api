"""Flask application factory."""
from flask import Flask
from flask_restx import Api

from app.config.config import get_config
from app.controllers.job_controller import api as jobs_api


def create_app():
    """Create and configure the Flask application."""
    # Get configuration
    config = get_config()
    
    # Initialize logging
    config.init_logging()
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Create API with Swagger documentation
    api = Api(
        app,
        title=config.API_TITLE,
        version=config.API_VERSION,
        description=config.API_DESCRIPTION,
        doc='/docs/',  # Swagger UI endpoint
        prefix='/api/v1'
    )
    
    # Register namespaces
    api.add_namespace(jobs_api, path='/jobs')
    
    # Health check endpoint
    @app.route('/')
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": config.API_TITLE,
            "version": config.API_VERSION
        }
    
    return app