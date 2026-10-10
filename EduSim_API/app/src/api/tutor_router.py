import logging
logger = logging.getLogger("EduSim.api.tutor_router")

from fastapi import APIRouter, Query, Depends, Header, BackgroundTasks
from typing import Optional
from sqlalchemy.orm import Session
import uuid

from app.src.config.database import get_db
from app.src.services.persistence_service import record_activity, record_search_history, resolve_user_from_authorization
from app.src.modules.tutor.controller import analyze_tutor_controller, TutorQueryRequest
from app.src.modules.tutor import service as tutor_service
from app.src.models.persistence import ChatHistory
from app.src.modules.legacy_rag.generator import generate_openrouter_text_async
from fastapi.responses import StreamingResponse

tutor_router = APIRouter()

from pydantic import BaseModel, Field
from typing import List, Any
from app.src.services.tutor import build_tutor_prompt, ask_tutor_service, identify_topic_from_text
from app.src.services.ai_router import call_ai
from app.src.services.mastery import update_mastery

class AskTutorRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Student question or physics prompt")
    textbook_chunks: Optional[List[Any]] = Field(default=None, description="Optional textbook context excerpts")
    session_id: Optional[str] = None
    topic: Optional[str] = None
    student_id: Optional[str] = None


@tutor_router.post("/ask")
async def ask_tutor_endpoint(
    request: AskTutorRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Context-Aware Socratic Tutor Endpoint:
    1. Loads student profile (mastery scores, weak topics, class level) via build_tutor_prompt()
    2. Calls call_ai() from the AI router
    3. Saves Q&A pair to chat_history
    4. Calls update_mastery() if question maps to an identifiable topic
    """
    user = resolve_user_from_authorization(authorization, db)
    student_id = request.student_id or (user.id if user else None)
    if not student_id:
        student_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    result = await ask_tutor_service(
        student_id=student_id,
        question=request.query,
        textbook_chunks=request.textbook_chunks,
        session_id=request.session_id,
        db=db,
    )
    return result


@tutor_router.post("/analyze-stream")
async def analyze_query_stream(
    request: TutorQueryRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Analyzes a physics query and streams the response back for ultra-fast first token.
    """
    from app.src.modules.tutor.service import analyze_tutor_query_stream
    from fastapi.responses import StreamingResponse
    from app.src.config.database import SessionLocal
    
    user = resolve_user_from_authorization(authorization, db)
    student_profile = None
    if user:
        from app.src.repositories.student_repository import StudentRepository
        profile_obj = StudentRepository.get_or_create_profile(db, user.id)
        student_profile = {
            "skill_level": profile_obj.skill_level,
            "mastered_topics": profile_obj.mastered_topics,
            "misconceptions": profile_obj.misconceptions
        }
        
    history_dicts = None
    if request.history:
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]
    return StreamingResponse(
        analyze_tutor_query_stream(
            request.query,
            history=history_dicts,
            subject=request.subject,
            chapter=request.chapter,
            topic=request.topic,
            student_profile=student_profile,
            user_id=user.id if user else None,
            db_session_factory=SessionLocal
        ),
        media_type="text/event-stream"
    )


