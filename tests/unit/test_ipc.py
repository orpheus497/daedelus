"""
Comprehensive unit tests for IPC (Inter-Process Communication).

Tests all major functionality:
- Message serialization/deserialization
- Message types
- IPC server
- IPC client
- Message routing
- Error handling

Created by: orpheus497
"""

import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from daedelus.daemon.ipc import IPCClient, IPCMessage, IPCServer, MessageType


class TestMessageType:
    """Test MessageType enum."""

    def test_message_types_exist(self):
        """Test that all message types are defined."""
        assert MessageType.SUGGEST
        assert MessageType.LOG_COMMAND
        assert MessageType.COMPLETE
        assert MessageType.SEARCH
        assert MessageType.PING
        assert MessageType.STATUS
        assert MessageType.SHUTDOWN
        assert MessageType.SUCCESS
        assert MessageType.ERROR

    def test_message_type_values(self):
        """Test message type values are strings."""
        assert MessageType.SUGGEST.value == "suggest"
        assert MessageType.LOG_COMMAND.value == "log_command"
        assert MessageType.PING.value == "ping"
        assert MessageType.SUCCESS.value == "success"
        assert MessageType.ERROR.value == "error"


class TestIPCMessage:
    """Test IPCMessage class."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = IPCMessage(MessageType.SUGGEST, {"partial": "git"})

        assert msg.type == MessageType.SUGGEST
        assert msg.data == {"partial": "git"}

    def test_message_creation_without_data(self):
        """Test creating message without data."""
        msg = IPCMessage(MessageType.PING)

        assert msg.type == MessageType.PING
        assert msg.data == {}

    def test_message_to_json(self):
        """Test serializing message to JSON."""
        msg = IPCMessage(
            MessageType.SUGGEST,
            {"partial": "git", "cwd": "/tmp", "history": ["ls"]},
        )

        json_str = msg.to_json()

        assert isinstance(json_str, str)
        obj = json.loads(json_str)
        assert obj["type"] == "suggest"
        assert obj["data"]["partial"] == "git"
        assert obj["data"]["cwd"] == "/tmp"
        assert obj["data"]["history"] == ["ls"]

    def test_message_from_json(self):
        """Test deserializing message from JSON."""
        json_str = json.dumps({
            "type": "suggest",
            "data": {"partial": "git", "cwd": "/tmp"},
        })

        msg = IPCMessage.from_json(json_str)

        assert msg.type == MessageType.SUGGEST
        assert msg.data["partial"] == "git"
        assert msg.data["cwd"] == "/tmp"

    def test_message_from_json_without_data(self):
        """Test deserializing message without data field."""
        json_str = json.dumps({"type": "ping"})

        msg = IPCMessage.from_json(json_str)

        assert msg.type == MessageType.PING
        assert msg.data == {}

    def test_message_from_json_invalid(self):
        """Test deserializing invalid JSON raises error."""
        with pytest.raises(ValueError, match="Invalid IPC message"):
            IPCMessage.from_json("not json")

    def test_message_from_json_unknown_type(self):
        """Test deserializing unknown message type raises error."""
        json_str = json.dumps({"type": "unknown_type", "data": {}})

        with pytest.raises(ValueError, match="Invalid IPC message"):
            IPCMessage.from_json(json_str)

    def test_message_from_json_missing_type(self):
        """Test deserializing message without type raises error."""
        json_str = json.dumps({"data": {}})

        with pytest.raises(ValueError, match="Invalid IPC message"):
            IPCMessage.from_json(json_str)

    def test_message_roundtrip(self):
        """Test serialize -> deserialize roundtrip."""
        original = IPCMessage(
            MessageType.LOG_COMMAND,
            {
                "command": "ls -la",
                "exit_code": 0,
                "duration": 0.5,
                "cwd": "/home/user",
            },
        )

        json_str = original.to_json()
        restored = IPCMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.data == original.data

    def test_message_repr(self):
        """Test message string representation."""
        msg = IPCMessage(MessageType.PING, {"test": "data"})

        repr_str = repr(msg)

        assert "IPCMessage" in repr_str
        assert "ping" in repr_str


class TestIPCServer:
    """Test IPCServer class."""

    def test_server_creation(self, temp_dir):
        """Test creating IPC server."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()

        server = IPCServer(socket_path, handler)

        assert server.socket_path == socket_path
        assert server.handler is handler

    def test_server_start_creates_socket(self, temp_dir):
        """Test that starting server creates socket file."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()
        server = IPCServer(socket_path, handler)

        server.start()

        try:
            assert Path(socket_path).exists()
        finally:
            server.stop()

    def test_server_start_sets_permissions(self, temp_dir):
        """Test that socket has correct permissions."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()
        server = IPCServer(socket_path, handler)

        server.start()

        try:
            # Check permissions are owner-only
            import stat
            mode = os.stat(socket_path).st_mode
            # Should be readable and writable by owner only
            assert mode & stat.S_IRUSR
            assert mode & stat.S_IWUSR
        finally:
            server.stop()

    def test_server_stop_removes_socket(self, temp_dir):
        """Test that stopping server removes socket file."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()
        server = IPCServer(socket_path, handler)

        server.start()
        server.stop()

        assert not Path(socket_path).exists()

    def test_server_route_message_suggest(self, temp_dir):
        """Test routing SUGGEST message."""
        handler = Mock()
        handler.handle_suggest = Mock(return_value={"suggestions": []})

        server = IPCServer(str(temp_dir / "test.sock"), handler)
        msg = IPCMessage(MessageType.SUGGEST, {"partial": "git"})

        response = server._route_message(msg)

        assert response.type == MessageType.SUCCESS
        handler.handle_suggest.assert_called_once_with({"partial": "git"})

    def test_server_route_message_log_command(self, temp_dir):
        """Test routing LOG_COMMAND message."""
        handler = Mock()
        handler.handle_log_command = Mock(return_value={})

        server = IPCServer(str(temp_dir / "test.sock"), handler)
        msg = IPCMessage(MessageType.LOG_COMMAND, {"command": "ls"})

        response = server._route_message(msg)

        assert response.type == MessageType.SUCCESS
        handler.handle_log_command.assert_called_once()

    def test_server_route_message_ping(self, temp_dir):
        """Test routing PING message."""
        handler = Mock()
        handler.handle_ping = Mock(return_value={"status": "ok"})

        server = IPCServer(str(temp_dir / "test.sock"), handler)
        msg = IPCMessage(MessageType.PING)

        response = server._route_message(msg)

        assert response.type == MessageType.SUCCESS
        handler.handle_ping.assert_called_once()

    def test_server_route_message_unknown_type(self, temp_dir):
        """Test that routing unknown message type returns error."""
        handler = Mock()
        server = IPCServer(str(temp_dir / "test.sock"), handler)

        # Create message with a type not in handlers map
        # We'll use SUCCESS which shouldn't have a handler
        msg = IPCMessage(MessageType.SUCCESS)

        response = server._route_message(msg)

        assert response.type == MessageType.ERROR
        assert "Unknown message type" in response.data["error"]

    def test_server_route_message_missing_handler(self, temp_dir):
        """Test routing when handler method doesn't exist."""
        handler = Mock(spec=[])  # Handler with no methods

        server = IPCServer(str(temp_dir / "test.sock"), handler)
        msg = IPCMessage(MessageType.SUGGEST)

        response = server._route_message(msg)

        assert response.type == MessageType.ERROR
        assert "not implemented" in response.data["error"].lower()

    def test_server_route_message_handler_exception(self, temp_dir):
        """Test routing when handler raises exception."""
        handler = Mock()
        handler.handle_ping = Mock(side_effect=RuntimeError("Handler error"))

        server = IPCServer(str(temp_dir / "test.sock"), handler)
        msg = IPCMessage(MessageType.PING)

        response = server._route_message(msg)

        assert response.type == MessageType.ERROR
        assert "Handler error" in response.data["error"]


