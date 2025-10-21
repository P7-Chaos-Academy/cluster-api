"""Service layer for interacting with Raspberry Pi GPIO pins."""
import logging
import time
from threading import Lock

try:
    import RPi.GPIO as RPi_GPIO  # type: ignore
except (RuntimeError, ModuleNotFoundError):
    RPi_GPIO = None

logger = logging.getLogger(__name__)


class GPIOService:
    """Service class for GPIO operations."""

    def __init__(self):
        self._gpio = RPi_GPIO
        self._lock = Lock()
        self._initialized_pins = set()

        if self._gpio:
            self._configure()
        else:
            logger.warning("RPi.GPIO module not available; GPIO operations are disabled.")

    def _configure(self):
        """Configure the GPIO library."""
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setwarnings(False)

    def activate_pin(self, pin: int, pulse_seconds: float = 0.3) -> None:
        """Activate a GPIO pin for a short pulse."""
        if not isinstance(pin, int):
            raise ValueError("Pin must be an integer.")
        if pin < 0:
            raise ValueError("Pin must be non-negative.")
        if not self._gpio:
            raise RuntimeError("GPIO module is not available on this system.")

        with self._lock:
            if pin not in self._initialized_pins:
                self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)
                self._initialized_pins.add(pin)

            self._gpio.output(pin, self._gpio.HIGH)
            time.sleep(pulse_seconds)
            self._gpio.output(pin, self._gpio.LOW)


# Global service instance
gpio_service = GPIOService()
