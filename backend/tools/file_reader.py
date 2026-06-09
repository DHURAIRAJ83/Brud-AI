"""
File Reader Tool
----------------
Reads uploaded files and answers questions about their content.
Leverages RAG for semantic search when content is large.
"""

import logging
from pathlib import Path

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def file_reader_tool(user_message: str, file_path: str = None, **_) -> str:
    """Read a file and return its text or use RAG to answer questions."""
    if not file_path:
        # Try to find most recently uploaded file
        upload_dir = Path(settings.upload_dir)
        files = sorted(upload_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return "No files have been uploaded yet."
        file_path = str(files[0])

    path = Path(file_path)
    if not path.exists():
        return f"File not found: {path.name}"

    ext = path.suffix.lower()
    try:
        if ext == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            return f"Cannot read file type: {ext}"
    except Exception as e:
        logger.error("File read error: %s", e)
        return f"Error reading file: {e}"

    if not text.strip():
        return "The file appears to be empty."

    # For short files, return directly; for long files, use RAG
    word_count = len(text.split())
    if word_count <= 400:
        return f"**File: {path.name}**\n\n{text}"

    # Use LLM to answer question about the file content
    from ai.ollama_client import ollama_client
    truncated = " ".join(text.split()[:600])
    answer = await ollama_client.generate(
        prompt=(
            f"Based on this document content, answer the user's question.\n\n"
            f"Document ({path.name}):\n{truncated}\n\n"
            f"User question: {user_message}\n\n"
            f"Answer:"
        ),
        temperature=0.3,
        max_tokens=400,
    )
    return answer
