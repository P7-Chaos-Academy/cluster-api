"""Service responsible for issuing remote shutdown commands over SSH."""
import logging
import os
import paramiko

from app.config.config import get_config

logger = logging.getLogger(__name__)


class ShutdownService:
    """Provide SSH-based shutdown orchestration for remote nodes."""

    def __init__(self) -> None:
        self._config = get_config()
        self._ssh_key_path = os.getenv("SSH_KEY_PATH", "/root/.ssh/id_ed25519")

        # Validate SSH key existence on service init
        if not os.path.exists(self._ssh_key_path):
            raise FileNotFoundError(
                f"SSH key not found at {self._ssh_key_path}. "
                f"Ensure it is mounted via Kubernetes secret 'ssh-key-secret'."
            )

    def shutdown(self, host_label: str, address: str) -> None:
        """Dispatch a shutdown command to a remote node over SSH."""
        if not address:
            raise ValueError("A valid address or hostname is required for shutdown.")

        user = getattr(self._config, "SHUTDOWN_USERNAME", None)
        if not user:
            raise ValueError("Missing SHUTDOWN_USERNAME in configuration.")

        command = getattr(self._config, "SHUTDOWN_COMMAND", "sudo shutdown now")

        logger.info("Initiating remote shutdown for %s (%s)...", host_label, address)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=address,
                username=user,
                key_filename=self._ssh_key_path,
                timeout=10,
            )
            ssh.exec_command(command)
            logger.info(
                "Shutdown command sent to %s@%s using key %s",
                user, address, self._ssh_key_path,
            )
        except Exception as err:
            logger.error("Failed to shutdown %s (%s): %s", host_label, address, err, exc_info=True)
            raise
        finally:
            try:
                ssh.close()
            except Exception:
                logger.debug("Failed to close SSH client for %s", host_label, exc_info=True)


shutdown_service = ShutdownService()