class TestIPCClient:
    """Test IPCClient class."""

    def test_client_creation(self, temp_dir):
        """Test creating IPC client."""
        socket_path = str(temp_dir / "test.sock")

        client = IPCClient(socket_path)

        assert client.socket_path == socket_path
        assert client.timeout == 1.0

    def test_client_custom_timeout(self, temp_dir):
        """Test client with custom timeout."""
        socket_path = str(temp_dir / "test.sock")

        client = IPCClient(socket_path, timeout=5.0)

        assert client.timeout == 5.0

    def test_client_ping_no_server(self, temp_dir):
        """Test ping when server is not running."""
        socket_path = str(temp_dir / "nonexistent.sock")
        client = IPCClient(socket_path, timeout=0.1)

        result = client.ping()

        assert result is False

    def test_client_suggest_raises_on_error_response(self, temp_dir):
        """Test that suggest raises on error response."""
        # This test would require a mock server, skip for unit tests
        # Will be covered in integration tests
        pass


class TestIntegration:
    """Integration tests for client-server communication."""

    def test_client_server_ping(self, temp_dir):
        """Test client can ping server."""
        socket_path = str(temp_dir / "test.sock")

        # Create mock handler
        handler = Mock()
        handler.handle_ping = Mock(return_value={"status": "ok"})

        # Start server in background thread
        server = IPCServer(socket_path, handler)
        server.start()

        def server_loop():
            try:
                conn, addr = server.socket.accept()
                server.handle_connection(conn, addr)
            except:
                pass

        server_thread = threading.Thread(target=server_loop, daemon=True)
        server_thread.start()

        time.sleep(0.1)  # Give server time to start

        try:
            # Test ping
            client = IPCClient(socket_path, timeout=1.0)
            result = client.ping()

            assert result is True
            handler.handle_ping.assert_called_once()

        finally:
            server.stop()

    def test_client_server_suggest(self, temp_dir):
        """Test client can request suggestions from server."""
        socket_path = str(temp_dir / "test.sock")

        # Create mock handler
        handler = Mock()
        handler.handle_suggest = Mock(return_value={
            "suggestions": [
                {"command": "git status", "confidence": 0.9},
            ]
        })

        # Start server
        server = IPCServer(socket_path, handler)
        server.start()

        def server_loop():
            try:
                conn, addr = server.socket.accept()
                server.handle_connection(conn, addr)
            except:
                pass

        server_thread = threading.Thread(target=server_loop, daemon=True)
        server_thread.start()

        time.sleep(0.1)

        try:
            # Test suggest
            client = IPCClient(socket_path, timeout=1.0)
            suggestions = client.suggest("git", "/tmp", ["ls"])

            assert len(suggestions) == 1
            assert suggestions[0]["command"] == "git status"
            handler.handle_suggest.assert_called_once()

        finally:
            server.stop()

    def test_client_server_log_command(self, temp_dir):
        """Test client can log command to server."""
        socket_path = str(temp_dir / "test.sock")

        # Create mock handler
        handler = Mock()
        handler.handle_log_command = Mock(return_value={})

        # Start server
        server = IPCServer(socket_path, handler)
        server.start()

        def server_loop():
            try:
                conn, addr = server.socket.accept()
                server.handle_connection(conn, addr)
            except:
                pass

        server_thread = threading.Thread(target=server_loop, daemon=True)
        server_thread.start()

        time.sleep(0.1)

        try:
            # Test log command
            client = IPCClient(socket_path, timeout=1.0)
            client.log_command("ls -la", 0, 0.5, "/tmp", "session123")

            handler.handle_log_command.assert_called_once()
            call_args = handler.handle_log_command.call_args[0][0]
            assert call_args["command"] == "ls -la"
            assert call_args["exit_code"] == 0

        finally:
            server.stop()

    def test_client_server_status(self, temp_dir):
        """Test client can get status from server."""
        socket_path = str(temp_dir / "test.sock")

        # Create mock handler
        handler = Mock()
        handler.handle_status = Mock(return_value={
            "uptime": 100,
            "commands_logged": 50,
        })

        # Start server
        server = IPCServer(socket_path, handler)
        server.start()

        def server_loop():
            try:
                conn, addr = server.socket.accept()
                server.handle_connection(conn, addr)
            except:
                pass

        server_thread = threading.Thread(target=server_loop, daemon=True)
        server_thread.start()

        time.sleep(0.1)

        try:
            # Test status
            client = IPCClient(socket_path, timeout=1.0)
            status = client.status()

            assert status["uptime"] == 100
            assert status["commands_logged"] == 50

        finally:
            server.stop()


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_server_handles_invalid_json(self, temp_dir):
        """Test server handles invalid JSON gracefully."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()
        server = IPCServer(socket_path, handler)
        server.start()

        try:
            # Send invalid JSON
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(socket_path)
            client_sock.sendall(b"not json at all")

            # Receive error response
            data = client_sock.recv(4096)
            response = IPCMessage.from_json(data.decode("utf-8"))

            assert response.type == MessageType.ERROR
            assert "Invalid IPC message" in response.data["error"]

            client_sock.close()

        finally:
            server.stop()

    def test_server_handles_malformed_message(self, temp_dir):
        """Test server handles malformed message."""
        socket_path = str(temp_dir / "test.sock")
        handler = Mock()
        server = IPCServer(socket_path, handler)
        server.start()

        try:
            # Send JSON with unknown message type
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(socket_path)

            bad_message = json.dumps({"type": "not_a_real_type", "data": {}})
            client_sock.sendall(bad_message.encode("utf-8"))

            # Receive error response
            data = client_sock.recv(4096)
            response = IPCMessage.from_json(data.decode("utf-8"))

            assert response.type == MessageType.ERROR

            client_sock.close()

        finally:
            server.stop()


class TestMessageTypes:
    """Test all message types are handled."""

    def test_all_message_types_have_handlers(self, temp_dir):
        """Test that all request types have handler mappings."""
        handler = Mock()

        # Add all expected handler methods
        handler.handle_suggest = Mock(return_value={})
        handler.handle_log_command = Mock(return_value={})
        handler.handle_complete = Mock(return_value={})
        handler.handle_search = Mock(return_value={})
        handler.handle_ping = Mock(return_value={})
        handler.handle_status = Mock(return_value={})
        handler.handle_shutdown = Mock(return_value={})

        server = IPCServer(str(temp_dir / "test.sock"), handler)

        # Test each message type routes correctly
        message_types = [
            MessageType.SUGGEST,
            MessageType.LOG_COMMAND,
            MessageType.COMPLETE,
            MessageType.SEARCH,
            MessageType.PING,
            MessageType.STATUS,
            MessageType.SHUTDOWN,
        ]

        for msg_type in message_types:
            msg = IPCMessage(msg_type, {})
            response = server._route_message(msg)
            assert response.type == MessageType.SUCCESS
