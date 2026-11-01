"""
mutations.py
============
Controlled State Mutations for the EduSim Runtime Store.

All live sandbox state updates must flow exclusively through mutations. 
This guarantees transactional safety, defensive validation, caching flushes, 
reactive evaluations, and notifications for subscribers.
"""


from __future__ import annotations
from typing import Any, Optional
from app.src.modules.sandbox.state.runtime_store import RuntimeStore


def pause_simulation(store: RuntimeStore) -> None:
    """Halts execution clock."""
    store.simulation.pause()
    store.notify()


def resume_simulation(store: RuntimeStore) -> None:
    """Starts execution clock."""
    store.simulation.resume()
    store.notify()


def update_mass(store: RuntimeStore, object_id: str, new_mass: float) -> None:
    """
    Mutates body mass.
    Triggers caching flushes, derived educational observable recalculations,
    and dispatches live notifications to external observers.
    """
    obj = store.objects.get(object_id)
    if not obj:
        raise ValueError(f"Target object '{object_id}' not found for mass update.")

    # Defensive validation
    validated_mass = max(0.001, float(new_mass))
    
    # 1. Update Object State
    obj.mass = validated_mass
    
    # Update inertia proportionally (fallback calculation cylinder)
    if obj.inertia > 0.0:
        obj.inertia = (obj.inertia / (obj.mass if obj.mass > 0 else 1.0)) * validated_mass

    # 2. Invalidate caching & evaluate derived observable chains (reactive recomputation)
    store.observables.invalidate_cache()
    g_y = store.get_gravity_y()
    store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)

    # 3. Dispatch changes to frontend synchronization & subscribers
    store.notify()


def apply_force(store: RuntimeStore, object_id: str, fx: float, fy: float) -> None:
    """
    Applies translational force to a dynamic physical body.
    Increments net force vectors and updates dynamic acceleration components.
    """
    obj = store.objects.get(object_id)
    if not obj:
        return

    if obj.is_static:
        return

    # Increment forces
    obj.net_force.x += float(fx)
    obj.net_force.y += float(fy)

    # Recompute immediate linear acceleration (a = F / m)
    obj.acceleration.x = obj.net_force.x / obj.mass
    obj.acceleration.y = obj.net_force.y / obj.mass

    # Invalidate caching & evaluate observables
    store.observables.invalidate_cache()
    g_y = store.get_gravity_y()
    store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)
    store.notify()


def update_velocity(store: RuntimeStore, object_id: str, vx: float, vy: float) -> None:
    """Directly alters physical body speed parameters."""
    obj = store.objects.get(object_id)
    if not obj or obj.is_static:
        return

    obj.velocity.x = float(vx)
    obj.velocity.y = float(vy)

    # Invalidate caching & evaluate observables
    store.observables.invalidate_cache()
    g_y = store.get_gravity_y()
    store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)
    store.notify()


def set_position(store: RuntimeStore, object_id: str, x: float, y: float) -> None:
    """Teleports body coordinates to designated locations."""
    obj = store.objects.get(object_id)
    if not obj:
        return

    obj.position.x = float(x)
    obj.position.y = float(y)

    # Invalidate caching & evaluate observables
    store.observables.invalidate_cache()
    g_y = store.get_gravity_y()
    store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)
    store.notify()


def select_object_mutation(store: RuntimeStore, object_id: Optional[str]) -> None:
    """Alters focus targets and resets highlight states."""
    # Deselect previous selection
    prev_id = store.interaction.selected_object_id
    if prev_id:
        prev_obj = store.objects.get(prev_id)
        if prev_obj:
            prev_obj.is_selected = False

    # Select new object
    store.interaction.select_object(object_id)
    if object_id:
        obj = store.objects.get(object_id)
        if obj:
            obj.is_selected = True

    store.notify()


def update_widget_mutation(store: RuntimeStore, control_id: str, value: Any) -> None:
    """Alters UI slider selection values and propagates to mapped bindings."""
    store.interaction.update_widget(control_id, value)

    # Traverse bindings to locate destination schemas
    control_schema = next((c for c in store.schema.controls if c.id == control_id), None)
    if control_schema and control_schema.binding:
        binding = control_schema.binding
        
        # Apply to specific object parameters
        if binding.scope == "object" and binding.object_id:
            if "mass" in str(binding.property_path).lower():
                update_mass(store, binding.object_id, float(value))
            elif "velocity" in str(binding.property_path).lower() or "vel" in str(binding.property_path).lower():
                # Direct speed update
                obj = store.objects.get(binding.object_id)
                if obj:
                    update_velocity(store, binding.object_id, float(value), obj.velocity.y)
        
        # Apply to global environment fields
        elif binding.scope == "environment":
            if "gravity" in str(binding.property_path).lower():
                store.schema.environment.gravity.y = float(value)
                
                # Invalidate and propagate
                store.observables.invalidate_cache()
                g_y = store.get_gravity_y()
                store.observables.evaluate_all(store.objects, g_y, store.simulation.frame_count)
                store.notify()
