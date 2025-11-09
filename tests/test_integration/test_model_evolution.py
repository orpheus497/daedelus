"""Model evolution tests."""
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_model_version_tracking(temp_dir):
    """Test model version management."""
    from daedelus.llm.model_manager import ModelManager
    
    mgr = ModelManager(temp_dir)
    models = mgr.list_models()
    
    assert isinstance(models, list)
