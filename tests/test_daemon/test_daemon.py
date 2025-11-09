"""
Tests for daemon module.

Tests daemon lifecycle, event loop, and graceful shutdown.

Created by: orpheus497
"""

import signal
import time
from pathlib import Path

import pytest

from daedelus.daemon.daemon import DaedelusDaemon


def test_daemon_initialization(test_config):
    """Test daemon setup."""
    daemon = DaedelusDaemon(test_config)

    assert daemon.config == test_config
    assert daemon.running is False


def test_daemon_socket_creation(test_config, temp_dir):
    """Test Unix socket setup."""
    daemon = DaedelusDaemon(test_config)

    # Socket should be created during initialization
    socket_path = Path(test_config.get("daemon.socket_path"))
    assert socket_path.parent.exists()


def test_daemon_pid_file(test_config, temp_dir):
    """Test PID file management."""
    daemon = DaedelusDaemon(test_config)
    pid_path = Path(test_config.get("daemon.pid_path"))

    # Create PID file
    daemon._write_pid_file()

    assert pid_path.exists()

    with open(pid_path) as f:
        pid = int(f.read().strip())

    assert pid > 0


@pytest.mark.slow
def test_daemon_start_stop(test_config):
    """Test daemon lifecycle."""
    import threading

    daemon = DaedelusDaemon(test_config)

    # Start in thread
    thread = threading.Thread(target=daemon.start)
    thread.daemon = True
    thread.start()

    # Wait for startup
    time.sleep(0.5)

    assert daemon.running

    # Stop daemon
    daemon.stop()

    # Wait for shutdown
    thread.join(timeout=5)

    assert not daemon.running


def test_signal_handling(test_config):
    """Test SIGTERM/SIGINT handling."""
    import threading

    daemon = DaedelusDaemon(test_config)

    # Start in thread
    thread = threading.Thread(target=daemon.start)
    thread.daemon = True
    thread.start()

    time.sleep(0.5)

    # Send SIGTERM
    daemon._handle_signal(signal.SIGTERM, None)

    thread.join(timeout=5)

    assert not daemon.running


def test_privacy_filter_integration(test_config):
    """Test privacy filtering layer."""
    daemon = DaedelusDaemon(test_config)

    # Command from excluded path
    excluded_path = "/home/user/.ssh"
    result = daemon._should_filter_command("cat id_rsa", excluded_path)

    assert result is True


@pytest.mark.performance
def test_concurrent_request_handling(test_config):
    """Test multi-client support."""
    import threading
    from daedelus.daemon.ipc import IPCClient

    daemon = DaedelusDaemon(test_config)

    # Start daemon
    thread = threading.Thread(target=daemon.start)
    thread.daemon = True
    thread.start()

    time.sleep(0.5)

    # Create multiple clients
    clients = [IPCClient(test_config) for _ in range(5)]

    # Send concurrent requests
    def send_ping(client):
        try:
            client.ping()
        except:
            pass

    threads = []
    for client in clients:
        t = threading.Thread(target=send_ping, args=(client,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=2)

    daemon.stop()
    thread.join(timeout=5)
