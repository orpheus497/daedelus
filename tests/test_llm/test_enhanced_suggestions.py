"""Tests for enhanced suggestions."""



def test_enhanced_suggestions_init(test_db):
    """Test enhanced suggestions initialization."""
    from daedelus.llm.enhanced_suggestions import EnhancedSuggestions

    es = EnhancedSuggestions(test_db)
    assert es is not None
