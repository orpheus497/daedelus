"""Tests for command generator."""
import pytest

def test_generator_init(test_db):
    """Test generator initialization."""
    from daedelus.llm.command_generator import CommandGenerator
    generator = CommandGenerator(test_db)
    assert generator is not None

def test_generate_from_description(test_db):
    """Test command generation."""
    from daedelus.llm.command_generator import CommandGenerator
    generator = CommandGenerator(test_db)
    result = generator.generate("list files")
    assert isinstance(result, str)
