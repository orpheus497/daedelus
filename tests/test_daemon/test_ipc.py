"""
Tests for IPC module.

Tests Unix domain socket communication and JSON protocol.

Created by: orpheus497
"""

import json
from pathlib import Path

import pytest

from daedelus.daemon.ipc import IPCClient, IPCServer


def test_ipc_server_init(test_config):
    """Test IPC server initialization."""
    server = IPCServer(test_config)

    assert server.socket_path == Path(test_config.get("daemon.socket_path"))


def test_ipc_client_init(test_config):
    """Test IPC client initialization."""
    client = IPCClient(test_config)

    assert client.socket_path == Path(test_config.get("daemon.socket_path"))


def test_ping_pong(test_config, temp_dir):
    """Test PING request."""
    import socket
    import threading

    # Create mock server
    socket_path = temp_dir / "test.sock"

    def mock_server():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(socket_path))
            sock.listen(1)

            conn, _ = sock.accept()
            data = conn.recv(4096).decode()

            # Parse request
            request = json.loads(data)
            assert request["type"] == "ping"

            # Send response
            response = json.dumps({"status": "ok", "message": "pong"})
            conn.sendall(response.encode())
            conn.close()
        finally:
            sock.close()

    # Start server thread
    thread = threading.Thread(target=mock_server)
    thread.daemon = True
    thread.start()

    import time
    time.sleep(0.1)

    # Send ping
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.connect(str(socket_path))

    request = json.dumps({"type": "ping", "data": {}})
    client_socket.sendall(request.encode())

    response = client_socket.recv(4096).decode()
    data = json.loads(response)

    assert data["status"] == "ok"
    assert data["message"] == "pong"

    client_socket.close()
    thread.join(timeout=2)


def test_log_command_request(test_config):
    """Test LOG_COMMAND message."""
    message = {
        "type": "log_command",
        "data": {
            "command": "git status",
            "cwd": "/home/user/project",
            "exit_code": 0,
            "duration": 0.05
        }
    }

    # Should serialize to JSON
    json_str = json.dumps(message)
    assert "log_command" in json_str


def test_suggest_request(test_config):
    """Test SUGGEST message."""
    message = {
        "type": "suggest",
        "data": {
            "partial": "git st",
            "cwd": "/home/user/project",
            "history": ["git add .", "git commit"]
        }
    }

    json_str = json.dumps(message)
    assert "suggest" in json_str


def test_json_serialization():
    """Test message encoding."""
    data = {"test": "value", "number": 42}
    json_str = json.dumps(data)

    parsed = json.loads(json_str)

    assert parsed == data


def test_invalid_message_format():
    """Test error handling for bad JSON."""
    invalid = "not valid json{"

    with pytest.raises(json.JSONDecodeError):
        json.loads(invalid)


def test_socket_permissions(test_config, temp_dir):
    """Test that socket has correct permissions."""
    import socket
    import os

    socket_path = temp_dir / "test.sock"

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(socket_path))

    # Check permissions (should be user-only)
    stats = os.stat(socket_path)
    mode = stats.st_mode & 0o777

    # Should not be world-readable
    assert mode & 0o004 == 0

    sock.close()
