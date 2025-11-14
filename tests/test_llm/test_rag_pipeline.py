"""Tests for RAG pipeline."""



def test_rag_pipeline_init(test_db):
    """Test RAG pipeline initialization."""
    from daedelus.llm.rag_pipeline import RAGPipeline

    pipeline = RAGPipeline(test_db)
    assert pipeline.db == test_db


def test_retrieve_context(test_db):
    """Test context retrieval."""
    from daedelus.llm.rag_pipeline import RAGPipeline

    test_db.log_command("git status", "/home/user", 0, 0.05)
    pipeline = RAGPipeline(test_db)
    context = pipeline.retrieve_context("git", cwd="/home/user")
    assert isinstance(context, (list, dict))
