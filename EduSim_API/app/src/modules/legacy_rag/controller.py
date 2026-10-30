import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .service import query_rag_service

logger = logging.getLogger("EduSim.modules.legacy_rag.controller")


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="The educational question to ask")
    subject: Optional[str] = Field(None, description="The subject category (e.g., mathematics, science, biology)")
    class_num: Optional[int] = Field(None, description="The class/grade number (e.g., 1, 10)")
    board: Optional[str] = Field(None, description="The education board (e.g., NCERT, SSC)")
    book_code: Optional[str] = Field(None, description="Specific textbook code (e.g., aejm1, jesc1)")


class RagQueryResponse(BaseModel):
    success: bool
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None
    context: List[Any]
    fallback_mode: bool


async def rag_query_controller(request: RagQueryRequest):
    try:
        result = await query_rag_service(
            query=request.query,
            subject=request.subject,
            class_num=request.class_num,
            board=request.board,
            book_code=request.book_code,
        )
        return {
            "success": True,
            **result,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"RAG AI Service Unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}",
        )
    except Exception as e:
        logger.error(f"RAG Query Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the RAG query.",
        )
