"""
snapshots.py
============
Runtime Snapshot, Checkpoint, and Timeline Replay Engine for EduSim.

This module captures deep, lightweight state snapshots of the RuntimeStore.
These snapshots are completely serializable, enabling:
- Timeline scrubbing (rewinding/forwarding frames)
- Replay systems (saving and loading execution history)
- Multi-checkpoint Undo/Redo operations
"""


from __future__ import annotations
from typing import Any, Dict, List
from copy import deepcopy
from pydantic import BaseModel, Field

from app.src.modules.sandbox.state.runtime_store import RuntimeStore
from app.src.modules.sandbox.state.object_state import StateVector2D


class SimulationSnapshot(BaseModel):
    """
    Authoritative lightweight state checkpoint record.
    Completely serializable to JSON.
    """
    simulation_state: Dict[str, Any] = Field(..., description="Copy of global SimulationState parameters")
    object_states: Dict[str, Dict[str, Any]] = Field(..., description="Map of object_id -> object state dict")
    interaction_state: Dict[str, Any] = Field(..., description="Copy of InteractionState parameters")
    observable_values: Dict[str, float] = Field(..., description="Map of observable_id -> calculated float value")


def take_snapshot(store: RuntimeStore) -> SimulationSnapshot:
    """
    Captures the current state of the RuntimeStore into a deep,
    serializable SimulationSnapshot model.
    """
    # 1. Capture Simulation State
    sim_copy = store.simulation.model_dump()

    # 2. Capture Object States
    objs_copy = {}
    for oid, obj in store.objects.items():
        objs_copy[oid] = obj.model_dump()

    # 3. Capture Interaction State
    inter_copy = store.interaction.model_dump()

    # 4. Capture current cached observable readings
    obs_copy = {}
    for oid, val in store.observables.values.items():
        obs_copy[oid] = val.value

    return SimulationSnapshot(
        simulation_state=sim_copy,
        object_states=objs_copy,
        interaction_state=inter_copy,
        observable_values=obs_copy
    )


def restore_snapshot(store: RuntimeStore, snapshot: SimulationSnapshot) -> None:
    """
    Restores the RuntimeStore state from a SimulationSnapshot.
    Re-evaluates dependencies and dispatches notifications.
    """
    # 1. Restore Simulation Parameters
    for k, v in snapshot.simulation_state.items():
        setattr(store.simulation, k, v)

    # 2. Restore Object States
    for oid, obj_dict in snapshot.object_states.items():
        if oid in store.objects:
            obj_state = store.objects[oid]
            # Restore coordinate fields
            obj_state.position = StateVector2D(**obj_dict["position"])
            obj_state.velocity = StateVector2D(**obj_dict["velocity"])
            obj_state.acceleration = StateVector2D(**obj_dict["acceleration"])
            obj_state.net_force = StateVector2D(**obj_dict["net_force"])
            
            # Restore other scalar fields
            obj_state.angle = obj_dict["angle"]
            obj_state.angular_velocity = obj_dict["angular_velocity"]
            obj_state.angular_acceleration = obj_dict["angular_acceleration"]
            obj_state.torque = obj_dict["torque"]
            obj_state.mass = obj_dict["mass"]
            obj_state.inertia = obj_dict["inertia"]
            obj_state.is_sleeping = obj_dict["is_sleeping"]
            obj_state.is_selected = obj_dict["is_selected"]
            obj_state.is_hovered = obj_dict["is_hovered"]
            obj_state.colliding_with = list(obj_dict["colliding_with"])

    # 3. Restore Interaction State
    from app.src.modules.sandbox.state.interaction_state import PointerCoordinate
    for k, v in snapshot.interaction_state.items():
        if k == "pointer":
            store.interaction.pointer = PointerCoordinate(**v)
        else:
            setattr(store.interaction, k, deepcopy(v))

    # 4. Restore Observable values
    store.observables.invalidate_cache()
    for oid, val in snapshot.observable_values.items():
        if oid in store.observables.values:
            run_val = store.observables.values[oid]
            run_val.value = val
            run_val.is_cached = True
            run_val.last_updated_frame = store.simulation.frame_count

    # 5. Flush and force re-evaluation to guarantee reactive safety
    g_y = store.get_gravity_y()
    store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)

    # 6. Notify subscribers of transition
    store.notify()


class SnapshotTimeline:
    """
    Manages history of snapshots to support Undo, Redo, 
    and checkpoint timelines.
    """
    def __init__(self, store: RuntimeStore, max_history: int = 100) -> None:
        self.store: RuntimeStore = store
        self.max_history: int = max_history
        self.history: List[SimulationSnapshot] = []
        self.future: List[SimulationSnapshot] = []

    def record_checkpoint(self) -> None:
        """Saves current state in history and flushes future redo stacks."""
        snap = take_snapshot(self.store)
        self.history.append(snap)
        self.future.clear()

        # Enforce history boundaries
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def undo(self) -> bool:
        """
        Rolls back the store to the previous recorded checkpoint.
        Returns True if successful, False if no history remains.
        """
        if not self.history:
            return False

        # Take current snapshot to save in redo future
        curr = take_snapshot(self.store)
        self.future.append(curr)

        # Restore previous state
        prev = self.history.pop()
        restore_snapshot(self.store, prev)
        return True

    def redo(self) -> bool:
        """
        Rolls forward to the next recorded redo checkpoint.
        """
        if not self.future:
            return False

        # Save current to history
        curr = take_snapshot(self.store)
        self.history.append(curr)

        # Restore future checkpoint
        nxt = self.future.pop()
        restore_snapshot(self.store, nxt)
        return True

    def jump_to_frame(self, frame_index: int) -> bool:
        """
        Timeline scrubbing support. Jumps to the snapshot matching frame count.
        """
        for snap in self.history + self.future:
            if snap.simulation_state.get("frame_count") == frame_index:
                restore_snapshot(self.store, snap)
                return True
        return False
