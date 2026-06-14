"""
File Upload Service — validates and stores uploaded files.
Feeds new files into the RAG pipeline automatically.
"""

import logging
import os
import uuid
from pathlib import Path

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc"}
MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


class UploadService:
    def __init__(self):
        self._upload_dir = Path(settings.upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def validate(self, filename: str, size: int) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
            )
        if size > MAX_BYTES:
            raise ValueError(
                f"File too large ({size / 1024 / 1024:.1f} MB). "
                f"Max: {settings.max_file_size_mb} MB"
            )

    def save(self, filename: str, content: bytes) -> str:
        """Save file to uploads dir with a UUID prefix. Returns absolute path."""
        safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
        dest = self._upload_dir / safe_name
        dest.write_bytes(content)
        logger.info("Saved upload: %s (%d bytes)", dest, len(content))
        return str(dest)

    def list_files(self) -> list[dict]:
        """Return metadata for all uploaded files."""
        files = []
        for f in sorted(self._upload_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append({
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "path": str(f),
                })
        return files

    def delete(self, filename: str) -> bool:
        safe_name = Path(filename).name
        target = self._upload_dir / safe_name
        if target.exists():
            target.unlink()
            logger.info("Deleted: %s", safe_name)
            return True
        return False


# Singleton
upload_service = UploadService()
