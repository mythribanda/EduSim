"""
selectors.py
============
Authoritative Query Selectors for the EduSim Runtime Store.

This module houses reusable, optimized query selectors to retrieve nested 
state values from the RuntimeStore. 

Using selectors prevents structural coupling (deep dot-path lookups) in tutor 
dialogues or rendering pipelines, and supports future optimization caches.
"""


from __future__ import annotations
from typing import List, Dict, Optional
from app.src.modules.sandbox.state.runtime_store import RuntimeStore
from app.src.modules.sandbox.state.object_state import ObjectRuntimeState, StateVector2D
from app.src.modules.sandbox.schemas.relationship_schema import EducationalRelationship


def get_object_state(store: RuntimeStore, object_id: str) -> Optional[ObjectRuntimeState]:
    """Retrieves an object's physical runtime parameters by ID."""
    return store.objects.get(object_id)


def get_object_velocity(store: RuntimeStore, object_id: str) -> Optional[StateVector2D]:
    """Returns the live velocity vector of a target object."""
    obj = get_object_state(store, object_id)
    return obj.velocity if obj else None


def get_selected_object(store: RuntimeStore) -> Optional[ObjectRuntimeState]:
    """Retrieves the physical state parameters of the currently selected body."""
    sel_id = store.interaction.selected_object_id
    if not sel_id:
        return None
    return get_object_state(store, sel_id)


def get_observable_value(store: RuntimeStore, observable_id: str) -> float:
    """
    Returns the current calculated float value of a specific educational observable.
    If evaluation is needed, resolves using the cached manager.
    """
    run_val = store.observables.values.get(observable_id)
    if run_val:
        return run_val.value
    return 0.0


def get_total_energy(store: RuntimeStore) -> float:
    """
    Calculates the aggregate Mechanical Energy (Kinetic + Gravitational Potential) 
    across all active non-static physical bodies.
    """
    total = 0.0
    g_y = store.get_gravity_y()
    for obj in store.objects.values():
        if not obj.is_static:
            total += obj.get_kinetic_energy()
            total += obj.get_potential_energy(g_y)
    return total


def get_active_relationships(store: RuntimeStore) -> List[EducationalRelationship]:
    """
    Retrieves list of active schemas containing formula bindings.
    """
    return store.schema.relationships


def get_runtime_bounds(store: RuntimeStore) -> Dict[str, float]:
    """Returns canvas width and height boundary specs."""
    rc = store.schema.metadata.runtime_config
    return {
        "width": float(rc.canvas_width),
        "height": float(rc.canvas_height)
    }
