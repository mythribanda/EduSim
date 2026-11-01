"""
control_serializer.py
======================
Interactive User Control Widgets Serializer for EduSim.

Converts static UI control bindings (mass sliders, gravity toggles, launch 
buttons) combined with live runtime states and Socratic interaction locks 
into clean generic frontend widget contracts.
"""


from __future__ import annotations
from typing import Any, Dict, List
from app.src.modules.sandbox.schemas.control_schema import SandboxControl
from app.src.modules.sandbox.state.runtime_store import RuntimeStore


class ControlSerializer:
    """
    Translates sandbox controller schemas and active lock statuses into 
    frontend-ready widget specifications.
    """

    @classmethod
    def resolve_current_value(cls, store: RuntimeStore, binding: Any) -> Any:
        """
        Queries the authoritative RuntimeStore to fetch the actual, 
        live numerical or boolean value currently bound to the slider/toggle.
        """
        if not binding:
            return None

        # 1. Bound to live observable
        obs_id = getattr(binding, "observable_id", None)
        if obs_id:
            if obs_id in store.observables.values:
                return round(float(store.observables.values[obs_id].value), 4)

        scope = getattr(binding, "scope", "")
        # Standardize scopes in case of string vs Enum
        scope_str = scope.value if hasattr(scope, "value") else str(scope)
        prop_path = getattr(binding, "property_path", "") or ""
        prop_path_lower = prop_path.lower()

        # 2. Scope = OBJECT
        if scope_str == "object" and getattr(binding, "object_id", None):
            obj_id = binding.object_id
            if obj_id in store.objects:
                obj = store.objects[obj_id]
                if "mass" in prop_path_lower:
                    return round(float(obj.mass), 4)
                elif "velocity" in prop_path_lower or "vel" in prop_path_lower:
                    if "x" in prop_path_lower:
                        return round(float(obj.velocity.x), 4)
                    if "y" in prop_path_lower:
                        return round(float(obj.velocity.y), 4)
                elif "position" in prop_path_lower or "pos" in prop_path_lower:
                    if "x" in prop_path_lower:
                        return round(float(obj.position.x), 4)
                    if "y" in prop_path_lower:
                        return round(float(obj.position.y), 4)
                elif "angle" in prop_path_lower:
                    return round(float(obj.angle), 4)
                elif "static" in prop_path_lower:
                    return obj.is_static
                elif "visible" in prop_path_lower:
                    return obj.is_visible

        # 3. Scope = ENVIRONMENT
        elif scope_str == "environment":
            if "gravity" in prop_path_lower:
                return round(float(store.get_gravity_y()), 4)
            elif "wind" in prop_path_lower:
                return round(float(getattr(store.simulation, "wind_x", 0.0)), 4)

        # 4. Scope = SIMULATION
        elif scope_str == "simulation":
            if "playback_speed" in prop_path_lower or "speed" in prop_path_lower:
                return round(float(store.simulation.playback_speed), 4)
            elif "paused" in prop_path_lower:
                return store.simulation.is_paused

        return None

    @classmethod
    def serialize_control(
        cls,
        schema: SandboxControl,
        store: RuntimeStore
    ) -> Dict[str, Any]:
        """
        Combines static control layouts (ranges, labels, widget types) with 
        its live resolved sandbox value and active Socratic tutorial lock status.
        """
        binding = schema.binding
        
        # 1. Resolve live slider/toggle values
        live_value = cls.resolve_current_value(store, binding)

        # 2. Determine lock states (controls_edit global lock or widget-specific locks)
        is_locked = (
            store.interaction.interaction_locks.get("controls_edit", False) or
            store.interaction.interaction_locks.get(schema.id, False)
        )

        # 3. Serialize widget configs
        config = schema.widget_config
        config_dict = {}
        if config:
            if hasattr(config, "model_dump"):
                config_dict = config.model_dump()
            elif isinstance(config, dict):
                config_dict = dict(config)

        # 4. Serialize binding details
        binding_dict = {}
        if binding:
            binding_dict = {
                "scope": binding.scope.value if hasattr(binding.scope, "value") else str(binding.scope),
                "object_id": getattr(binding, "object_id", None),
                "property_path": getattr(binding, "property_path", None),
                "observable_id": getattr(binding, "observable_id", None),
                "action": getattr(binding, "action", None)
            }

        # 5. Assemble unified generic contract
        payload = {
            "id": schema.id,
            "label": schema.label,
            "widget_type": schema.widget_type.value if hasattr(schema.widget_type, "value") else str(schema.widget_type),
            "widget_config": config_dict,
            "binding": binding_dict,
            "current_value": live_value if live_value is not None else config_dict.get("default_value"),
            "is_enabled": schema.is_enabled and not is_locked,
            "is_visible": schema.is_visible,
            "is_locked": is_locked,
            "group": schema.group or "General Controls",
            "educational_impact": list(schema.educational_impact) if schema.educational_impact else [],
            "tooltip": schema.tooltip,
            "display_order": schema.display_order
        }

        return payload

    @classmethod
    def serialize_controls(
        cls,
        schemas: List[SandboxControl],
        store: RuntimeStore
    ) -> List[Dict[str, Any]]:
        """Serializes multiple UI controls, sorting them by display order."""
        serialized_list = []
        for ctrl in schemas:
            serialized_list.append(cls.serialize_control(ctrl, store))
            
        # Order by display order ascending
        return sorted(serialized_list, key=lambda x: (x["group"], x["display_order"]))
