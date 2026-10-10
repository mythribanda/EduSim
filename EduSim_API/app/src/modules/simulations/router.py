"""
router.py
=========
FastAPI REST router for deterministic static physics simulations and AI explanation.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel, Field

from .registry import (
    SIMULATION_REGISTRY,
    get_simulation_meta,
    get_simulation_schema,
    run_simulation,
)
from app.src.services.ai_router import call_ai

logger = logging.getLogger("EduSim.simulations")

router = APIRouter(tags=["Static Simulations"])


class ExplainSimulationRequest(BaseModel):
    simulation_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    student_question: str


def strip_markdown(text: str) -> str:
    """Removes markdown formatting tags, returning clean plain text."""
    # Remove code blocks and inline backticks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove headers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Remove bold and italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Remove bullet list symbols and blockquotes
    text = re.sub(r"^\s*[-*+>]\s+", "", text, flags=re.MULTILINE)
    # Replace newlines and excessive whitespace with a single space
    text = re.sub(r"\s+", " ", text).strip()

    # Enforce constraint: under 100 words
    words = text.split()
    if len(words) > 100:
        truncated = " ".join(words[:100])
        last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        if last_punct > 30:
            text = truncated[:last_punct + 1]
        else:
            text = truncated + "."

    return text.strip()


@router.get(
    "/api/simulations/static",
    summary="List all static simulations",
    description="Returns metadata for all available deterministic physics simulations."
)
@router.get("/api/simulations/static/", include_in_schema=False)
async def list_simulations():
    return {
        "success": True,
        "simulations": SIMULATION_REGISTRY
    }


@router.get(
    "/api/simulations/static/{simulation_id}/schema",
    summary="Get parameter JSON schema for a simulation",
    description="Returns the Pydantic model JSON Schema for automatic frontend form and slider generation."
)
async def get_simulation_parameter_schema(
    simulation_id: str = Path(..., description="Simulation identifier e.g. 'projectile-motion'")
):
    schema = get_simulation_schema(simulation_id)
    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"Static simulation '{simulation_id}' not found."
        )
    meta = get_simulation_meta(simulation_id)
    return {
        "success": True,
        "simulation_id": simulation_id,
        "meta": meta,
        "schema": schema
    }


@router.post(
    "/api/simulations/static/{simulation_id}/run",
    summary="Execute deterministic simulation computation",
    description="Computes exact physics equations and returns time series graph points and metrics."
)
async def run_simulation_endpoint(
    simulation_id: str = Path(..., description="Simulation identifier e.g. 'projectile-motion'"),
    params: Dict[str, Any] = Body(default_factory=dict, description="Input simulation parameters")
):
    try:
        result = run_simulation(simulation_id, params)
        return {
            "success": True,
            "simulation_id": simulation_id,
            "parameters": params,
            "result": result,
            # Also keep root-level state keys for backwards compatibility
            **result
        }
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Static simulation calculation failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Static simulation calculation failed."
        )



@router.post(
    "/api/simulations/explain",
    summary="AI explanation of simulation outcome",
    description="Generates an encouraging, kid-friendly explanation under 100 words in plain text."
)
@router.post("/api/simulations/static/explain", include_in_schema=False)
async def explain_simulation_endpoint(request: ExplainSimulationRequest):
    """
    Explains the physics behind a student's question using Ollama.
    """
    # 1. System prompt
    system_prompt = (
        "You are a friendly physics tutor for students aged 10-16. "
        "Always use simple language. Never use jargon without explaining it. "
        "Be encouraging and curious."
    )

    # 2. Extract title and clean numeric params/results (filter out large raw sample arrays)
    meta = get_simulation_meta(request.simulation_id)
    sim_title = meta.get("title") if meta else request.simulation_id.replace("-", " ").title()

    clean_params = {
        k: v for k, v in request.params.items()
        if not isinstance(v, list)
    }
    clean_results = {
        k: v for k, v in request.result.items()
        if not isinstance(v, list) and k not in ("graph_data", "formulas_used")
    }

    # 3. User prompt
    user_prompt = (
        f"Simulation: {sim_title}\n"
        f"Parameters: {json.dumps(clean_params if clean_params else request.params, indent=2)}\n"
        f"Results: {json.dumps(clean_results if clean_results else request.result, indent=2)}\n\n"
        f'Student Question: "{request.student_question}"\n\n'
        "Please explain why this happened in simple, encouraging words.\n"
        "Rules:\n"
        "- Plain text only (no markdown, no asterisks, no bullet points, no bold, no backticks)\n"
        "- Keep the total explanation under 100 words\n"
        "- Friendly, warm, and curious tone"
    )

    try:
        ai_response = await call_ai(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        raw_text = ai_response.get("text", "")
        clean_text = strip_markdown(raw_text)
        if not clean_text:
            clean_text = (
                f"Great observation! In {sim_title}, changing the settings directly impacts the motion "
                "because energy and forces shift. Keep experimenting to see how each control affects the path!"
            )
        return {"explanation": clean_text}
    except Exception as exc:
        logger.error(f"Failed to generate simulation explanation: {exc}")
        return {
            "explanation": (
                f"Great question! In {sim_title}, the outcome changes because forces and energy are connected. "
                "Try adjusting the values again and watch how the graph responds!"
            )
        }

