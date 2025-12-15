"""Fixtures for GPIO service unit tests"""

from unittest.mock import MagicMock

@pytest.fixture
def mock_rpi_gpio():
    """Mock RPi.GPIO module."""
    mock_gpio = MagicMock()
    mock_gpio.BOARD = 10
    mock_gpio.OUT = 11
    mock_gpio.HIGH = 1
    mock_gpio.LOW = 0
    return mock_gpio