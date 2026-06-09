"""
RAG Engine — Retrieval Augmented Generation
--------------------------------------------
Manages document ingestion, chunking, embedding, FAISS indexing,
and similarity search — all 100% CPU-friendly.

Stack:
  - sentence-transformers (all-MiniLM-L6-v2) for embeddings
  - FAISS flat index for vector search
  - pypdf / python-docx for document parsing
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGEngine:
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatL2] = None
        self._chunks: list[str] = []           # parallel to FAISS index rows
        self._chunk_sources: list[str] = []    # which file each chunk came from
        self._dim: int = 384                   # MiniLM output dim

    # ── Lazy model load ────────────────────────────────────────────────────────
    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s", settings.embedding_model)
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    @property
    def index(self) -> faiss.IndexFlatL2:
        if self._index is None:
            self._index = faiss.IndexFlatL2(self._dim)
        return self._index

    # ── Text extraction ────────────────────────────────────────────────────────
    def _extract_text(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return self._read_pdf(file_path)
        elif ext in (".docx", ".doc"):
            return self._read_docx(file_path)
        elif ext == ".txt":
            return Path(file_path).read_text(encoding="utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _read_pdf(self, path: str) -> str:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _read_docx(self, path: str) -> str:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    # ── Chunking ───────────────────────────────────────────────────────────────
    def _chunk_text(self, text: str) -> list[str]:
        size = settings.rag_chunk_size
        overlap = settings.rag_chunk_overlap
        words = text.split()
        chunks, start = [], 0
        while start < len(words):
            end = start + size
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start += size - overlap
        return chunks

    # ── Indexing ───────────────────────────────────────────────────────────────
    def ingest_file(self, file_path: str) -> int:
        """Extract, chunk, embed, and index a document. Returns chunk count."""
        logger.info("Ingesting: %s", file_path)
        text = self._extract_text(file_path)
        chunks = self._chunk_text(text)
        if not chunks:
            logger.warning("No text extracted from %s", file_path)
            return 0

        embeddings = self.model.encode(chunks, show_progress_bar=False)
        embeddings = np.array(embeddings, dtype="float32")
        self.index.add(embeddings)

        source = Path(file_path).name
        self._chunks.extend(chunks)
        self._chunk_sources.extend([source] * len(chunks))

        logger.info("Indexed %d chunks from %s", len(chunks), source)
        return len(chunks)

    # ── Retrieval ──────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """Return top-k relevant chunks for a query."""
        k = top_k or settings.rag_top_k
        if self.index.ntotal == 0:
            return []

        query_vec = self.model.encode([query], show_progress_bar=False)
        query_vec = np.array(query_vec, dtype="float32")

        distances, indices = self.index.search(query_vec, min(k, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            results.append({
                "chunk": self._chunks[idx],
                "source": self._chunk_sources[idx],
                "score": float(1 / (1 + dist)),  # normalise distance → similarity
            })
        return results

    def build_context(self, query: str) -> str:
        """Retrieve chunks and format as context string for the LLM."""
        hits = self.search(query)
        if not hits:
            return ""
        parts = [f"[Source: {h['source']}]\n{h['chunk']}" for h in hits]
        return "\n\n---\n\n".join(parts)

    def stats(self) -> dict:
        return {
            "total_chunks": self.index.ntotal,
            "unique_sources": len(set(self._chunk_sources)),
        }

    def reset(self):
        self._index = None
        self._chunks.clear()
        self._chunk_sources.clear()
        logger.info("RAG index reset")


# Singleton
rag_engine = RAGEngine()
