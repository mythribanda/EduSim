
from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.api.persistence_router")

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.persistence import (
    FormulaHistory,
    SimulationHistory,
    ChatHistory,
    UserSetting,
    SessionEvent,
)
from app.src.services.persistence_service import (
    get_state_payload,
    get_persistence_snapshot,
    list_curriculum_history,
    list_dashboard_history,
    list_formula_history,
    list_sandbox_history,
    list_tutor_history,
    record_app_state,
    record_activity,
    record_curriculum_visit,
    record_formula_calculation,
    record_formula_action,
    save_formula_attempt,
    record_sandbox_event,
    record_search_history,
    record_search_selection,
    require_user,
    save_curriculum_progress,
    save_dashboard_state,
    save_formula_session,
    save_sandbox_state,
    save_tutor_conversation,
    save_user_state,
    upsert_user_profile,
    upsert_user_setting,
    record_user_session,
    record_refresh_token,
    upsert_session_state,
    serialize_row,
)


persistence_router = APIRouter(tags=["Persistence"])


class RecordActivityRequest(BaseModel):
    domain: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SessionStateRequest(BaseModel):
    namespace: str = Field(..., min_length=1)
    state_key: str = Field(..., min_length=1)
    state_json: dict[str, Any]
    expires_at: Optional[datetime] = None


class CurriculumProgressRequest(BaseModel):
    class_name: Optional[str] = None
    subject: str
    chapter: Optional[str] = None
    topic: Optional[str] = None
    progress_state: Optional[str] = "started"
    completion_percent: Optional[float] = 0.0
    last_opened_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_json: Optional[dict[str, Any]] = None


class TutorConversationRequest(BaseModel):
    source_query: str
    query_type: Optional[str] = None
    topic: Optional[str] = None
    subject: Optional[str] = None
    class_name: Optional[str] = None
    chapter: Optional[str] = None
    explanation: Optional[str] = None
    rag_content_json: Optional[Any] = None
    formulas_json: Optional[Any] = None
    metadata_json: Optional[dict[str, Any]] = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True


class FormulaSessionRequest(BaseModel):
    topic: str
    subject: Optional[str] = None
    class_name: Optional[str] = None
    chapter: Optional[str] = None
    active_tab: Optional[str] = None
    rag_content_json: Optional[Any] = None
    formulas_json: Optional[Any] = None
    state_json: Optional[dict[str, Any]] = None
    last_formula_id: Optional[str] = None
    closed_at: Optional[datetime] = None
    is_active: bool = True


class FormulaCalculationRequest(BaseModel):
    session_id: str
    formula_id: str
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: Optional[dict[str, Any]] = None
    calculation_steps_json: Optional[Any] = None
    graph_json: Optional[Any] = None


class SandboxStateRequest(BaseModel):
    simulation_id: str
    prompt: str
    topic: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    dsl_json: Optional[Any] = None
    runtime_json: Optional[Any] = None
    snapshot_json: Optional[Any] = None
    ui_state_json: Optional[dict[str, Any]] = None
    is_active: bool = True


class SandboxEventRequest(BaseModel):
    simulation_id: str
    event_type: str
    payload_json: Optional[Any] = None


class SearchHistoryRequest(BaseModel):
    query: str
    scope: Optional[str] = None
    result_count: int = 0
    results_json: Optional[Any] = None
    metadata_json: Optional[dict[str, Any]] = None


class DashboardStateRequest(BaseModel):
    widgets_json: Optional[Any] = None
    layout_json: Optional[Any] = None
    preferences_json: Optional[Any] = None
    last_viewed_at: Optional[datetime] = None


class UserProfileRequest(BaseModel):
    avatar: Optional[str] = None
    bio: Optional[str] = None
    display_name: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None


class UserSettingRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: Any


class FormulaActionRequest(BaseModel):
    session_id: str
    action: str
    formula_id: Optional[str] = None
    payload_json: Optional[Any] = None


class FormulaAttemptRequest(BaseModel):
    session_id: str
    formula_id: str
    attempt_json: dict[str, Any]
    score: Optional[float] = 0.0
    is_correct: Optional[bool] = False


class CurriculumVisitRequest(BaseModel):
    class_name: Optional[str] = None
    subject: str
    chapter: Optional[str] = None
    topic: Optional[str] = None
    page: Optional[str] = None
    time_spent_seconds: Optional[int] = 0
    progress_json: Optional[dict[str, Any]] = None


class SearchSelectionRequest(BaseModel):
    search_history_id: str
    selected_result: str
    selection_json: Optional[dict[str, Any]] = None


