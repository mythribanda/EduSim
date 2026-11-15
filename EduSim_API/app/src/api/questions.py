import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Body, Header
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.services.question_service import QuestionService
from app.src.services.persistence_service import resolve_user_from_authorization
from app.src.models.question_models import (
    QuestionGenerateRequest,
    QuestionItem,
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
    Cached Curriculum Question Generator:
    1. Checks the questions table in DB for matching topic and difficulty.
    2. If enough cached questions exist, returns them immediately.
    3. If not enough, calls AI with fallback to generate questions for any subject/topic.
    4. Caches newly generated questions to the questions table for instant future hits.
    """
    effective_topic = req.topic or req.chapter or req.subject or "Science Concepts"
    effective_class = req.class_name or req.class_level or "10"
    questions = await QuestionService.generate_cached_questions(
        topic=effective_topic,
        subject=req.subject or "Science",
        difficulty=req.difficulty,
        class_level=effective_class,
        count=req.count,
        formula=req.formula or "",
        exclude_questions=req.exclude_questions or [],
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
