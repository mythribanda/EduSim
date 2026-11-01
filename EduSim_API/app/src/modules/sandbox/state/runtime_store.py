from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.state.runtime_store")

"""
runtime_store.py
================
Centralized Authoritative State Store for EduSim.

This acts as the centralized reactive database for the entire simulation execution. 
It houses all sub-state models (simulation clocks, active pointer coordinates, 
observable computations, and body transforms). 

It implements a pub/sub subscription mechanism (Observer pattern) so that external 
tutor engines, timeline scrubbers, or websocket controllers can monitor and react 
to state mutations.
"""


import uuid
from typing import Dict, Callable

from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema
from app.src.modules.sandbox.state.simulation_state import SimulationState
from app.src.modules.sandbox.state.object_state import ObjectRuntimeState, StateVector2D
from app.src.modules.sandbox.state.observable_state import ObservableStateManager
from app.src.modules.sandbox.state.interaction_state import InteractionState


class RuntimeStore:
    """
    Authoritative state repository and evaluation orchestrator.
    Combines global simulation, physical body, interactive pointer, 
    and calculated educational observable state contexts.
    """
    def __init__(self, sandbox: SandboxSchema) -> None:
        # Save base schema definition
        self.schema: SandboxSchema = sandbox
        
        # 1. Initialize Simulation State from metadata config
        rc = sandbox.metadata.runtime_config
        self.simulation: SimulationState = SimulationState(
            is_running=False,
            is_paused=True,
            simulation_time=0.0,
            frame_count=0,
            tick_rate=rc.max_fps,
            delta_time=1.0 / float(rc.max_fps),
            playback_speed=rc.simulation_speed,
            substeps=rc.substeps,
            active_scene_id=sandbox.metadata.id
        )

        # 2. Populate Object states from SandboxObjects
        self.objects: Dict[str, ObjectRuntimeState] = {}
        for obj in sandbox.objects:
            # Sync initial velocities and mass from the static compiled schema definition
            p = obj.position
            v = obj.runtime.initial_velocity
            
            # Simple inertia fallback (e.g. cylinder inertia = 0.5 * m * r^2)
            inertia = 1.0
            if obj.radius is not None:
                inertia = 0.5 * obj.physics.mass * (obj.radius ** 2)
            elif obj.width is not None and obj.height is not None:
                inertia = (1.0 / 12.0) * obj.physics.mass * (obj.width**2 + obj.height**2)

            state = ObjectRuntimeState(
                id=obj.id,
                position=StateVector2D(x=p.x, y=p.y),
                velocity=StateVector2D(x=v.x, y=v.y),
                acceleration=StateVector2D(x=0.0, y=0.0),
                angle=obj.runtime.initial_angle,
                angular_velocity=obj.runtime.initial_angular_vel,
                mass=obj.physics.mass,
                inertia=inertia,
                is_static=obj.is_static,
                is_sleeping=obj.runtime.is_sleeping,
                is_sensor=obj.physics.is_sensor,
                is_visible=obj.visuals.visible
            )
            self.objects[obj.id] = state

        # 3. Initialize ObservableStateManager
        self.observables: ObservableStateManager = ObservableStateManager(sandbox.observables)
        # Sequence order based on topological sort from schema compilation
        self.observables.set_evaluation_order([o.id for o in sandbox.observables])

        # 4. Initialize Pointer & Interaction State
        self.interaction: InteractionState = InteractionState()

        # 5. Pub/Sub Subscribers registry
        self._subscribers: Dict[str, Callable[[RuntimeStore], None]] = {}

    # --- Subscriber Registration ---

    def subscribe(self, callback: Callable[[RuntimeStore], None]) -> str:
        """
        Registers an external callback function that triggers on every tick 
        or state mutation. Returns a subscription ID for disposal.
        """
        sub_id = str(uuid.uuid4())
        self._subscribers[sub_id] = callback
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Removes a registered callback subscription."""
        if subscription_id in self._subscribers:
            del self._subscribers[subscription_id]

    def notify(self) -> None:
        """Dispatches the updated store instance to all registered observers."""
        for callback in list(self._subscribers.values()):
            try:
                callback(self)
            except Exception as e:
                logger.error(f"Error invoking state subscriber callback: {e}")

    # --- Unified Value Accessors ---

    def get_gravity_y(self) -> float:
        """Returns the vertical environment gravity component."""
        return self.schema.environment.gravity.y * self.schema.environment.gravity.scale
