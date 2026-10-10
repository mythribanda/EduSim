"""
service.py
==========
Authoritative Application Orchestrator for the EduSim Sandbox.

This file coordinates the initialization pipeline, creates the centralized 
authoritative RuntimeStore database, manages simulation session lifecycles, 
triggers mutations, and organizes snapshots/checkpoint timelines.

It acts as an adapter between the FastAPI boundary and internal engine mechanics.
Uses non-blocking asyncio.Lock() for high-concurrency event-loop safety.
"""

from __future__ import annotations
import asyncio
import uuid
from typing import Any, Dict, Optional

# Core Engine Imports
from app.src.modules.sandbox.initialization.sandbox_initializer import SandboxInitializer
from app.src.modules.sandbox.state.runtime_store import RuntimeStore
from app.src.modules.sandbox.state.mutations import update_widget_mutation
from app.src.modules.sandbox.state.snapshots import (
    take_snapshot,
    restore_snapshot as restore_snapshot_engine,
    SnapshotTimeline,
    SimulationSnapshot
)
from app.src.modules.sandbox.serializers import RuntimeSerializer

# Memory Registries with non-blocking asyncio.Lock
_session_lock = asyncio.Lock()
_active_sessions: Dict[str, RuntimeStore] = {}
_initial_specs: Dict[str, Any] = {}
_timelines: Dict[str, SnapshotTimeline] = {}
_session_owners: Dict[str, Optional[str]] = {}


async def get_session_owner(simulation_id: str) -> Optional[str]:
    """Retrieve the owner user_id for a given simulation session."""
    async with _session_lock:
        return _session_owners.get(simulation_id)


async def set_session_owner(simulation_id: str, user_id: Optional[str]) -> None:
    """Register or update the owner user_id for a simulation session."""
    async with _session_lock:
        _session_owners[simulation_id] = str(user_id) if user_id else None


async def generate_simulation(
    prompt: str,
    topic: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Coordinates context retrieval, LLM synthesis, Pydantic validation, 
    and compiler initialization to instantiate a new stateful session.
    
    Returns the full initial client-ready payload contract.
    """
    from app.src.modules.simulation_synthesis.service import generate_simulation_synthesis

    # 1. Synthesize declarative sandbox specification using AI Synthesis Core
    synthesis_result = await generate_simulation_synthesis(prompt=prompt, topic=topic)
    simulation_id = synthesis_result["id"]
    spec_data = synthesis_result.get("dsl", synthesis_result)

    # 2. Run Physical Compiler pipeline to heal units/normalize elements
    initializer = SandboxInitializer()
    sandbox_schema = initializer.pipeline.execute(spec_data)

    # 3. Create active RuntimeStore database state
    store = RuntimeStore(sandbox_schema)
    # Pre-evaluate direct and derived observables
    store.observables.evaluate_all(store.objects, store.get_gravity_y(), 0)

    # 4. Instantiate Snapshot Timeline
    timeline = SnapshotTimeline(store, max_history=100)
    timeline.record_checkpoint()

    # 5. Register session persistently in memory with non-blocking async lock
    async with _session_lock:
        _active_sessions[simulation_id] = store
        _initial_specs[simulation_id] = spec_data
        _timelines[simulation_id] = timeline
        if user_id:
            _session_owners[simulation_id] = str(user_id)

    # 6. Serialize and return the complete, frontend-safe initial payload
    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }


async def load_simulation(simulation_id: str) -> Dict[str, Any]:
    """
    Retrieves an active RuntimeStore session by ID and returns 
    its current serialized state.
    """
    async with _session_lock:
        store = _active_sessions.get(simulation_id)

    if not store:
        raise ValueError(f"Simulation session '{simulation_id}' not found.")

    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }


async def reset_simulation(simulation_id: str) -> Dict[str, Any]:
    """
    Reconstructs the active simulation session back to its Frame 0 starting point.
    """
    async with _session_lock:
        spec_data = _initial_specs.get(simulation_id)

    if not spec_data:
        raise ValueError(f"Initial specification for session '{simulation_id}' not found.")

    # Re-compile raw spec
    initializer = SandboxInitializer()
    sandbox_schema = initializer.pipeline.execute(spec_data)

    # Re-hydrate store
    store = RuntimeStore(sandbox_schema)
    store.observables.evaluate_all(store.objects, store.get_gravity_y(), 0)

    # Re-initialize timeline
    timeline = SnapshotTimeline(store, max_history=100)
    timeline.record_checkpoint()

    async with _session_lock:
        _active_sessions[simulation_id] = store
        _timelines[simulation_id] = timeline

    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }


async def update_control(simulation_id: str, control_id: str, value: Any) -> Dict[str, Any]:
    """
    Applies live widget slider values directly to physical bounds,
    re-evaluating observables, and returns the serialized tick sync frame.
    """
    async with _session_lock:
        store = _active_sessions.get(simulation_id)
        timeline = _timelines.get(simulation_id)

    if not store:
        raise ValueError(f"Simulation session '{simulation_id}' not found.")

    # Record history checkpoint before mutation
    if timeline:
        timeline.record_checkpoint()

    # Execute structured mutation
    update_widget_mutation(store, control_id, value)

    # Evaluate all reactive observables
    store.observables.evaluate_all(store.objects, store.get_gravity_y(), store.simulation.frame_count)

    # Serialize tick frame
    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }


async def get_runtime_payload(simulation_id: str) -> Dict[str, Any]:
    """
    Retrieves standard high-speed client-ready ticks for WebSocket updates.
    """
    async with _session_lock:
        store = _active_sessions.get(simulation_id)

    if not store:
        raise ValueError(f"Simulation session '{simulation_id}' not found.")

    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }


async def get_snapshot(simulation_id: str) -> Dict[str, Any]:
    """
    Takes a deep, serializable state checkpoint.
    """
    async with _session_lock:
        store = _active_sessions.get(simulation_id)

    if not store:
        raise ValueError(f"Simulation session '{simulation_id}' not found.")

    snapshot = take_snapshot(store)
    return {
        "simulation_id": simulation_id,
        "snapshot": snapshot.model_dump()
    }


async def restore_snapshot(simulation_id: str, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Loads and restores the state coordinates and observable clocks from
    a provided checkpoint dictionary.
    """
    async with _session_lock:
        store = _active_sessions.get(simulation_id)

    if not store:
        raise ValueError(f"Simulation session '{simulation_id}' not found.")

    snapshot = SimulationSnapshot(**snapshot_data)
    restore_snapshot_engine(store, snapshot)

    return {
        "simulation_id": simulation_id,
        "payload": RuntimeSerializer.serialize_full(store)
    }
