"""Service layer for interacting with Raspberry Pi GPIO pins."""
import logging
import time
from threading import Lock
from typing import Optional, Protocol

try:
    import RPi.GPIO as RPi_GPIO  # type: ignore
except (RuntimeError, ModuleNotFoundError):
    RPi_GPIO = None

try:
    import lgpio  # type: ignore
except ModuleNotFoundError:
    lgpio = None

logger = logging.getLogger(__name__)


class GPIOBackend(Protocol):
    """Protocol describing the operations a GPIO backend must implement."""

    name: str

    def setup_pin(self, pin: int) -> None:
        """Prepare a pin for output operations."""

    def pulse_pin(self, pin: int, pulse_seconds: float) -> None:
        """Drive a pin high for a short duration before returning it low."""


class RPIGPIOBackend:
    """Adapter around the legacy RPi.GPIO library."""

    name = "RPi.GPIO"

    def __init__(self, module) -> None:
        self._gpio = module
        self._initialized = set()
        self._configure()

    def _configure(self) -> None:
        """Configure the GPIO library for BCM numbering."""
        try:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setwarnings(False)
        except RuntimeError as err:
            raise RuntimeError(f"RPi.GPIO initialization failed: {err}") from err

    def setup_pin(self, pin: int) -> None:
        if pin not in self._initialized:
            self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)
            self._initialized.add(pin)

    def pulse_pin(self, pin: int, pulse_seconds: float) -> None:
        self._gpio.output(pin, self._gpio.HIGH)
        time.sleep(pulse_seconds)
        self._gpio.output(pin, self._gpio.LOW)


class LGPIOBackend:
    """Adapter around libgpiod via the lgpio Python bindings."""

    name = "lgpio"

    def __init__(self, module) -> None:
        self._lgpio = module
        try:
            self._chip_handle = self._lgpio.gpiochip_open(0)
        except OSError as err:
            raise RuntimeError(f"Failed to open /dev/gpiochip0: {err}") from err
        self._initialized = set()

    def setup_pin(self, pin: int) -> None:
        if pin in self._initialized:
            return

        result = self._lgpio.gpio_claim_output(self._chip_handle, pin, self._lgpio.LOW)
        if result < 0:
            error_text = getattr(self._lgpio, "error_text", lambda code: str(code))(result)
            raise RuntimeError(f"lgpio failed to claim pin {pin}: {error_text}")

        self._initialized.add(pin)

    def pulse_pin(self, pin: int, pulse_seconds: float) -> None:
        write = self._lgpio.gpio_write
        write(self._chip_handle, pin, self._lgpio.HIGH)
        time.sleep(pulse_seconds)
        write(self._chip_handle, pin, self._lgpio.LOW)


class GPIOService:
    """Service class for GPIO operations."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._backend = self._initialize_backend()

        if not self._backend:
            logger.warning("No GPIO backend could be initialized; GPIO operations are disabled.")
        else:
            logger.info("Using %s backend for GPIO operations.", self._backend.name)

    def _initialize_backend(self) -> Optional[GPIOBackend]:
        """Select the first GPIO backend that can be successfully initialized."""
        backend_initializers = []

        if lgpio:
            backend_initializers.append(self._initialize_lgpio)
        if RPi_GPIO:
            backend_initializers.append(self._initialize_rpi_gpio)

        for initializer in backend_initializers:
            try:
                return initializer()
            except RuntimeError as err:
                logger.warning("%s", err)

        return None

    def _initialize_rpi_gpio(self) -> GPIOBackend:
        return RPIGPIOBackend(RPi_GPIO)

    def _initialize_lgpio(self) -> GPIOBackend:
        return LGPIOBackend(lgpio)

    def activate_pin(self, pin: int, pulse_seconds: float = 0.3) -> None:
        """Activate a GPIO pin for a short pulse."""
        if not isinstance(pin, int):
            raise ValueError("Pin must be an integer.")
        if pin < 0:
            raise ValueError("Pin must be non-negative.")
        if not self._backend:
            raise RuntimeError("GPIO module is not available on this system.")

        with self._lock:
            self._backend.setup_pin(pin)
            self._backend.pulse_pin(pin, pulse_seconds)


# Global service instance
gpio_service = GPIOService()
