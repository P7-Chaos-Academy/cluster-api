"""Flask application factory."""

from flask import Flask
from flask_restx import Api

from app.config.config import get_config
from app.controllers.job_controller import api as jobs_api
from app.controllers.nodes_controller import api as nodes_api
from app.controllers.node_metadata_controller import api as node_metadata_api
from app.services.job_watcher_service import job_watcher_service


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
        doc="/docs/",  # Swagger UI endpoint
        prefix="/api/v1",
    )

    # Register namespaces
    api.add_namespace(jobs_api, path="/jobs")
    api.add_namespace(nodes_api, path="/nodes")
    api.add_namespace(node_metadata_api, path="/node-metadata")

    # Start job watcher on application startup
    with app.app_context():
        try:
            job_watcher_service.start()
            app.logger.info("Job watcher service started successfully")
        except Exception as e:
            app.logger.error(f"Failed to start job watcher: {e}")

    # Health check endpoint
    @app.route("/")
    @app.route("/health")
    def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": config.API_TITLE,
            "version": config.API_VERSION,
        }

    return app
