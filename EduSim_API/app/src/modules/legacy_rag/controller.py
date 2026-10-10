import logging
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from .service import query_rag_service

logger = logging.getLogger("EduSim.modules.legacy_rag.controller")

class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="The educational question to ask")
    subject: Optional[str] = Field("physics", description="The subject category (e.g., physics, biology)")

class RagQueryResponse(BaseModel):
    success: bool
    answer: str
    context: List[Any]
    fallback_mode: bool

async def rag_query_controller(request: RagQueryRequest):
    try:
        result = await query_rag_service(request.query, request.subject)
        return {
            "success": True,
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG Query Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the RAG query."
        )

