"""Nodes controller handling GPIO interactions."""
import logging
from flask import request
from flask_restx import Namespace, Resource, fields

from app.config.config import get_config
from app.services.gpio_service import gpio_service
from app.services.shutdown_service import shutdown_service

logger = logging.getLogger(__name__)
config = get_config()

api = Namespace('nodes', description='GPIO node operations')

node_response_model = api.model('NodeResponse', {
    'status': fields.String(description='Operation status', example='ok'),
    'pin': fields.Integer(description='GPIO pin that was activated', example=17)
})

error_model = api.model('NodeError', {
    'error': fields.String(description='Error message', example='Invalid pin')
})


@api.route('/<int:pin>')
class NodeActivation(Resource):
    """Controller for activating GPIO pins."""

    @api.doc('activate_node', description='Activate a GPIO pin for 0.3 seconds')
    @api.marshal_with(node_response_model)
    @api.response(200, 'GPIO pin activated', node_response_model)
    @api.response(400, 'Invalid request', error_model)
    @api.response(503, 'GPIO unavailable', error_model)
    @api.response(500, 'Internal server error', error_model)
    def post(self, pin: int):
        """Activate the requested GPIO pin."""
        try:
            gpio_service.activate_pin(pin)
            return {'status': 'ok', 'pin': pin}
        except ValueError as err:
            logger.error(f"Invalid GPIO request: {err}")
            api.abort(400, error=str(err))
        except RuntimeError as err:
            logger.error(f"GPIO unavailable: {err}")
            api.abort(503, error=str(err))
        except Exception as err:
            logger.exception(f"Failed to activate GPIO pin {pin}: {err}")
            api.abort(500, error='Failed to activate GPIO pin')

@api.route('/shutdown/<string:host>/<string:address>')
class NodeShutdown(Resource):
    """Controller for shutting down a server via SSH."""

    @api.doc('shutdown_node', description='Send a remote shutdown command over SSH')
    @api.marshal_with(node_response_model)
    @api.response(200, 'Server shutdown initiated', node_response_model)
    @api.response(400, 'Invalid request', error_model)
    @api.response(500, 'Internal server error', error_model)
    def post(self, host: str, address: str):
        """Shutdown the server at the specified host."""
        try:
            shutdown_service.shutdown(host_label=host, address=address)
            return {'status': 'ok', 'pin': None}
        except ValueError as err:
            logger.error("Invalid shutdown request: %s", err)
            api.abort(400, error=str(err))
        except Exception as err:
            logger.exception("Failed to shutdown server at %s: %s", host, err)
            api.abort(500, error='Failed to shutdown server')