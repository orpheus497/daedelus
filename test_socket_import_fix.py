#!/usr/bin/env python3
"""
Test to verify socket import fix in daemon.py

This test verifies that the socket module is properly imported
in the daemon module, fixing the NameError that occurred when
trying to catch socket.timeout exceptions.
"""

import ast
import sys
from pathlib import Path


def check_socket_import():
    """Check if socket is imported in daemon.py"""
    daemon_path = Path("src/daedelus/daemon/daemon.py")

    if not daemon_path.exists():
        print(f"❌ File not found: {daemon_path}")
        return False

    # Parse the file
    with open(daemon_path) as f:
        tree = ast.parse(f.read())

    # Check for socket import
    has_socket_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'socket':
                    has_socket_import = True
                    print(f"✅ Found: import socket")
                    break

    if not has_socket_import:
        print("❌ Missing: import socket")
        return False

    # Check for socket.timeout usage
    code = daemon_path.read_text()
    if 'socket.timeout' in code:
        print("✅ Found usage of socket.timeout (requires socket import)")

    return True


def check_syntax():
    """Check if daemon.py has valid Python syntax"""
    daemon_path = Path("src/daedelus/daemon/daemon.py")

    try:
        with open(daemon_path) as f:
            compile(f.read(), daemon_path, 'exec')
        print("✅ daemon.py has valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in daemon.py: {e}")
        return False


def main():
    print("=" * 60)
    print("Testing Socket Import Fix")
    print("=" * 60)

    syntax_ok = check_syntax()
    import_ok = check_socket_import()

    print("=" * 60)
    if syntax_ok and import_ok:
        print("✅ ALL TESTS PASSED")
        print("The socket import bug has been fixed!")
        return 0
    else:
        print("❌ TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
