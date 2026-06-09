"""
Upload Route — POST /api/upload, GET /api/files, DELETE /api/files/{name}
"""

import asyncio
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from services.upload_service import upload_service
from ai.rag_engine import rag_engine

router = APIRouter()


@router.post("/upload", summary="Upload a document for RAG indexing")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a PDF, DOCX, or TXT file.
    The file is automatically ingested into the RAG knowledge base.
    """
    content = await file.read()
    try:
        upload_service.validate(file.filename, len(content))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    saved_path = upload_service.save(file.filename, content)

    # Ingest into RAG (run in thread to avoid blocking event loop)
    loop = asyncio.get_event_loop()
    chunk_count = await loop.run_in_executor(
        None, rag_engine.ingest_file, saved_path
    )

    return {
        "message": "File uploaded and indexed successfully.",
        "filename": file.filename,
        "chunks_indexed": chunk_count,
        "rag_stats": rag_engine.stats(),
    }


@router.get("/files", summary="List uploaded files")
async def list_files():
    return {"files": upload_service.list_files()}


@router.delete("/files/{filename}", summary="Delete an uploaded file")
async def delete_file(filename: str):
    deleted = upload_service.delete(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"message": f"Deleted: {filename}"}
