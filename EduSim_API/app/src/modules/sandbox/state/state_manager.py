from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.state.state_manager")

"""
state_manager.py
================
Simulation State Manager & Physics Tick Orchestrator for EduSim.

This is the main execution controller of the backend runtime. It coordinates 
the exact physical-to-educational evaluation lifecycle for each frame tick:

Physics Tick / Frontend Event Sync
→ Authoritative Object State Sync
→ Invalidate Observable Cache
→ Topologically Recompute Observables
→ Refresh Educational Relationship Graph
→ Trigger Socratic Event Hooks
→ Dispatch Frontend Synchronization

It supports registering external tutor event hooks and handles coordinate updates 
dispatched by Matter.js.
"""


from typing import Any, Dict, List, Callable, Optional
from app.src.modules.sandbox.state.runtime_store import RuntimeStore
from app.src.modules.sandbox.state.mutations import apply_force

logger = logging.getLogger("EduSim.sandbox.state_manager")


class StateManager:
    """
    Main orchestrator for synchronization, event dispatching, 
    and reactive recomputations.
    """
    def __init__(self, store: RuntimeStore) -> None:
        self.store: RuntimeStore = store
        
        # Socratic tutor callbacks and event hooks
        self._tutor_triggers: List[Callable[[str, Any], None]] = []
        self._collision_callbacks: List[Callable[[str, str], None]] = []

    # --- Orchestration Event hooks ---

    def register_tutor_trigger(self, callback: Callable[[str, Any], None]) -> None:
        """Registers a listener for educational threshold events (e.g. max velocity achieved)."""
        self._tutor_triggers.append(callback)

    def register_collision_hook(self, callback: Callable[[str, str], None]) -> None:
        """Registers a listener for contact occurrences between bodies."""
        self._collision_callbacks.append(callback)

    def trigger_tutor_event(self, event_key: str, data: Any) -> None:
        """Dispatches educational event notifications to active tutoring engines."""
        for callback in self._tutor_triggers:
            try:
                callback(event_key, data)
            except Exception as e:
                logger.error(f"Error in tutor trigger callback: {e}")

    # ===========================================================================
    # Core Orchestration Tick Cycles
    # ===========================================================================

    def process_tick(self, delta_time: Optional[float] = None) -> None:
        """
        Manually advances the physical engine simulation state.
        Applies environment forces (like wind or drag) and recomputes all observables.
        """
        if self.store.simulation.is_paused:
            return

        # 1. Update timestep increments
        if delta_time is not None:
            self.store.simulation.delta_time = float(delta_time)
        self.store.simulation.step()

        # 2. Apply passive environmental forces (e.g. Wind or Drag)
        self._apply_environmental_forces()

        # 3. Flushes caches and recomputes educational observables
        self.store.observables.invalidate_cache()
        g_y = self.store.get_gravity_y()
        self.store.observables.evaluate_all(self.store.objects, g_y, self.store.simulation.frame_count)

        # 4. Notify system subscribers
        self.store.notify()

    def sync_frame_from_frontend(self, sync_payload: Dict[str, Any]) -> None:
        """
        Main synchronization entry point.
        Receives calculated coordinates, forces, and collisions from Matter.js frame,
        updates backend states, and evaluates dependent formulas.
        """
        # 1. Advance frames count matching frontend stepping
        self.store.simulation.frame_count = int(sync_payload.get("frame_count", self.store.simulation.frame_count + 1))
        self.store.simulation.simulation_time = float(sync_payload.get("simulation_time", self.store.simulation.simulation_time))

        # 2. Extract bodies arrays
        bodies_list = sync_payload.get("objects", [])
        for body_data in bodies_list:
            b_id = body_data.get("id")
            obj_state = self.store.objects.get(b_id)
            if not obj_state:
                continue

            # Parse position, velocity, acceleration, and dynamic forces
            pos = body_data.get("position", {"x": obj_state.position.x, "y": obj_state.position.y})
            vel = body_data.get("velocity", {"x": obj_state.velocity.x, "y": obj_state.velocity.y})
            accel = body_data.get("acceleration", {"x": obj_state.acceleration.x, "y": obj_state.acceleration.y})
            
            # Sync to the authoritative store database
            obj_state.sync_from_physics_engine(
                pos_x=float(pos.get("x", 0.0)),
                pos_y=float(pos.get("y", 0.0)),
                vel_x=float(vel.get("x", 0.0)),
                vel_y=float(vel.get("y", 0.0)),
                accel_x=float(accel.get("x", 0.0)),
                accel_y=float(accel.get("y", 0.0)),
                angle=float(body_data.get("angle", obj_state.angle)),
                ang_vel=float(body_data.get("angular_velocity", obj_state.angular_velocity)),
                ang_accel=float(body_data.get("angular_acceleration", obj_state.angular_acceleration)),
                force_x=float(body_data.get("net_force", {}).get("x", 0.0)),
                force_y=float(body_data.get("net_force", {}).get("y", 0.0)),
                torque=float(body_data.get("torque", 0.0)),
                is_sleeping=bool(body_data.get("is_sleeping", obj_state.is_sleeping)),
                colliding_with=body_data.get("colliding_with")
            )

        # 3. Process direct collisions events
        collisions_list = sync_payload.get("collisions", [])
        for col in collisions_list:
            id_a = col.get("body_a")
            id_b = col.get("body_b")
            
            # Dispatch to triggers
            for callback in self._collision_callbacks:
                try:
                    callback(id_a, id_b)
                except Exception as e:
                    logger.error("Error in collision callback: %s", e)

        # 4. Invalidate and evaluate educational observables (reactive recomputation)
        self.store.observables.invalidate_cache()
        g_y = self.store.get_gravity_y()
        self.store.observables.evaluate_all(self.store.objects, g_y, self.store.simulation.frame_count)

        # 5. Check for tutor threshold trigger actions (e.g. high energy alert)
        self._check_tutor_triggers()

        # 6. Dispatch final sync update to listeners (triggers web-sockets or persistence updates)
        self.store.notify()

    # --- Internal Utilities ---

    def _apply_environmental_forces(self) -> None:
        """Calculates passive force increments from wind configurations."""
        env = self.store.schema.environment
        
        # Apply Wind: F = mass * wind_magnitude
        if env.wind and env.wind.enabled:
            import math
            mag = env.wind.magnitude
            angle_rad = math.radians(env.wind.direction_deg)
            fx = mag * math.cos(angle_rad)
            fy = mag * math.sin(angle_rad)

            for obj_state in self.store.objects.values():
                if not obj_state.is_static and not obj_state.is_sensor:
                    # Apply proportional force mutator
                    apply_force(self.store, obj_state.id, fx * obj_state.mass, fy * obj_state.mass)

    def _check_tutor_triggers(self) -> None:
        """Scans calculated observables to trigger Socratic tutoring events."""
        # Example threshold: trigger whenever velocity exceeds speed bounds
        for obs_val in self.store.observables.values.values():
            schema = self.store.observables.schemas.get(obs_val.id)
            if schema and schema.tutor.importance >= 4:
                # High importance observables
                if abs(obs_val.value) > 15.0: # threshold speed 15m/s
                    self.trigger_tutor_event("threshold_exceeded", {
                        "observable_id": obs_val.id,
                        "value": obs_val.value,
                        "questions": schema.tutor.tutor_questions
                    })