class AuthSessionRequest(BaseModel):
    session_key: str
    device_info: Optional[dict[str, Any]] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


class RefreshTokenRecordRequest(BaseModel):
    token_jti: str
    expires_at: Optional[datetime] = None
    device_info: Optional[dict[str, Any]] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@persistence_router.get("/snapshot")
def get_snapshot(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return get_persistence_snapshot(db, user=user)


@persistence_router.get("/state")
def load_state(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return get_state_payload(db, user=user)


@persistence_router.get("/tutor/history")
def load_tutor_history_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return list_tutor_history(db, user=user)


@persistence_router.get("/tutor/sessions")
def get_tutor_sessions_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    from app.src.repositories.persistence_repository import PersistenceRepository
    repo = PersistenceRepository(db)
    sessions = repo.list_tutor_sessions(user.id)
    return {"success": True, "sessions": sessions}


@persistence_router.get("/tutor/session/{session_id}")
def get_tutor_session_endpoint(
    session_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session_id UUID format")
    
    from app.src.services.persistence_service import get_tutor_conversation_payload
    payload = get_tutor_conversation_payload(db, sid)
    session_owner = payload.get("user_id")
    if session_owner and str(session_owner) != str(user.id):
        if getattr(user, "role", None) not in ("admin", "educator", "teacher"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not own this tutor session."
            )
    return {"success": True, "session": payload}


@persistence_router.delete("/tutor/session/{session_id}")
def delete_tutor_session_endpoint(
    session_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session_id UUID format")
        
    try:
        deleted = db.query(ChatHistory).filter(ChatHistory.session_id == sid, ChatHistory.user_id == user.id).delete()
        db.commit()
        logger.info("[Database] Chat history saved in the database: updated")
        return {"success": True, "message": "History deleted successfully.", "deleted_count": deleted}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to delete history."})


@persistence_router.get("/curriculum/history")
def load_curriculum_history_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return list_curriculum_history(db, user=user)


@persistence_router.get("/formula/history")
def load_formula_history_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return list_formula_history(db, user=user)


@persistence_router.get("/sandbox/history")
def load_sandbox_history_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return list_sandbox_history(db, user=user)


@persistence_router.get("/dashboard/history")
def load_dashboard_history_endpoint(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    return list_dashboard_history(db, user=user)


@persistence_router.post("/activity")
def add_activity(
    request: RecordActivityRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    event = record_activity(
        db,
        user=user,
        domain=request.domain,
        action=request.action,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        source=request.source,
        metadata=request.metadata,
    )
    try:
        db.commit()
        logger.info("[Database] Activity logs saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "event": event["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/user-state")
def save_user_state_endpoint(
    request: SessionStateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_user_state(
        db,
        user=user,
        payload={
            "last_page_visited": request.state_json.get("last_page_visited"),
            "temporary_ui_state": request.state_json.get("temporary_ui_state"),
            "restoration_snapshot": request.state_json.get("restoration_snapshot") or request.state_json,
            "last_refreshed_at": request.expires_at,
        },
    )
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "state": record}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/session-state")
def save_session_state(
    request: SessionStateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = upsert_session_state(
        db,
        user=user,
        namespace=request.namespace,
        state_key=request.state_key,
        state_json=request.state_json,
        expires_at=request.expires_at,
    )
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "state": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/profile")
def save_profile(
    request: UserProfileRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = upsert_user_profile(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Profile updated successfully.", "profile": record}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to update profile."})


@persistence_router.post("/settings")
def save_setting(
    request: UserSettingRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = upsert_user_setting(db, user=user, key=request.key, value=request.value)
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        db.refresh(record)
        return {"success": True, "message": "Settings saved successfully.", "setting": record.id}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/curriculum/progress")
def save_curriculum(
    request: CurriculumProgressRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_curriculum_progress(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "progress": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/curriculum/visit")
def save_curriculum_visit(
    request: CurriculumVisitRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_curriculum_visit(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "visit": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/tutor/session")
def save_tutor_session(
    request: TutorConversationRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_tutor_conversation(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] Chat history saved in the database: updated")
        return {"success": True, "message": "Learning summary saved successfully.", "session": str(record.id)}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save learning summary."})


@persistence_router.post("/auth/session")
def save_auth_session(
    request: AuthSessionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_user_session(
        db,
        user=user,
        session_key=request.session_key,
        device_info=request.device_info,
        user_agent=request.user_agent,
        ip_address=request.ip_address,
        expires_at=request.expires_at,
        metadata=request.metadata,
    )
    try:
        db.commit()
        logger.info("[Database] User session saved in the database: updated")
        db.refresh(record)
        return {"success": True, "message": "Settings saved successfully.", "session": record.id}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/auth/refresh-token")
def save_refresh_token(
    request: RefreshTokenRecordRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_refresh_token(
        db,
        user=user,
        token_jti=request.token_jti,
        expires_at=request.expires_at,
        device_info=request.device_info,
        user_agent=request.user_agent,
        ip_address=request.ip_address,
        metadata=request.metadata,
    )
    try:
        db.commit()
        logger.info("[Database] User session saved in the database: updated")
        db.refresh(record)
        return {"success": True, "message": "Settings saved successfully.", "refresh_token": record.id}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/formula/session")
def save_formula_lab_session(
    request: FormulaSessionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_formula_session(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Formula history saved successfully.", "session": str(record.id)}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save formula history."})


@persistence_router.post("/formula/action")
def save_formula_lab_action(
    request: FormulaActionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_formula_action(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Formula history saved successfully.", "action": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save formula history."})


@persistence_router.post("/formula/attempt")
def save_formula_lab_attempt(
    request: FormulaAttemptRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_formula_attempt(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Formula history saved successfully.", "attempt": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save formula history."})


@persistence_router.post("/formula/calculation")
def save_formula_lab_calculation(
    request: FormulaCalculationRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_formula_calculation(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] Formula history saved in the database: updated")
        db.refresh(record)
        return {"success": True, "message": "Formula history saved successfully.", "calculation": record.id}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save formula history."})


@persistence_router.get("/formula/calculation/{calculation_id}")
def load_formula_calculation(
    calculation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    try:
        cid = uuid.UUID(calculation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid calculation_id UUID format")
    calculation = db.query(FormulaHistory).filter(FormulaHistory.id == cid, FormulaHistory.user_id == user.id).first()
    if not calculation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formula calculation not found")
    return {"success": True, "calculation": calculation}


@persistence_router.post("/sandbox/state")
def save_sandbox(
    request: SandboxStateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_sandbox_state(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] Simulation history saved in the database: updated")
        db.refresh(record)
        return {"success": True, "message": "Simulation progress saved successfully.", "simulation": record.id, "simulation_id": record.simulation_id}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save simulation progress."})


@persistence_router.get("/sandbox/state/{simulation_id}")
def load_sandbox_state(
    simulation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = db.query(SimulationHistory).filter(SimulationHistory.simulation_id == simulation_id, SimulationHistory.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox simulation not found")
    return {"success": True, "simulation": record}


@persistence_router.post("/sandbox/event")
def save_sandbox_event(
    request: SandboxEventRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_sandbox_event(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Simulation progress saved successfully.", "event": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save simulation progress."})


@persistence_router.get("/search/history")
def load_search_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    from app.src.repositories.persistence_repository import PersistenceRepository
    repo = PersistenceRepository(db)
    history = repo.list_search_history(user.id)
    selections = repo._get_setting(user.id, "search_selections", [])
    
    return {
        "success": True,
        "history": [
            {
                "search": item,
                "selections": [sel for sel in selections if sel.get("search_history_id") == item.get("id")]
            }
            for item in history
        ],
    }


@persistence_router.post("/search/history")
def save_search_history(
    request: SearchHistoryRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_search_history(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "history": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/search/selection")
def save_search_result_selection(
    request: SearchSelectionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = record_search_selection(
        db,
        user=user,
        search_history_id=request.search_history_id,
        selected_result=request.selected_result,
        selection_json=request.selection_json,
    )
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "selection": record["id"]}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.post("/dashboard/state")
def save_dashboard(
    request: DashboardStateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = save_dashboard_state(db, user=user, payload=request.model_dump())
    try:
        db.commit()
        logger.info("[Database] User setting saved in the database: updated")
        return {"success": True, "message": "Settings saved successfully.", "dashboard": record}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save settings."})


@persistence_router.get("/settings")
def load_settings(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    from app.src.repositories.persistence_repository import PersistenceRepository
    repo = PersistenceRepository(db)
    return {"success": True, "settings": [serialize_row(item) for item in repo.list_user_settings(user.id)]}


@persistence_router.get("/profile")
def load_profile(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    from app.src.repositories.persistence_repository import PersistenceRepository
    repo = PersistenceRepository(db)
    profiles = repo.list_profiles(user.id)
    profile = profiles[0] if profiles else None
    return {"success": True, "profile": profile}


@persistence_router.delete("/sandbox/state/{simulation_id}")
def delete_sandbox_state(
    simulation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = db.query(SimulationHistory).filter(SimulationHistory.simulation_id == simulation_id, SimulationHistory.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox simulation not found")
    try:
        record.deleted_at = datetime.now()
        db.commit()
        logger.info("[Database] Simulation history saved in the database: updated")
        return {"success": True, "message": "History deleted successfully."}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to delete history."})


# --- NEW HISTORY ENDPOINTS ---

@persistence_router.get("/history/chat")
def get_chat_history(
    session_type: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    query = db.query(ChatHistory).filter(ChatHistory.user_id == user.id)
    if session_type:
        query = query.filter(ChatHistory.session_type == session_type)
    chats = query.order_by(ChatHistory.created_at.desc()).all()
    
    history_list = []
    for chat in chats:
        meta = chat.metadata_json or {}
        history_list.append({
            "id": str(chat.id),
            "user_id": str(chat.user_id),
            "session_id": str(chat.session_id),
            "session_type": chat.session_type,
            "topic": meta.get("topic") or meta.get("formula") or "General Physics",
            "summary": chat.content,
            "created_at": chat.created_at.isoformat() if hasattr(chat.created_at, "isoformat") else str(chat.created_at),
        })
    return {"success": True, "history": history_list}


@persistence_router.get("/history/formula")
def get_formula_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    calculations = db.query(FormulaHistory).filter(FormulaHistory.user_id == user.id).order_by(FormulaHistory.created_at.desc()).all()
    return {"success": True, "history": [serialize_row(calc) for calc in calculations]}


@persistence_router.get("/history/simulation")
def get_simulation_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    simulations = db.query(SimulationHistory).filter(SimulationHistory.user_id == user.id, SimulationHistory.deleted_at.is_(None)).order_by(SimulationHistory.created_at.desc()).all()
    return {"success": True, "history": [serialize_row(sim) for sim in simulations]}


@persistence_router.delete("/history/chat/{session_id}")
def delete_chat_history(
    session_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    try:
        sid = uuid.UUID(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session_id UUID format")
        
    try:
        deleted = db.query(ChatHistory).filter(ChatHistory.session_id == sid, ChatHistory.user_id == user.id).delete()
        db.commit()
        logger.info("[Database] Chat history saved in the database: updated")
        return {"success": True, "message": "History deleted successfully.", "deleted_count": deleted}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to delete history."})


@persistence_router.delete("/history/formula/{calculation_id}")
def delete_formula_calculation(
    calculation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    try:
        cid = uuid.UUID(calculation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid calculation_id UUID format")
        
    try:
        deleted = db.query(FormulaHistory).filter(FormulaHistory.id == cid, FormulaHistory.user_id == user.id).delete()
        db.commit()
        logger.info("[Database] Formula history saved in the database: updated")
        return {"success": True, "message": "History deleted successfully.", "deleted_count": deleted}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to delete history."})


@persistence_router.delete("/history/simulation/{simulation_id}")
def delete_simulation_history(
    simulation_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user = require_user(authorization, db)
    record = db.query(SimulationHistory).filter(SimulationHistory.simulation_id == simulation_id, SimulationHistory.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Simulation record not found")
    try:
        record.deleted_at = datetime.now()
        db.commit()
        logger.info("[Database] Simulation history saved in the database: updated")
        return {"success": True, "message": "History deleted successfully."}
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": "Failed to delete history."})


# ─────────────────────────────────────────────────────────────────────────────
# POST /session-event  — record one row in session_events
# ─────────────────────────────────────────────────────────────────────────────

VALID_EVENT_TYPES = {"started", "answered", "completed", "asked_tutor"}


class SessionEventRequest(BaseModel):
    module_id: Optional[str] = "00000000-0000-0000-0000-000000000000"
    event_type: str
    payload: Optional[dict] = None


@persistence_router.post("/session-event")
def create_session_event(
    request: SessionEventRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Insert one row into session_events.
    Called fire-and-forget from the frontend emitEvent() helper.
    """
    if request.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event_type '{request.event_type}'. Must be one of: {sorted(VALID_EVENT_TYPES)}",
        )

    user = require_user(authorization, db)

    try:
        module_uuid = uuid.UUID(request.module_id)
    except (ValueError, AttributeError):
        module_uuid = uuid.UUID("00000000-0000-0000-0000-000000000000")

    event = SessionEvent(
        student_id=user.id,
        module_id=module_uuid,
        event_type=request.event_type,
        payload=request.payload or {},
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return {
            "success": True,
            "event_id": str(event.id),
            "event_type": event.event_type,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[Database] Failed to write session_event: {e}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Failed to record session event."},
        )

