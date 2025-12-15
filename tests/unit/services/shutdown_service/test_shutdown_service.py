"""Unit tests for ShutdownService."""

import sys
import pytest
from unittest.mock import MagicMock, patch


class TestShutdownServiceInit:
    """Tests for ShutdownService.__init__."""

    def test_init_success_with_existing_ssh_key(self):
        """Should initialize successfully when SSH key exists."""
        sys.modules.pop("app.services.shutdown_service", None)

        with patch("os.path.exists", return_value=True):
            with patch("app.config.config.get_config") as mock_get_config:
                mock_get_config.return_value = MagicMock()

                from app.services.shutdown_service import ShutdownService

                service = ShutdownService()

                assert service._ssh_key_path == "/root/.ssh/id_ed25519"

    def test_init_uses_custom_ssh_key_path_from_env(self):
        """Should use SSH_KEY_PATH from environment variable."""
        sys.modules.pop("app.services.shutdown_service", None)

        with patch.dict("os.environ", {"SSH_KEY_PATH": "/custom/path/key"}):
            with patch("os.path.exists", return_value=True):
                with patch("app.config.config.get_config") as mock_get_config:
                    mock_get_config.return_value = MagicMock()

                    from app.services.shutdown_service import ShutdownService

                    service = ShutdownService()

                    assert service._ssh_key_path == "/custom/path/key"

    def test_init_raises_when_ssh_key_missing(self):
        """Should raise FileNotFoundError when SSH key does not exist."""
        sys.modules.pop("app.services.shutdown_service", None)

        with patch("os.path.exists", return_value=False):
            with patch("app.config.config.get_config") as mock_get_config:
                mock_get_config.return_value = MagicMock()

                with pytest.raises(FileNotFoundError) as exc_info:
                    import importlib
                    import app.services.shutdown_service as mod

                    importlib.reload(mod)

                assert "SSH key not found" in str(exc_info.value)
                assert "ssh-key-secret" in str(exc_info.value)


class TestShutdownServiceShutdown:
    """Tests for ShutdownService.shutdown method."""

    def test_shutdown_raises_when_address_is_empty(self, shutdown_service):
        """Should raise ValueError when address is empty."""
        with pytest.raises(ValueError) as exc_info:
            shutdown_service.shutdown("node-1", "")

        assert "valid address" in str(exc_info.value)

    def test_shutdown_raises_when_address_is_none(self, shutdown_service):
        """Should raise ValueError when address is None."""
        with pytest.raises(ValueError) as exc_info:
            shutdown_service.shutdown("node-1", None)

        assert "valid address" in str(exc_info.value)

    def test_shutdown_raises_when_username_not_configured(self, shutdown_service):
        """Should raise ValueError when SHUTDOWN_USERNAME is not set."""
        shutdown_service._config.SHUTDOWN_USERNAME = None

        with pytest.raises(ValueError) as exc_info:
            shutdown_service.shutdown("node-1", "192.168.1.100")

        assert "SHUTDOWN_USERNAME" in str(exc_info.value)

    def test_shutdown_connects_with_correct_parameters(self, shutdown_service, mock_ssh):
        """Should connect to SSH with correct hostname, username, and key."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.connect.assert_called_once_with(
                hostname="192.168.1.100",
                username="testuser",
                key_filename="/root/.ssh/id_ed25519",
                timeout=10,
            )

    def test_shutdown_executes_default_command(self, shutdown_service, mock_ssh):
        """Should execute the default shutdown command."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.exec_command.assert_called_once_with("sudo shutdown now")

    def test_shutdown_executes_custom_command(self, shutdown_service, mock_ssh):
        """Should execute custom shutdown command from config."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            shutdown_service._config.SHUTDOWN_COMMAND = "systemctl poweroff"

            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.exec_command.assert_called_once_with("systemctl poweroff")

    def test_shutdown_sets_auto_add_policy(self, shutdown_service, mock_ssh):
        """Should set AutoAddPolicy for host key verification."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.set_missing_host_key_policy.assert_called_once()

    def test_shutdown_closes_ssh_connection(self, shutdown_service, mock_ssh):
        """Should close SSH connection after command execution."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.close.assert_called_once()

    def test_shutdown_closes_connection_on_connect_failure(self, shutdown_service, mock_ssh):
        """Should close SSH connection even when connect fails."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            mock_ssh.connect.side_effect = Exception("Connection refused")

            with pytest.raises(Exception) as exc_info:
                shutdown_service.shutdown("node-1", "192.168.1.100")

            assert "Connection refused" in str(exc_info.value)
            mock_ssh.close.assert_called_once()

    def test_shutdown_closes_connection_on_exec_failure(self, shutdown_service, mock_ssh):
        """Should close SSH connection even when exec_command fails."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            mock_ssh.exec_command.side_effect = Exception("Command failed")

            with pytest.raises(Exception) as exc_info:
                shutdown_service.shutdown("node-1", "192.168.1.100")

            assert "Command failed" in str(exc_info.value)
            mock_ssh.close.assert_called_once()

    def test_shutdown_handles_close_failure_gracefully(self, shutdown_service, mock_ssh):
        """Should not raise when close() fails."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            mock_ssh.close.side_effect = Exception("Close failed")

            # Should not raise despite close() failure
            shutdown_service.shutdown("node-1", "192.168.1.100")

            mock_ssh.close.assert_called_once()

    def test_shutdown_propagates_ssh_exception(self, shutdown_service, mock_ssh):
        """Should propagate SSH exceptions to caller."""
        with patch("paramiko.SSHClient", return_value=mock_ssh):
            mock_ssh.connect.side_effect = Exception("Authentication failed")

            with pytest.raises(Exception) as exc_info:
                shutdown_service.shutdown("node-1", "192.168.1.100")

            assert "Authentication failed" in str(exc_info.value)