@tutor_router.post("/analyze")
async def analyze_query(
    request: TutorQueryRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
    db: Session = Depends(get_db),
):
    """
    Analyzes a physics query to detect concepts, formulas, and provide AI/RAG explanations.
    Guarantees AT MOST ONE OpenRouter LLM call per action.
    """
    user = resolve_user_from_authorization(authorization, db)
    student_profile = None
    if user:
        from app.src.repositories.student_repository import StudentRepository
        profile_obj = StudentRepository.get_or_create_profile(db, user.id)
        student_profile = {
            "skill_level": profile_obj.skill_level,
            "mastered_topics": profile_obj.mastered_topics,
            "misconceptions": profile_obj.misconceptions
        }
    else:
        logger.warning("[WARN] No user resolved from auth header — chat will NOT be saved to DB!")
        logger.info(f"  Authorization header present: {bool(authorization)}")
        if authorization and authorization.startswith("Bearer "):
            token_preview = authorization.split(" ", 1)[1][:20] + "..."
            logger.info(f"  Token preview: {token_preview}")
            from app.src.utils.auth import decode_token as _decode
            raw_token = authorization.split(" ", 1)[1].strip()
            try:
                import jwt as _jwt
                payload = _jwt.decode(raw_token, options={"verify_exp": False, "verify_signature": False})
                exp = payload.get("exp")
                if exp:
                    from datetime import datetime, timezone
                    exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                    now_dt = datetime.now(timezone.utc)
                    logger.info(f"  Token expired at: {exp_dt} (now: {now_dt}, delta: {now_dt - exp_dt})")
            except Exception:
                logger.info("  Could not decode token for diagnostics")
        
    effective_request_id = request.request_id or x_request_id or f"req_{uuid.uuid4().hex[:12]}"
    response = await analyze_tutor_controller(request, student_profile, request_id=effective_request_id)
    logger.info("--- DEBUG AUTH ---")
    logger.info(f"Authorization Header: {'present' if authorization else 'MISSING'}")
    logger.info(f"Resolved User: {user.id if user else 'NONE (NOT SAVING)'}")
    logger.info(f"Request ID: {effective_request_id}")
    logger.info(f"Provider: {response.get('provider', 'unknown')} | Tokens: {response.get('tokens_used', 0)}")
    logger.info("------------------")
    data = response.get("data", {}) if isinstance(response, dict) else {}
    explanation = data.get("explanation") or data.get("ai_explanation") or ""
    is_failed = bool(data.get("generation_failed", False)) or not bool(response.get("success", True))

    is_402 = (
        data.get("status_code") == 402
        or data.get("error_type") == "BILLING_CREDIT_LIMIT"
        or (is_failed and ("payment required (HTTP 402)" in explanation or "HTTP 402" in explanation))
    )

    if is_402:
        from fastapi.responses import JSONResponse
        logger.error("[DB SAVE SKIPPED] Tutor generation failed due to HTTP 402 Payment Required: %s", explanation[:150])
        return JSONResponse(
            status_code=402,
            content={
                "success": False,
                "message": "OpenRouter payment required (HTTP 402). Please add credits to your OpenRouter account.",
                "error": explanation,
                "data": data,
            }
        )
    
    if is_failed:
        logger.error("[DB SAVE SKIPPED] Tutor generation failed: %s", explanation[:150])
        return response

    if user:
        from app.src.repositories.persistence_repository import PersistenceRepository
        repo = PersistenceRepository(db)
        sessions = repo.list_tutor_sessions(user.id)
        
        session_id = None
        if request.session_id:
            try:
                session_id = uuid.UUID(request.session_id)
            except Exception:
                pass
                
        if not session_id:
            session_id = uuid.uuid4()
        
        # 1. Extract the topic
        concepts = data.get("concepts") or []
        topic = concepts[0] if concepts else request.query
        if len(topic) > 100:
            topic = topic[:97] + "..."
            
        # 2. Extract concise summary directly from the unified response (0 extra LLM calls)
        summary = data.get("summary")
        if not summary:
            summary = await generate_learning_summary(explanation)
        
        # 3. Save the summary and explanation into chat_history
        try:
            user_record = ChatHistory(
                user_id=user.id,
                session_id=session_id,
                session_type="tutor",
                role="user",
                topic=topic,
                content=request.query,
                summary=summary,
                metadata_json={
                    "class_name": request.class_name,
                    "subject": request.subject,
                    "chapter": request.chapter,
                    "topic": request.topic
                }
            )
            
            assistant_record = ChatHistory(
                user_id=user.id,
                session_id=session_id,
                session_type="tutor",
                role="assistant",
                topic=topic,
                content=explanation,
                summary=None,
                metadata_json={
                    "class_name": request.class_name,
                    "subject": request.subject,
                    "chapter": request.chapter,
                    "topic": request.topic
                }
            )
            
            logger.info("--- PERSISTENCE LOG ---")
            logger.info(f"user_id: {user.id}")
            logger.info(f"session_id: {session_id}")
            logger.info(f"topic: {topic}")
            logger.info(f"summary length: {len(summary) if summary else 0}")
            
            db.add(user_record)
            db.add(assistant_record)
            
            record_activity(
                db,
                user=user,
                domain="tutor",
                action="analyze",
                entity_type="query",
                entity_id=request.query[:120],
                source="/api/tutor/analyze",
                metadata={"topic": topic},
            )

            db.commit()
            db.refresh(user_record)
            db.refresh(assistant_record)
            
            logger.info(f"INSERTED RECORD ID: {user_record.id}")
            logger.info("-----------------------")
            
            if isinstance(response, dict):
                response["success"] = True
                response["message"] = "Learning summary saved successfully"
                response["session_id"] = str(session_id)
                
            # Queue non-LLM profile update in background (0 extra LLM calls)
            if explanation and "Error:" not in explanation:
                from app.src.config.database import SessionLocal
                from app.src.modules.tutor.service import update_profile_from_interaction
                background_tasks.add_task(
                    update_profile_from_interaction,
                    SessionLocal,
                    user.id,
                    concepts
                )
        except Exception as e:
            db.rollback()
            logger.error(f"Exception during save: {repr(e)}")
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save learning summary."})
    
    logger.info("Tutor request:", request.query)
    if explanation:
        try:
            logger.info("LLM response:", explanation[:200])
        except Exception:
            logger.info("LLM response contains non-ascii characters")
    try:
        logger.info("Tutor API response success:", response.get("success") if isinstance(response, dict) else True)
    except Exception:
        pass
    
    return response


