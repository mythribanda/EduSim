import logging
from typing import List, Dict, Any, Union, Optional
from fastapi import APIRouter, Depends, Body, Header, status
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.services.question_service import QuestionService
from app.src.services.persistence_service import resolve_user_from_authorization
from app.src.models.question_models import (
    QuestionGenerateRequest,
    QuestionItem,
    QuestionGenerationResponse,
    QuestionSubmitRequest,
    QuestionSubmitResponse,
)

logger = logging.getLogger("EduSim.api.questions")

router = APIRouter(tags=["Questions"])


@router.post("/generate", response_model=List[QuestionItem])
@router.post("/generate/", response_model=List[QuestionItem], include_in_schema=False)
async def generate_questions_endpoint(
    req: QuestionGenerateRequest = Body(...),
    db: Session = Depends(get_db),
):
    """
    Cached Physics Question Generator:
    1. Checks the questions table in DB:
       SELECT questions WHERE topic=? AND difficulty=? AND class_level=? LIMIT count
    2. If enough cached questions exist, returns them (zero AI cost).
    3. If not enough, calls Ollama to generate the shortfall only.
    4. Validates and saves newly generated questions to the questions table for all future calls.
    """
    questions = await QuestionService.generate_cached_questions(
        topic=req.topic,
        difficulty=req.difficulty,
        class_level=req.class_level,
        count=req.count,
        db=db,
    )
    return questions


@router.post("/submit", response_model=QuestionSubmitResponse)
@router.post("/submit/", response_model=QuestionSubmitResponse, include_in_schema=False)
async def submit_question_endpoint(
    req: QuestionSubmitRequest = Body(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Submit student answer to evaluate correctness, update mastery, and fetch recommendations.
    """
    user = resolve_user_from_authorization(authorization, db)
    effective_student_id = req.student_id or (str(user.id) if user else None)
    
    result = await QuestionService.submit_question_answer(
        topic=req.topic,
        selected_option=req.selected_option,
        student_id=effective_student_id,
        question_id=req.question_id,
        correct_option=req.correct_option,
        db=db,
    )
    return result
