"""Configuration module for the Kubernetes Job API."""
import os
import logging


class Config:
    """Base configuration class."""
    
    # Flask settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))
    
    # Kubernetes settings
    DEFAULT_NAMESPACE = os.getenv('DEFAULT_NAMESPACE', 'default')
    
    # Logging settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # API settings
    API_TITLE = 'Kubernetes Job API'
    API_VERSION = '1.0.0'
    API_DESCRIPTION = 'REST API for creating and managing Kubernetes jobs'
    
    @classmethod
    def init_logging(cls):
        """Initialize logging configuration."""
        log_level = getattr(logging, cls.LOG_LEVEL, logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'default')
    return config.get(env, config['default'])