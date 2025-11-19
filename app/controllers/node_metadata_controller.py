"""Controller for node metadata management endpoints."""

from flask import request
from flask_restx import Namespace, Resource, fields
import logging

from app.repositories.node_repository import node_repository

logger = logging.getLogger(__name__)

# Create namespace
api = Namespace('node-metadata', description='Node metadata CRUD operations')

# API Models
node_model = api.model('NodeMetadata', {
    'id': fields.Integer(readonly=True, description='Node ID'),
    'node_name': fields.String(required=True, description='Node name (unique)', example='nano1'),
    'ip_address': fields.String(required=True, description='Node IP address', example='172.25.26.250'),
    'gpio_pin': fields.Integer(description='GPIO pin number for power control', example=17),
    'node_type': fields.String(description='Type of node', example='jetson-nano'),
    'description': fields.String(description='Human-readable description', example='Jetson Nano 1'),
    'created_at': fields.String(readonly=True, description='Creation timestamp'),
    'updated_at': fields.String(readonly=True, description='Last update timestamp')
})

node_input_model = api.model('NodeMetadataInput', {
    'node_name': fields.String(required=True, description='Node name (unique)', example='nano1'),
    'ip_address': fields.String(required=True, description='Node IP address', example='172.25.26.250'),
    'gpio_pin': fields.Integer(description='GPIO pin number for power control', example=17),
    'node_type': fields.String(description='Type of node', example='jetson-nano'),
    'description': fields.String(description='Human-readable description', example='Jetson Nano 1')
})


@api.route('/')
class NodeMetadataList(Resource):
    """Operations on node metadata collection."""
    
    @api.doc('list_node_metadata')
    @api.marshal_list_with(node_model)
    def get(self):
        """List all nodes metadata."""
        try:
            nodes = node_repository.get_all_nodes()
            return nodes, 200
        except Exception as e:
            logger.error("Failed to get nodes: %s", e)
            api.abort(500, f"Failed to retrieve nodes: {str(e)}")
    
    @api.doc('create_node_metadata')
    @api.expect(node_input_model)
    @api.marshal_with(node_model, code=201)
    def post(self):
        """Create a new node metadata entry."""
        try:
            data = request.json
            
            # Validate required fields
            if not data.get('node_name'):
                api.abort(400, "node_name is required")
            if not data.get('ip_address'):
                api.abort(400, "ip_address is required")
            
            # Check if node already exists
            existing = node_repository.get_node_by_name(data['node_name'])
            if existing:
                api.abort(409, f"Node '{data['node_name']}' already exists")
            
            # Create node
            node_repository.upsert_node(
                node_name=data['node_name'],
                ip_address=data['ip_address'],
                gpio_pin=data.get('gpio_pin'),
                node_type=data.get('node_type', 'jetson'),
                description=data.get('description')
            )
            
            # Return created node
            node = node_repository.get_node_by_name(data['node_name'])
            return node, 201
            
        except Exception as e:
            logger.error("Failed to create node: %s", e)
            api.abort(500, f"Failed to create node: {str(e)}")


@api.route('/<string:node_name>')
@api.param('node_name', 'The node name')
class NodeMetadata(Resource):
    """Operations on individual node metadata."""
    
    @api.doc('get_node_metadata')
    @api.marshal_with(node_model)
    def get(self, node_name):
        """Get node metadata by name."""
        try:
            node = node_repository.get_node_by_name(node_name)
            if not node:
                api.abort(404, f"Node '{node_name}' not found")
            return node, 200
        except Exception as e:
            logger.error("Failed to get node %s: %s", node_name, e)
            api.abort(500, f"Failed to retrieve node: {str(e)}")
    
    @api.doc('update_node_metadata')
    @api.expect(node_input_model)
    @api.marshal_with(node_model)
    def put(self, node_name):
        """Update node metadata."""
        try:
            data = request.json
            
            # Check if node exists
            existing = node_repository.get_node_by_name(node_name)
            if not existing:
                api.abort(404, f"Node '{node_name}' not found")
            
            # Update node (node_name from URL, other fields from body)
            node_repository.upsert_node(
                node_name=node_name,
                ip_address=data.get('ip_address', existing['ip_address']),
                gpio_pin=data.get('gpio_pin', existing.get('gpio_pin')),
                node_type=data.get('node_type', existing.get('node_type', 'jetson')),
                description=data.get('description', existing.get('description'))
            )
            
            # Return updated node
            node = node_repository.get_node_by_name(node_name)
            return node, 200
            
        except Exception as e:
            logger.error("Failed to update node %s: %s", node_name, e)
            api.abort(500, f"Failed to update node: {str(e)}")
    
    @api.doc('delete_node_metadata')
    @api.response(204, 'Node deleted')
    def delete(self, node_name):
        """Delete node metadata."""
        try:
            # Check if node exists
            existing = node_repository.get_node_by_name(node_name)
            if not existing:
                api.abort(404, f"Node '{node_name}' not found")
            
            # Delete node
            success = node_repository.delete_node(node_name)
            if success:
                return '', 204
            else:
                api.abort(500, "Failed to delete node")
                
        except Exception as e:
            logger.error("Failed to delete node %s: %s", node_name, e)
            api.abort(500, f"Failed to delete node: {str(e)}")
