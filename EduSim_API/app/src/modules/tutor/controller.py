import logging
from fastapi import HTTPException
from pydantic import BaseModel, Field
from .service import analyze_tutor_query

logger = logging.getLogger("EduSim.modules.tutor.controller")


class ChatMessage(BaseModel):
    role: str
    content: str

class TutorQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="The physics question or formula to analyze")
    class_name: str | None = None
    subject: str | None = None
    chapter: str | None = None
    topic: str | None = None
    history: list[ChatMessage] | None = None
    session_id: str | None = None
    request_id: str | None = None

async def analyze_tutor_controller(
    request: TutorQueryRequest,
    student_profile: dict | None = None,
    request_id: str | None = None
):
    try:
        history_dicts = None
        if request.history:
            history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]
        effective_request_id = request.request_id or request_id
        data = await analyze_tutor_query(
            request.query,
            history=history_dicts,
            subject=request.subject,
            chapter=request.chapter,
            topic=request.topic,
            student_profile=student_profile,
            request_id=effective_request_id
        )
        is_failed = bool(data.get("generation_failed", False))
        return {
            "success": not is_failed,
            "data": data,
            "generation_status": data.get("generation_status", "failed" if is_failed else "success"),
            "provider": data.get("provider", "unknown"),
            "tokens_used": data.get("tokens_used", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tutor Analysis Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Tutor Analysis Error."
        )

