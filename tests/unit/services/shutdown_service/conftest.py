"""Fixtures for shutdown_service unit tests."""

import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_config():
    """Create a mock config with shutdown settings."""
    config = MagicMock()
    config.SHUTDOWN_USERNAME = "testuser"
    config.SHUTDOWN_COMMAND = "sudo shutdown now"
    return config


@pytest.fixture
def shutdown_service(mock_config):
    """Create a ShutdownService instance with mocked dependencies.

    Clears the module cache and patches os.path.exists to avoid
    the SSH key validation in __init__.
    """
    sys.modules.pop("app.services.shutdown_service", None)

    with patch("os.path.exists", return_value=True):
        with patch("app.config.config.get_config", return_value=mock_config):
            from app.services.shutdown_service import ShutdownService
            return ShutdownService()


@pytest.fixture
def mock_ssh():
    """Create a mock paramiko SSHClient."""
    ssh = MagicMock()
    return ssh
