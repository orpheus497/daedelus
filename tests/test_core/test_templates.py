"""
Tests for command template system.

Tests Jinja2 template rendering and variable substitution.

Created by: orpheus497
"""

from daedelus.core.templates import TemplateManager


def test_template_system_init(temp_dir):
    """Test template system initialization."""
    system = TemplateManager(template_dir=temp_dir)
    assert system.template_dir == temp_dir


def test_create_template(temp_dir):
    """Test template creation."""
    system = TemplateManager(template_dir=temp_dir)

    template_id = system.create(
        name="git_commit", template="git commit -m '{{message}}'", category="git"
    )

    assert template_id is not None


def test_render_template(temp_dir):
    """Test Jinja2 rendering."""
    system = TemplateManager(template_dir=temp_dir)

    system.create(name="echo_var", template="echo {{variable}}", category="test")

    result = system.render("echo_var", {"variable": "hello"})

    assert result == "echo hello"


def test_built_in_templates(temp_dir):
    """Test default template library."""
    system = TemplateManager(template_dir=temp_dir)

    templates = system.list_built_in()

    # Should have git, docker templates
    assert len(templates) > 0


def test_delete_template(temp_dir):
    """Test template removal."""
    system = TemplateManager(template_dir=temp_dir)

    tid = system.create("test", "echo test", "test")
    system.delete(tid)

    # Should be deleted
    assert system.get(tid) is None