@tutor_router.post("/guide")
async def get_tutor_guide(
    request: TutorQueryRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Analyzes a physics query to construct only the simulation guide/instructions (saving tokens).
    """
    from app.src.modules.tutor.service import generate_tutor_guide
    from fastapi import HTTPException
    
    try:
        response = await generate_tutor_guide(request.query)
        user = resolve_user_from_authorization(authorization, db)
        if user:
            concepts = request.topic or request.query
            if len(concepts) > 100:
                concepts = concepts[:97] + "..."
            
            record_activity(
                db,
                user=user,
                domain="tutor",
                action="guide",
                entity_type="query",
                entity_id=request.query[:120],
                source="/api/tutor/guide",
                metadata={"topic": concepts},
            )
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Exception during save guide activity: {repr(e)}")
                
        return {
            "success": True,
            "data": response
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tutor Guide Generation Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Tutor Guide Generation Error."
        )


@tutor_router.post("/explain-sim")
async def explain_sim(
    request: TutorQueryRequest,
    authorization: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
    db: Session = Depends(get_db),
):
    """
    Direct, fast, and RAG-free dynamic LLM explanation for simulation physics events.
    """
    from app.src.modules.tutor.service import explain_simulation_query
    from fastapi import HTTPException
    try:
        history_dicts = None
        if request.history:
            history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]
        effective_request_id = request.request_id or x_request_id
        data = await explain_simulation_query(request.query, history=history_dicts, request_id=effective_request_id)
        return {
            "success": True,
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation Explanation Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Simulation Explanation Error."
        )



@tutor_router.get("/search")
async def search_curriculum(
    q: str = Query(..., min_length=1),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Search the curriculum and return matching subjects/chapters/topics."""
    results = tutor_service.search_curriculum(q)
    user = resolve_user_from_authorization(authorization, db)
    if user:
        record_search_history(
            db,
            user=user,
            payload={
                "query": q,
                "scope": "curriculum",
                "result_count": len(results),
                "results_json": results,
            },
        )
        try:
            db.commit()
            logger.info("[Database] User setting saved in the database: updated")
            return {"query": q, "results": results, "message": "Settings saved successfully."}
        except Exception as e:
            db.rollback()
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})
    return {"query": q, "results": results}


@tutor_router.get("/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=1),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Return autocomplete suggestions for curriculum topics/chapters."""
    suggestions = tutor_service.autocomplete_curriculum(q)
    user = resolve_user_from_authorization(authorization, db)
    if user:
        record_search_history(
            db,
            user=user,
            payload={
                "query": q,
                "scope": "autocomplete",
                "result_count": len(suggestions),
                "results_json": suggestions,
            },
        )
        try:
            db.commit()
            logger.info("[Database] User setting saved in the database: updated")
            return {"query": q, "results": suggestions, "suggestions": suggestions, "message": "Settings saved successfully."}
        except Exception as e:
            db.rollback()
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})
    return {"query": q, "results": suggestions, "suggestions": suggestions}


@tutor_router.get("/topic")
async def get_topic(
    subject: str,
    class_name: str,
    chapter: str,
    topic: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Load stored curriculum content for the selected topic/chapter."""
    content = tutor_service.get_topic_content(subject, class_name, chapter, topic)
    user = resolve_user_from_authorization(authorization, db)
    if user:
        record_activity(
            db,
            user=user,
            domain="curriculum",
            action="open-topic",
            entity_type="topic",
            entity_id=f"{subject}:{class_name}:{chapter}:{topic or ''}",
            source="/api/tutor/topic",
            metadata={"subject": subject, "class_name": class_name, "chapter": chapter, "topic": topic},
        )
        try:
            db.commit()
            logger.info("[Database] Activity logs saved in the database: updated")
            if isinstance(content, dict):
                content["message"] = "Settings saved successfully."
        except Exception as e:
            db.rollback()
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})
    return content