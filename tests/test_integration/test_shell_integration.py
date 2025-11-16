"""Shell integration tests."""

import pytest


@pytest.mark.integration
def test_command_logging_from_shell(test_db):
    """Test shell -> daemon communication."""
    # Simulate shell logging
    cmd_id = test_db.log_command("echo test", "/home/user", 0, 0.01)
    assert cmd_id > 0
