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
        """Return top-k relevant chunks for a query with hybrid Tamil keyword boosting."""
        k = top_k or settings.rag_top_k
        if self.index.ntotal == 0:
            return []

        query_vec = self.model.encode([query], show_progress_bar=False)
        query_vec = np.array(query_vec, dtype="float32")

        # Detect if query has Tamil characters
        is_tamil = any(0x0B80 <= ord(c) <= 0x0BFF for c in query)

        # Retrieve more candidates if we want to re-rank via keyword boosting
        candidate_k = min(k * 3, self.index.ntotal) if is_tamil else min(k, self.index.ntotal)
        distances, indices = self.index.search(query_vec, candidate_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            
            chunk_text = self._chunks[idx]
            base_score = float(1 / (1 + dist))
            boost = 0.0
            
            if is_tamil:
                # Tokenize and filter out common stop words
                words = [w.strip(".,!?\"'()[]{}") for w in query.lower().split()]
                stop_words = {"என்று", "என்பது", "மற்றும்", "ஒரு", "the", "a", "is", "in", "of", "and", "to", "for", "on", "with"}
                keywords = [w for w in words if w and w not in stop_words and len(w) > 1]
                
                if keywords:
                    matches = sum(1 for kw in keywords if kw in chunk_text.lower())
                    boost = 0.25 * (matches / len(keywords))

            results.append({
                "chunk": chunk_text,
                "source": self._chunk_sources[idx],
                "score": base_score + boost,
            })
            
        if is_tamil:
            results.sort(key=lambda x: x["score"], reverse=True)
            
        return results[:k]

    async def build_context(self, query: str) -> str:
        """
        Builds a dependency-aware context (HR-04) combining:
        - Active Workspace Context (Active File, Active Symbol)
        - Direct and Second-level imports (with traversal depth limit <= 3)
        - RAG search results for the user query
        Enforces strict limits: MAX_DEPENDENCY_FILES = 10, MAX_CONTEXT_CHARS = 12000.
        """
        from ai.project_context import project_context_manager
        from ai.workspace_indexer import workspace_indexer
        from models.base import db_manager
        import json

        ctx = project_context_manager.get_context()
        active_file = ctx.get("active_file")
        active_symbol = ctx.get("active_symbol")
        cursor_line = ctx.get("cursor_line") or 1

        # 1. Search RAG chunks as baseline
        hits = self.search(query)

        # Gather all codebase files we are interested in
        codebase_files = set()
        if active_file:
            codebase_files.add(active_file)

        # Try to resolve RAG search hit sources to codebase files
        try:
            all_modules = await db_manager.fetch_all("SELECT file_path FROM project_modules")
            module_paths = [row["file_path"] for row in all_modules]
        except Exception as e:
            logger.debug("Failed fetching project modules for RAG resolution: %s", e)
            module_paths = []

        for h in hits:
            src = h["source"]
            # Find matching module in workspace
            for p in module_paths:
                if p.endswith("/" + src) or p == src:
                    codebase_files.add(p)
                    break

        # 2. Trace dependencies up to depth 3 for all codebase files
        dependencies = []
        for f in list(codebase_files):
            try:
                deps = await workspace_indexer.resolve_dependency_chain(f, max_depth=3)
                dependencies.extend(deps)
            except Exception as e:
                logger.debug("Failed resolving dependency chain for %s: %s", f, e)

        # 3. Create blocks with priorities
        blocks = []

        # Priority 1: Active File Snippet
        if active_file:
            full_path = workspace_indexer.root_dir / active_file
            if full_path.exists():
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    line_idx = cursor_line - 1
                    start = max(0, line_idx - 100)
                    end = min(len(lines), line_idx + 100)
                    content = "".join(lines[start:end])
                    blocks.append({
                        "file": active_file,
                        "type": "active_file",
                        "priority": 1.0,
                        "content": f"# --- Active File: {active_file} (Lines {start+1} to {end}) ---\n{content}"
                    })
                except Exception as ex:
                    logger.debug("Error reading active file %s: %s", active_file, ex)

        # Priority 1.5: RAG Search Chunks (direct factual hits from query)
        for idx, h in enumerate(hits):
            blocks.append({
                "file": h["source"],
                "type": "rag_hit",
                "priority": 1.5,
                "content": f"[Source Document: {h['source']}]\n{h['chunk']}"
            })

        # Priority 2: Active Symbol Definition
        if active_symbol:
            # Look up active symbol definition in workspace index lists
            symbol_def = None
            symbol_type = "unknown"
            for c in workspace_indexer.classes:
                if c["name"] == active_symbol:
                    symbol_def = c
                    symbol_type = "class"
                    break
            if not symbol_def:
                for f in workspace_indexer.functions:
                    if f["name"] == active_symbol:
                        symbol_def = f
                        symbol_type = "function"
                        break
            if not symbol_def:
                for r in workspace_indexer.routes:
                    if r["function"] == active_symbol or r["path"] == active_symbol:
                        symbol_def = r
                        symbol_type = "route"
                        break

            if symbol_def:
                sym_file = symbol_def["file"]
                sym_line = symbol_def.get("line") or 1
                full_path = workspace_indexer.root_dir / sym_file
                if full_path.exists():
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        start = max(0, sym_line - 1)
                        end = min(len(lines), start + 60)
                        content = "".join(lines[start:end])
                        blocks.append({
                            "file": sym_file,
                            "type": "active_symbol",
                            "priority": 2.0,
                            "content": f"# --- Active Symbol Definition: {active_symbol} ({symbol_type}) in {sym_file} ---\n{content}"
                        })
                    except Exception as ex:
                        logger.debug("Error reading symbol file %s: %s", sym_file, ex)

        # Priority 3 & 4 & 5: Dependencies from chain
        processed_deps = set()
        for dep in dependencies:
            to_file = dep["to_file"]
            depth = dep["depth"]

            # Map depth to priority
            # Depth 1 -> Priority 3 (Direct imports)
            # Depth 2 -> Priority 4 (Second-level imports)
            # Depth 3 -> Priority 5 (Transitive imports)
            priority = 3.0 if depth == 1 else (4.0 if depth == 2 else 5.0)

            dep_key = (to_file, priority)
            if dep_key in processed_deps:
                continue
            processed_deps.add(dep_key)

            # Retrieve DB model details
            try:
                row = await db_manager.fetch_one(
                    "SELECT classes, functions, routes FROM project_modules WHERE file_path = ?",
                    (to_file,)
                )
            except Exception:
                row = None

            if row:
                try:
                    classes_list = json.loads(row["classes"])
                    funcs_list = json.loads(row["functions"])
                    routes_list = json.loads(row["routes"])

                    summary_parts = [f"# --- Dependency (Depth {depth}): {to_file} ---"]
                    if classes_list:
                        summary_parts.append(f"Classes: {', '.join(classes_list)}")
                    if funcs_list:
                        summary_parts.append(f"Functions: {', '.join(funcs_list)}")
                    if routes_list:
                        summary_parts.append(f"Routes: {', '.join(routes_list)}")
                    if not classes_list and not funcs_list and not routes_list:
                        summary_parts.append("(No public symbols)")

                    blocks.append({
                        "file": to_file,
                        "type": "dependency",
                        "priority": priority,
                        "content": "\n".join(summary_parts)
                    })
                except Exception as ex:
                    logger.debug("Error parsing dependency JSON for %s: %s", to_file, ex)

        # 4. Sort blocks by priority
        blocks.sort(key=lambda b: b["priority"])

        # 5. Assemble context under limits (HR-04)
        MAX_DEPENDENCY_FILES = 10
        MAX_CONTEXT_CHARS = 12000

        final_parts = []
        distinct_files = set()
        current_chars = 0

        for b in blocks:
            file_name = b["file"]
            
            # Skip dependency summaries if the file's detailed code was already included
            if b["type"] == "dependency" and file_name in distinct_files:
                continue
                
            is_new_file = file_name not in distinct_files
            if is_new_file and len(distinct_files) >= MAX_DEPENDENCY_FILES:
                continue

            block_content = b["content"]
            if current_chars + len(block_content) + 4 > MAX_CONTEXT_CHARS:
                # Truncate this block to fit perfectly
                remaining = MAX_CONTEXT_CHARS - current_chars - 4
                if remaining > 100:
                    truncated_content = block_content[:remaining] + "\n..."
                    final_parts.append(truncated_content)
                    distinct_files.add(file_name)
                break

            final_parts.append(block_content)
            distinct_files.add(file_name)
            current_chars += len(block_content) + 4

        return "\n\n---\n\n".join(final_parts)

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
