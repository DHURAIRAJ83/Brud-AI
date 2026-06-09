"""
RAG Route — query the knowledge base directly
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.rag_engine import rag_engine
from ai.ollama_client import ollama_client

router = APIRouter()


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=20)


@router.post("/rag/query", summary="Query the RAG knowledge base")
async def rag_query(request: RAGQueryRequest):
    """Search uploaded documents and generate a grounded answer."""
    chunks = rag_engine.search(request.query, top_k=request.top_k)
    if not chunks:
        return {
            "answer": "No relevant documents found. Please upload files first.",
            "chunks": [],
            "stats": rag_engine.stats(),
        }

    context = "\n\n".join(c["chunk"] for c in chunks)
    prompt = (
        f"Answer this question using ONLY the provided context.\n"
        f"If the answer is not in the context, say 'I don't know'.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {request.query}\n\nAnswer:"
    )

    try:
        answer = await ollama_client.generate(prompt=prompt, temperature=0.3, max_tokens=400)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"answer": answer, "chunks": chunks, "stats": rag_engine.stats()}


@router.get("/rag/stats", summary="RAG index statistics")
async def rag_stats():
    return rag_engine.stats()


@router.post("/rag/reset", summary="Clear the RAG index")
async def rag_reset():
    rag_engine.reset()
    return {"message": "RAG index cleared."}
