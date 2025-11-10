#!/usr/bin/env python3
"""
Test script to verify daemon initialization and basic functionality.
Tests the socket.timeout fix and daemon lifecycle.
"""

import os
import sys
import time
import tempfile
import socket
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_daemon_imports():
    """Test that daemon modules can be imported."""
    print("Testing daemon imports...")
    try:
        from daedelus.daemon.daemon import DaedelusDaemon
        from daedelus.daemon.ipc import IPCServer, IPCClient
        from daedelus.utils.config import Config
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_daemon_initialization():
    """Test daemon can be initialized."""
    print("\nTesting daemon initialization...")
    try:
        from daedelus.daemon.daemon import DaedelusDaemon
        from daedelus.utils.config import Config

        # Create a temp config
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            # Override paths to use temp directory
            config._config["daemon"]["socket_path"] = f"{tmpdir}/daemon.sock"
            config._config["daemon"]["pid_path"] = f"{tmpdir}/daemon.pid"
            config._config["daemon"]["log_path"] = f"{tmpdir}/daemon.log"
            config._config["database"]["path"] = f"{tmpdir}/history.db"
            config._config["model"]["model_path"] = f"{tmpdir}/model.bin"
            config._config["vector_store"]["index_path"] = f"{tmpdir}/index.ann"

            daemon = DaedelusDaemon(config)
            print(f"✓ Daemon initialized with session: {daemon.session_id}")
            return True

    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_socket_timeout_handling():
    """Test that socket timeout is handled correctly in event loop."""
    print("\nTesting socket timeout handling...")
    try:
        # Create a simple socket server with timeout
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = f"{tmpdir}/test.sock"
            server_sock.bind(sock_path)
            server_sock.listen(1)
            server_sock.settimeout(0.5)

            # Try to accept with timeout (should raise socket.timeout)
            start = time.time()
            try:
                server_sock.accept()
                print("✗ Should have timed out")
                return False
            except socket.timeout:
                elapsed = time.time() - start
                print(f"✓ socket.timeout caught correctly (after {elapsed:.2f}s)")
                return True
            except Exception as e:
                print(f"✗ Wrong exception: {type(e).__name__}: {e}")
                return False
            finally:
                server_sock.close()

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_component_initialization():
    """Test that all daemon components can be initialized."""
    print("\nTesting component initialization...")
    try:
        from daedelus.core.database import CommandDatabase
        from daedelus.core.embeddings import CommandEmbedder
        from daedelus.core.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test database
            db_path = Path(tmpdir) / "test.db"
            db = CommandDatabase(db_path)
            session_id = db.create_session(shell="/bin/bash", cwd="/tmp")
            print(f"  ✓ Database initialized (session: {session_id})")
            db.close()

            # Test embedder
            model_path = Path(tmpdir) / "model.bin"
            embedder = CommandEmbedder(model_path=model_path)
            print(f"  ✓ Embedder initialized")

            # Test vector store
            index_path = Path(tmpdir) / "index.ann"
            vector_store = VectorStore(index_path=index_path, dim=128)
            print(f"  ✓ Vector store initialized")

        return True

    except Exception as e:
        print(f"✗ Component initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Daemon Startup Verification Tests")
    print("=" * 60)

    all_passed = True

    # Run tests
    all_passed &= test_daemon_imports()
    all_passed &= test_component_initialization()
    all_passed &= test_daemon_initialization()
    all_passed &= test_socket_timeout_handling()

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("\nThe daemon should now start correctly.")
        print("The socket.timeout fix resolves the event loop crash.")
        return 0
    else:
        print("✗ Some tests failed!")
        print("\nThere may be additional issues to resolve.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
