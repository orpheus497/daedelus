"""Tests for CLI module."""

from click.testing import CliRunner

from daedelus.cli.main import cli


def test_cli_version():
    """Test --version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.3.0" in result.output


def test_cli_help():
    """Test --help flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Daedalus" in result.output


def test_setup_command(temp_dir):
    """Test setup command."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=str(temp_dir)):
        result = runner.invoke(cli, ["setup"])
        assert result.exit_code == 0


def test_status_command(temp_dir):
    """Test status command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    # May fail if daemon not running, but should not crash
    assert result.exit_code in [0, 1]
