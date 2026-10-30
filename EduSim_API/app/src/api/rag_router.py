from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.src.api.auth import get_current_user
from app.src.models.user import User
from app.src.services.rag_service import RagService
from app.src.modules.legacy_rag.controller import rag_query_controller, RagQueryRequest
from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.legacy_rag.vector_store import is_index_ready

rag_router = APIRouter()


def require_vector_index():
    if not vector_store.is_ready and not is_index_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="index not built"
        )


class RagSearchRequest(BaseModel):
    subject: str = "physics"
    class_name: str = ""
    chapter: str = ""
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    query: str = ""


@rag_router.post("/query")
async def query_rag_endpoint(
    request: RagQueryRequest,
    current_user: User = Depends(get_current_user),
):
    require_vector_index()
    try:
        return await rag_query_controller(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {str(e)}",
        )


@rag_router.post("/search")
async def search_rag(
    req: RagSearchRequest,
    current_user: User = Depends(get_current_user),
):
    require_vector_index()
    chunks = RagService.search_chunks(
        subject=req.subject,
        chapter=req.chapter,
        query=req.query,
        chapter_number=req.chapter_number,
        chapter_title=req.chapter_title,
    )
    return {"chunks": chunks}
