"""
controller.py
=============
Lightweight FastAPI Controller/Router Layer for EduSim Sandbox Orchestration.

Exposes REST boundaries to manage simulation generation, state synchronization,
dynamic parameter manipulation, and checkpoint/snapshot workflows.

Maintains structural separation by delegating all execution logic to the service layer.
Enforces strict IDOR protection: every query that takes a session_id / simulation_id
verifies that the session belongs to the requesting user.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Body, status, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.user import User
from app.src.models.persistence import SimulationHistory
from app.src.services.persistence_service import (
    record_activity,
    record_sandbox_event,
    resolve_user_from_authorization,
    save_sandbox_state,
)
from app.src.modules.sandbox import service

logger = logging.getLogger(__name__)

# Initialize APIRouter
sandbox_router = APIRouter(prefix="/sandbox", tags=["Sandbox"])


# ============================================================================
# IDOR Verification Helper
# ============================================================================

async def verify_sandbox_session_owner(
    simulation_id: str,
    user: Optional[User],
    db: Session
) -> None:
    """
    IDOR Prevention: Validates that the requested sandbox session belongs
    to the authenticated user making the request.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access sandbox session."
        )

    # Educators and Admins can supervise all sessions
    role = getattr(user, "role", None)
    if role in ("admin", "educator", "teacher", "superadmin"):
        return

    # 1. Check in-memory session owner
    owner_id = await service.get_session_owner(simulation_id)
    if owner_id and str(owner_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not own this sandbox simulation session."
        )

    # 2. Check persistent SimulationHistory records in database
    sim_record = (
        db.query(SimulationHistory)
        .filter(SimulationHistory.simulation_id == str(simulation_id))
        .first()
    )
    if sim_record and str(sim_record.user_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not own this sandbox simulation session."
        )


# ============================================================================
# Pydantic Request Models
# ============================================================================

class LoadRequest(BaseModel):
    """Payload to retrieve an active simulation session."""
    simulation_id: str = Field(..., description="UUID of the active simulation session")


class ResetRequest(BaseModel):
    """Payload to reset a simulation back to its initial Frame 0 config."""
    simulation_id: str = Field(..., description="UUID of the active simulation session")


class ControlUpdateRequest(BaseModel):
    """Payload to apply slider or coordinate changes to active objects."""
    simulation_id: str = Field(..., description="UUID of the active simulation session")
    control_id: str = Field(..., description="Widget ID mapped in sandbox controls")
    value: Any = Field(..., description="Target value to apply (mass, gravity, etc)")


class SnapshotRestoreRequest(BaseModel):
    """Payload containing complete snapshot parameters to restore sandbox state."""
    snapshot: Dict[str, Any] = Field(..., description="Lightweight snapshot record")


# ============================================================================
# DEPRECATED: use POST /api/simulations/generate
@sandbox_router.post(
    "/generate",
    summary="[Deprecated] Generate simulation - use POST /api/simulations/generate",
    deprecated=True
)
async def generate_sandbox_simulation_deprecated(
    request: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    from app.src.modules.simulation_synthesis.service import generate_simulation_synthesis
    prompt = request.get("prompt", "")
    topic = request.get("topic")
    user = resolve_user_from_authorization(authorization, db)
    user_id = str(user.id) if user else None
    return await service.generate_simulation(prompt=prompt, topic=topic, user_id=user_id)


@sandbox_router.post(
    "/load",
    summary="Fetch current serialized parameters of an active session"
)
async def load_sandbox_simulation(
    request: LoadRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Returns the initial state configuration or current coordinates of the active ID.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(request.simulation_id, user, db)
        data = await service.load_simulation(simulation_id=request.simulation_id)
        if user:
            record_activity(
                db,
                user=user,
                domain="sandbox",
                action="load",
                entity_type="simulation",
                entity_id=request.simulation_id,
                source="/api/sandbox/load",
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Simulation retrieval failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulation retrieval failed due to an internal error."
        )


@sandbox_router.post(
    "/reset",
    summary="Reset active simulation session to its start frame"
)
async def reset_sandbox_simulation(
    request: ResetRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Restores positions, velocities, clocks, and observables back to initial values.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(request.simulation_id, user, db)
        data = await service.reset_simulation(simulation_id=request.simulation_id)
        if user:
            record_activity(
                db,
                user=user,
                domain="sandbox",
                action="reset",
                entity_type="simulation",
                entity_id=request.simulation_id,
                source="/api/sandbox/reset",
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Simulation reset failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulation reset failed due to an internal error."
        )


@sandbox_router.post(
    "/control/update",
    summary="Apply parameter updates to dynamic elements"
)
async def update_sandbox_control(
    request: ControlUpdateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Applies widget value mutations and triggers reactive observable re-evaluation.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(request.simulation_id, user, db)
        data = await service.update_control(
            simulation_id=request.simulation_id,
            control_id=request.control_id,
            value=request.value
        )
        if user:
            record_sandbox_event(
                db,
                user=user,
                payload={
                    "simulation_id": request.simulation_id,
                    "event_type": "control-update",
                    "payload_json": {"control_id": request.control_id, "value": request.value},
                },
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Parameter modification failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Parameter modification failed due to an internal error."
        )


@sandbox_router.get(
    "/runtime/{id}",
    summary="Get dynamic tick sync parameters"
)
async def get_sandbox_runtime(
    simulation_id: str = Path(..., alias="id", description="Active simulation UUID"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Fetches real-time ticks, speed clocks, pointer positions, and canvas bounds.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(simulation_id, user, db)
        data = await service.get_runtime_payload(simulation_id=simulation_id)
        if user:
            record_activity(
                db,
                user=user,
                domain="sandbox",
                action="runtime",
                entity_type="simulation",
                entity_id=simulation_id,
                source="/api/sandbox/runtime",
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Failed to fetch runtime tick: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch runtime tick due to an internal error."
        )


@sandbox_router.get(
    "/snapshot/{id}",
    summary="Download deep serializable state checkpoint"
)
async def get_sandbox_snapshot(
    simulation_id: str = Path(..., alias="id", description="Active simulation UUID"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Captures complete positions, coordinates, forces, and observables for undo/replays.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(simulation_id, user, db)
        data = await service.get_snapshot(simulation_id=simulation_id)
        if user:
            record_activity(
                db,
                user=user,
                domain="sandbox",
                action="snapshot",
                entity_type="simulation",
                entity_id=simulation_id,
                source="/api/sandbox/snapshot",
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Failed to capture snapshot: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture snapshot due to an internal error."
        )


@sandbox_router.post(
    "/snapshot/{id}/restore",
    summary="Restore state coordinates from checkpoint upload"
)
async def restore_sandbox_snapshot(
    simulation_id: str = Path(..., alias="id", description="Active simulation UUID"),
    request: SnapshotRestoreRequest = Body(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Restores velocities, coordinates, and calculations from deep snapshot dictionary.
    Enforces IDOR verification.
    """
    try:
        user = resolve_user_from_authorization(authorization, db)
        await verify_sandbox_session_owner(simulation_id, user, db)
        data = await service.restore_snapshot(
            simulation_id=simulation_id,
            snapshot_data=request.snapshot
        )
        if user:
            record_activity(
                db,
                user=user,
                domain="sandbox",
                action="restore-snapshot",
                entity_type="simulation",
                entity_id=simulation_id,
                source="/api/sandbox/snapshot/restore",
                metadata={"snapshot": request.snapshot},
            )
            db.commit()
        return {
            "success": True,
            **data
        }
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error(f"Failed to restore state snapshot: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore state snapshot due to an internal error."
        )
