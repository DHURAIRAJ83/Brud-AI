import pytest
from ai.command_parser import command_parser, DesktopAction
from ai.action_planner import action_planner, ExecutionStrategy, TrustLevel
from ai.rag_engine import rag_engine


def test_command_decomposition():
    """Verify that multi-step commands are correctly decomposed into raw components."""
    raw_input_en = "create folder projects and open vscode"
    parts_en = command_parser.decompose_multi_step(raw_input_en)
    assert len(parts_en) == 2
    assert parts_en[0] == "create folder projects"
    assert parts_en[1] == "open vscode"

    raw_input_ta = "Projects folder உருவாக்கு பின்னர் குரோம் திற"
    parts_ta = command_parser.decompose_multi_step(raw_input_ta)
    assert len(parts_ta) == 2
    assert parts_ta[0] == "Projects folder உருவாக்கு"
    assert parts_ta[1] == "குரோம் திற"


def test_action_planner_decomposition_strategy():
    """Verify action planner selects DECOMPOSE strategy and builds sub_steps."""
    action = DesktopAction(
        tool="files.create_folder",
        params={"name": "reports"},
        confidence=0.95,
        raw_input="create folder reports then close paint",
        source_language="en",
        is_desktop_command=True
    )
    
    plan = action_planner.plan(action)
    assert plan.strategy == ExecutionStrategy.DECOMPOSE
    assert len(plan.sub_steps) == 2
    
    # Verify sub_steps details
    step1 = plan.sub_steps[0]
    assert step1["action"]["tool"] == "files.create_folder"
    assert step1["strategy"] == "await_approval"
    assert step1["trust_level"] == "caution"

    step2 = plan.sub_steps[1]
    assert step2["action"]["tool"] == "desktop.close_app"
    assert step2["strategy"] == "await_approval"
    assert step2["trust_level"] == "caution"

    # Overall trust level is the max (caution)
    assert plan.trust_level == TrustLevel.CAUTION


@pytest.mark.asyncio
async def test_rag_hybrid_boosting():
    """Verify that search query containing Tamil characters boosts matched chunks."""
    rag_engine.reset()
    
    # Ingest mock chunks
    rag_engine._chunks = [
        "FastAPI is a modern web framework for Python.",
        "நெசவுத் தொழில் என்பது தமிழ்நாட்டில் மிகவும் புகழ்பெற்றது.", # Has Tamil keyword "நெசவுத் தொழில்"
        "Machine Learning is a field of artificial intelligence."
    ]
    rag_engine._chunk_sources = ["source1", "source2", "source3"]
    
    # Manually populate index with dummy embeddings matching dimension
    import faiss
    import numpy as np
    rag_engine._index = faiss.IndexFlatL2(384)
    dummy_embeddings = np.random.randn(3, 384).astype("float32")
    # Normalize dummy vectors to simulate embeddings
    faiss.normalize_L2(dummy_embeddings)
    rag_engine.index.add(dummy_embeddings)
    
    # Query with Tamil keywords
    query = "தமிழ்நாட்டில் நெசவுத் தொழில் பற்றி கூறுங்கள்"
    
    # Search RAG
    results = rag_engine.search(query, top_k=3)
    
    # The Tamil chunk should rise to the top (highest score) due to keyword boosting
    assert len(results) > 0
    assert "நெசவுத்" in results[0]["chunk"]
    for res in results[1:]:
        assert results[0]["score"] > res["score"]
    
    rag_engine.reset()
