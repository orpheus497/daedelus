"""End-to-end integration tests."""
import pytest
import time

@pytest.mark.integration
def test_full_workflow(test_db, test_config):
    """Test complete user workflow."""
    from daedelus.core.suggestions import SuggestionEngine
    
    # Log commands
    test_db.log_command("git status", "/home/user/project", 0, 0.05)
    test_db.log_command("git add .", "/home/user/project", 0, 0.12)
    
    # Get suggestions
    engine = SuggestionEngine(test_db)
    suggestions = engine.suggest("git", cwd="/home/user/project")
    
    assert len(suggestions) > 0

@pytest.mark.integration
def test_privacy_filter_flow(test_db):
    """Test privacy filtering."""
    from daedelus.core.safety import SafetyAnalyzer
    
    analyzer = SafetyAnalyzer(level="warn")
    result = analyzer.check("cat ~/.ssh/id_rsa")
    
    # Should detect sensitive path
    assert result.is_dangerous or "ssh" in str(result).lower()
