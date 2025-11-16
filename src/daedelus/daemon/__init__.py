"""
Daemon module for Daedelus.

Provides the persistent background daemon and IPC communication protocol.

Created by: orpheus497
"""

from daedelus.daemon.daemon import DaedelusDaemon
from daedelus.daemon.ipc import IPCClient, IPCMessage, IPCServer, MessageType

__all__ = [
    "DaedelusDaemon",
    "IPCClient",
    "IPCServer",
    "IPCMessage",
    "MessageType",
]
