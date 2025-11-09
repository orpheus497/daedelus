"""
IPC (Inter-Process Communication) protocol for Daedalus.

Handles communication between the daemon and shell clients via Unix domain sockets.
Uses JSON messages for simplicity and debuggability.

Created by: orpheus497
"""

import json
import logging
import socket
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """IPC message types."""

    # Shell -> Daemon
    SUGGEST = "suggest"           # Request command suggestions
    LOG_COMMAND = "log_command"   # Log executed command
    COMPLETE = "complete"         # Request completion options
    SEARCH = "search"             # Search command history

    # Control messages
    PING = "ping"                 # Health check
    STATUS = "status"             # Get daemon status
    SHUTDOWN = "shutdown"         # Graceful shutdown

    # Responses
    SUCCESS = "success"
    ERROR = "error"


class IPCMessage:
    """
    IPC message wrapper.

    All messages are JSON-encoded with this structure:
    {
        "type": "suggest|log_command|...",
        "data": {...}
    }
    """

    def __init__(self, msg_type: MessageType, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Create IPC message.

        Args:
            msg_type: Message type
            data: Message payload
        """
        self.type = msg_type
        self.data = data or {}

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
        })

    @classmethod
    def from_json(cls, json_str: str) -> "IPCMessage":
        """
        Deserialize message from JSON string.

        Args:
            json_str: JSON string

        Returns:
            IPCMessage instance

        Raises:
            ValueError: If JSON is invalid or type is unknown
        """
        try:
            obj = json.loads(json_str)
            msg_type = MessageType(obj["type"])
            data = obj.get("data", {})
            return cls(msg_type, data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid IPC message: {e}")

    def __repr__(self) -> str:
        """String representation."""
        return f"IPCMessage(type={self.type.value}, data={self.data})"


class IPCServer:
    """
    Unix domain socket server for daemon.

    Handles incoming connections from shell clients and routes
    messages to appropriate handlers.
    """

    def __init__(self, socket_path: str, handler: Any) -> None:
        """
        Initialize IPC server.

        Args:
            socket_path: Path to Unix domain socket
            handler: Object with handle_* methods for each message type
        """
        self.socket_path = socket_path
        self.handler = handler
        self.socket: Optional[socket.socket] = None

    def start(self) -> None:
        """
        Start listening on Unix domain socket.

        Raises:
            OSError: If socket creation fails
        """
        # Remove old socket file if exists
        try:
            import os
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass

        # Create Unix domain socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)
        self.socket.listen(5)

        # Set restrictive permissions (owner only)
        import os
        import stat
        os.chmod(self.socket_path, stat.S_IRUSR | stat.S_IWUSR)

        logger.info(f"IPC server listening on {self.socket_path}")

    def handle_connection(self, conn: socket.socket, addr: Any) -> None:
        """
        Handle a single client connection.

        Args:
            conn: Client socket connection
            addr: Client address (unused for Unix sockets)
        """
        try:
            # Receive message (max 4KB)
            data = conn.recv(4096)
            if not data:
                return

            # Parse message
            try:
                msg = IPCMessage.from_json(data.decode("utf-8"))
                logger.debug(f"Received: {msg.type.value}")
            except ValueError as e:
                error_response = IPCMessage(
                    MessageType.ERROR,
                    {"error": str(e)},
                )
                conn.sendall(error_response.to_json().encode("utf-8"))
                return

            # Route to handler
            response = self._route_message(msg)

            # Send response
            conn.sendall(response.to_json().encode("utf-8"))

        except Exception as e:
            logger.error(f"Error handling connection: {e}", exc_info=True)
            error_response = IPCMessage(
                MessageType.ERROR,
                {"error": f"Internal error: {str(e)}"},
            )
            try:
                conn.sendall(error_response.to_json().encode("utf-8"))
            except:
                pass  # Connection might be closed

        finally:
            conn.close()

    def _route_message(self, msg: IPCMessage) -> IPCMessage:
        """
        Route message to appropriate handler method.

        Args:
            msg: Incoming message

        Returns:
            Response message
        """
        # Map message types to handler methods
        handlers = {
            MessageType.SUGGEST: "handle_suggest",
            MessageType.LOG_COMMAND: "handle_log_command",
            MessageType.COMPLETE: "handle_complete",
            MessageType.SEARCH: "handle_search",
            MessageType.PING: "handle_ping",
            MessageType.STATUS: "handle_status",
            MessageType.SHUTDOWN: "handle_shutdown",
        }

        handler_name = handlers.get(msg.type)
        if not handler_name:
            return IPCMessage(
                MessageType.ERROR,
                {"error": f"Unknown message type: {msg.type.value}"},
            )

        # Call handler method
        try:
            handler_method = getattr(self.handler, handler_name)
            result = handler_method(msg.data)

            return IPCMessage(MessageType.SUCCESS, result)

        except AttributeError:
            return IPCMessage(
                MessageType.ERROR,
                {"error": f"Handler not implemented: {handler_name}"},
            )
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            return IPCMessage(
                MessageType.ERROR,
                {"error": str(e)},
            )

    def stop(self) -> None:
        """Stop IPC server and clean up socket."""
        if self.socket:
            self.socket.close()

        # Remove socket file
        try:
            import os
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass

        logger.info("IPC server stopped")


class IPCClient:
    """
    Unix domain socket client for shell integration.

    Used by shell plugins to communicate with daemon.
    """

    def __init__(self, socket_path: str, timeout: float = 1.0) -> None:
        """
        Initialize IPC client.

        Args:
            socket_path: Path to Unix domain socket
            timeout: Socket timeout in seconds
        """
        self.socket_path = socket_path
        self.timeout = timeout

    def send_message(self, msg: IPCMessage) -> IPCMessage:
        """
        Send message to daemon and get response.

        Args:
            msg: Message to send

        Returns:
            Response message

        Raises:
            ConnectionError: If cannot connect to daemon
            TimeoutError: If request times out
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            # Connect to daemon
            sock.connect(self.socket_path)

            # Send message
            sock.sendall(msg.to_json().encode("utf-8"))

            # Receive response
            data = sock.recv(4096)
            if not data:
                raise ConnectionError("Daemon closed connection")

            # Parse response
            response = IPCMessage.from_json(data.decode("utf-8"))
            return response

        finally:
            sock.close()

    def suggest(
        self,
        partial: str,
        cwd: str,
        history: list[str],
    ) -> list[Dict[str, Any]]:
        """
        Request command suggestions.

        Args:
            partial: Partially typed command
            cwd: Current working directory
            history: Recent command history

        Returns:
            List of suggestions
        """
        msg = IPCMessage(
            MessageType.SUGGEST,
            {
                "partial": partial,
                "cwd": cwd,
                "history": history,
            },
        )

        response = self.send_message(msg)
        if response.type == MessageType.ERROR:
            raise RuntimeError(response.data.get("error", "Unknown error"))

        return response.data.get("suggestions", [])

    def log_command(
        self,
        command: str,
        exit_code: int,
        duration: float,
        cwd: str,
        session_id: str,
    ) -> None:
        """
        Log executed command.

        Args:
            command: Command that was executed
            exit_code: Exit code (0 = success)
            duration: Execution time in seconds
            cwd: Working directory
            session_id: Session identifier
        """
        msg = IPCMessage(
            MessageType.LOG_COMMAND,
            {
                "command": command,
                "exit_code": exit_code,
                "duration": duration,
                "cwd": cwd,
                "session_id": session_id,
            },
        )

        response = self.send_message(msg)
        if response.type == MessageType.ERROR:
            logger.warning(f"Failed to log command: {response.data.get('error')}")

    def ping(self) -> bool:
        """
        Ping daemon to check if alive.

        Returns:
            True if daemon responds, False otherwise
        """
        try:
            msg = IPCMessage(MessageType.PING)
            response = self.send_message(msg)
            return response.type == MessageType.SUCCESS
        except:
            return False

    def status(self) -> Dict[str, Any]:
        """
        Get daemon status.

        Returns:
            Status information dictionary
        """
        msg = IPCMessage(MessageType.STATUS)
        response = self.send_message(msg)

        if response.type == MessageType.ERROR:
            raise RuntimeError(response.data.get("error"))

        return response.data


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test message serialization
    msg = IPCMessage(
        MessageType.SUGGEST,
        {"partial": "git ", "cwd": "/tmp", "history": ["ls", "cd /tmp"]},
    )

    json_str = msg.to_json()
    print(f"Serialized: {json_str}")

    msg2 = IPCMessage.from_json(json_str)
    print(f"Deserialized: {msg2}")

    # Test client (requires daemon to be running)
    try:
        client = IPCClient("/tmp/daedelus_test.sock")
        if client.ping():
            print("Daemon is alive!")
        else:
            print("Daemon not responding")
    except Exception as e:
        print(f"Client error: {e}")
