import logging
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .service import (
    generate_simulation_synthesis,
    list_simulation_synthesis,
    get_simulation_synthesis,
    generate_simulation_synthesis_stream,
)

logger = logging.getLogger("EduSim.modules.simulation_synthesis.controller")


class AgentGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=4, description="User prompt for simulation generation")
    topic: str | None = Field(default=None, description="Optional topic override")
    complexity: str | None = Field(default=None, description="Complexity level")
    include_answers: bool = Field(default=True, description="Whether to include answers")
    streaming: bool = Field(default=False, description="Whether to stream the response")


async def synthesis_generate_controller(request: AgentGenerateRequest):
    try:
        data = await generate_simulation_synthesis(prompt=request.prompt, topic=request.topic)
        return {
            "success": True,
            **data,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Simulation synthesis failed.")



async def synthesis_list_controller(limit: int = 30):
    try:
        data = await list_simulation_synthesis(limit=limit)
        return {
            "success": True,
            "items": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list simulations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list simulations.")


async def synthesis_get_controller(simulation_id: str):
    try:
        item = await get_simulation_synthesis(simulation_id=simulation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Simulation not found")
        return {
            "success": True,
            **item,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load simulation.")


async def synthesis_export_controller(simulation_id: str):
    import json as _json
    try:
        item = get_simulation_synthesis(simulation_id=simulation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Simulation not found")

        filename = f"{simulation_id}.json"
        return Response(
            content=_json.dumps(item.get("dsl", {}), indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export simulation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export simulation.")


async def synthesis_generate_stream_controller(request: AgentGenerateRequest):
    """
    Streaming version of synthesis generation.
    Returns Server-Sent Events (SSE) stream showing progress updates.
    
    Events:
    - started: Initial event with simulation ID
    - progress: Stage updates
    - complete: Final event with full simulation
    - error: Error event if generation fails
    """
    try:
        return StreamingResponse(
            generate_simulation_synthesis_stream(
                prompt=request.prompt,
                topic=request.topic
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable proxy buffering
                "Connection": "keep-alive",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start streaming.")