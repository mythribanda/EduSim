import logging
logger = logging.getLogger("EduSim.api.simulation_router")

from fastapi import APIRouter, Depends, Header
from typing import Optional
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.services.persistence_service import record_activity, resolve_user_from_authorization

from app.src.modules.simulation_synthesis.controller import (
    AgentGenerateRequest,
    synthesis_generate_controller,
    synthesis_list_controller,
    synthesis_get_controller,
    synthesis_export_controller,
    synthesis_generate_stream_controller,
)

simulation_router = APIRouter()


# Unified simulation generation endpoint
@simulation_router.post("/generate")
# DEPRECATED: use POST /api/simulations/generate
@simulation_router.post("/synthesis/generate")
async def generate_synthesized_simulation(
    request: AgentGenerateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    response = await synthesis_generate_controller(request)
    user = resolve_user_from_authorization(authorization, db)
    if user:
        record_activity(
            db,
            user=user,
            domain="simulation",
            action="synthesis-generate",
            entity_type="simulation",
            entity_id=str(response.get("id") or request.prompt[:120]),
            source="/api/simulations/generate",
            metadata={"topic": request.topic},
        )
        try:
            db.commit()
            logger.info("[Database] Activity logs saved in the database: updated")
            if isinstance(response, dict):
                response["message"] = "Simulation progress saved successfully."
        except Exception as e:
            db.rollback()
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=500, content={"success": False, "message": "Failed to save simulation progress."})
    return response


@simulation_router.post("/generate-stream")
@simulation_router.post("/synthesis/generate-stream")
async def generate_synthesized_simulation_stream(
    request: AgentGenerateRequest,
):
    return await synthesis_generate_stream_controller(request)


@simulation_router.get("/list")
@simulation_router.get("/synthesis/list")
async def list_synthesized_simulations(limit: int = 30):
    return await synthesis_list_controller(limit=limit)


@simulation_router.get("/{simulation_id}")
@simulation_router.get("/synthesis/{simulation_id}")
async def get_synthesized_simulation(simulation_id: str):
    return await synthesis_get_controller(simulation_id=simulation_id)


@simulation_router.get("/{simulation_id}/export")
@simulation_router.get("/synthesis/{simulation_id}/export")
async def export_synthesized_simulation(simulation_id: str):
    return await synthesis_export_controller(simulation_id=simulation_id)


from app.src.modules.simulations.static.simulation_registry import (
    list_static_simulations,
    get_static_simulation,
    run_static_simulation,
)
from fastapi import Body, HTTPException


# ============================================================================
# DETERMINISTIC STATIC SIMULATION ENDPOINTS
# ============================================================================

@simulation_router.get("/static")
async def get_static_simulations_registry():
    """
    Returns metadata and parameter schemas for all deterministic static simulations.
    """
    return {
        "success": True,
        "simulations": list_static_simulations()
    }


@simulation_router.get("/static/{simulation_id}")
async def get_single_static_simulation(simulation_id: str):
    """
    Returns parameter schema and metadata for a specific static simulation.
    """
    sim = get_static_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Static simulation '{simulation_id}' not found.")
    return {
        "success": True,
        **sim
    }


@simulation_router.post("/static/{simulation_id}/run")
async def run_static_simulation_endpoint(
    simulation_id: str,
    params: dict = Body(default_factory=dict),
):
    """
    Executes deterministic physics calculation for a static simulation.
    """
    try:
        result = run_static_simulation(simulation_id=simulation_id, params=params)
        return {
            "success": True,
            **result
        }
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Static simulation calculation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Static simulation calculation failed.")



# ============================================================================
# SIMPLIFIED AI SIMULATION ENDPOINTS
# ============================================================================

# DEPRECATED: use POST /api/simulations/generate
@simulation_router.post("/agent/generate")
async def generate_with_agent(request: AgentGenerateRequest):
    return await synthesis_generate_controller(request)


@simulation_router.post("/agent/generate-stream")
async def generate_with_agent_stream(request: AgentGenerateRequest):
    return await synthesis_generate_stream_controller(request)


@simulation_router.post("/agent/error-report")
async def report_agent_error(simulation_id: str | None = None, payload: dict | None = None):
    return {"success": True, "detail": "Telemetry disabled by design."}


@simulation_router.post("/runtime/report")
async def report_runtime_intelligence(report_data: dict):
    return {"success": True, "detail": "Telemetry disabled by design."}