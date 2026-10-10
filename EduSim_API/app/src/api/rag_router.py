from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from app.src.services.rag_service import RagService
from app.src.modules.legacy_rag.controller import rag_query_controller, RagQueryRequest
from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.legacy_rag.vector_store import is_index_ready

rag_router = APIRouter()


def require_vector_index():
    if not is_index_ready() and not bool(vector_store._retrievers):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="index not built"
        )


class RagSearchRequest(BaseModel):
    subject: str = "physics"
    class_name: str = ""
    chapter: str = ""
    query: str = ""


@rag_router.post("/query")
async def query_rag_endpoint(request: RagQueryRequest):
    require_vector_index()
    return await rag_query_controller(request)


@rag_router.post("/search")
async def search_rag(req: RagSearchRequest):
    require_vector_index()
    chunks = RagService.search_chunks(req.subject, req.chapter, req.query)
    return {"chunks": chunks}

