from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.initialization.object_initializer")

"""
object_initializer.py
=====================
Production-grade SandboxObject Factory for EduSim.

This module initializes, normalizes, and validates individual physics objects 
from raw specification lists. 

It handles:
- ID generation (e.g. "object_1")
- Visual hint completion (colors, tints, opacity, z-indices) based on role
- Safe defaults matching defaults.py (mass, friction, restitution, density)
- Shape geometry validation
- Extensible object builder registration (allowing dynamic scenario composition 
  such as custom rocket or spring body configurations)
"""


import uuid
from typing import Any, Dict, List, Optional, Callable

from app.src.modules.sandbox.schemas.object_schema import (
    SandboxObject,
    ObjectRole,
    Vector2D,
    PhysicsProperties,
    VisualHints,
    RuntimeMetadata,
    EducationalMetadata
)
from app.src.modules.sandbox.initialization.normalizers import (
    normalize_number,
    normalize_vector_2d,
    normalize_object_geometry
)
from app.src.modules.sandbox.initialization.defaults import (
    DEFAULT_COLOR_CIRCLE,
    DEFAULT_COLOR_RECTANGLE,
    DEFAULT_COLOR_POLYGON,
    DEFAULT_COLOR_STATIC,
    DEFAULT_COLOR_SENSOR,
    DEFAULT_PHYSICS_PROPERTIES,
    DEFAULT_VISUAL_HINTS,
    DEFAULT_RUNTIME_METADATA
)


# Type definition for custom object builders/processors
ObjectBuilderFn = Callable[[Dict[str, Any]], Dict[str, Any]]


class ObjectInitializerRegistry:
    """
    Central registry for dynamic object builders. 
    Enables simulation-agnostic extensibility by letting custom domains 
    (e.g., fluid boundaries, active propulsion engines) register hooks.
    """
    def __init__(self) -> None:
        self._builders: Dict[str, ObjectBuilderFn] = {}

    def register(self, object_type: str, builder_fn: ObjectBuilderFn) -> None:
        """Registers a builder function for a specific semantic object_type."""
        self._builders[object_type.lower()] = builder_fn

    def get(self, object_type: str) -> Optional[ObjectBuilderFn]:
        """Retrieves a registered builder function."""
        return self._builders.get(object_type.lower())


# Central registry instance
object_registry = ObjectInitializerRegistry()


# ===========================================================================
# Default Builder & Pre-processors
# ===========================================================================

def apply_visual_defaults(obj_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Applies vibrant educational colors based on shape and role if missing."""
    visuals = obj_dict.get("visuals") or {}
    if not isinstance(visuals, dict):
        visuals = {}

    # Merge standard hints defaults
    for k, v in DEFAULT_VISUAL_HINTS.items():
        if k not in visuals:
            visuals[k] = v

    # Auto-color matching based on role and shape
    is_static = bool(obj_dict.get("is_static", False))
    role_str = str(obj_dict.get("role", "body")).strip().lower()
    shape_type = str(obj_dict.get("shape_type", "circle")).strip().lower()

    if not visuals.get("color"):
        if is_static or role_str == "anchor":
            visuals["color"] = DEFAULT_COLOR_STATIC
        elif role_str == "sensor":
            visuals["color"] = DEFAULT_COLOR_SENSOR
        else:
            # Match by shape
            if shape_type == "circle":
                visuals["color"] = DEFAULT_COLOR_CIRCLE
            elif shape_type == "rectangle":
                visuals["color"] = DEFAULT_COLOR_RECTANGLE
            else:
                visuals["color"] = DEFAULT_COLOR_POLYGON

    obj_dict["visuals"] = visuals
    return obj_dict


def apply_physics_defaults(obj_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Enforces standard Newtonian physics constraints and defaults."""
    physics = obj_dict.get("physics") or {}
    if not isinstance(physics, dict):
        physics = {}

    for k, v in DEFAULT_PHYSICS_PROPERTIES.items():
        if k not in physics:
            physics[k] = v

    # Mass vs staticity rules
    is_static = bool(obj_dict.get("is_static", False))
    if is_static:
        # Matter.js expects static objects to behave as infinite mass,
        # but the schema enforces mass > 0. We default static objects to standard 1.0kg 
        # (the static flag handles the physics engine locking).
        physics["mass"] = physics.get("mass") or 1.0
    else:
        physics["mass"] = normalize_number(physics.get("mass", 1.0), 1.0)
        
    physics["restitution"] = normalize_number(physics.get("restitution", 0.5), 0.5)
    physics["friction"] = normalize_number(physics.get("friction", 0.1), 0.1)
    physics["friction_static"] = normalize_number(physics.get("friction_static", 0.05), 0.05)
    physics["gravity_scale"] = normalize_number(physics.get("gravity_scale", 1.0), 1.0)

    # Handle sensor flag propagation
    role_str = str(obj_dict.get("role", "body")).strip().lower()
    if role_str == "sensor":
        physics["is_sensor"] = True

    obj_dict["physics"] = physics
    return obj_dict


def apply_runtime_defaults(obj_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures velocity, initial angles, and air resistance properties exist."""
    runtime = obj_dict.get("runtime") or {}
    if not isinstance(runtime, dict):
        runtime = {}

    for k, v in DEFAULT_RUNTIME_METADATA.items():
        if k not in runtime:
            runtime[k] = v

    runtime["initial_velocity"] = normalize_vector_2d(runtime.get("initial_velocity"))
    runtime["initial_angle"] = normalize_number(runtime.get("initial_angle", 0.0), 0.0)
    runtime["initial_angular_vel"] = normalize_number(runtime.get("initial_angular_vel", 0.0), 0.0)
    runtime["air_resistance"] = normalize_number(runtime.get("air_resistance", 0.01), 0.01)

    obj_dict["runtime"] = runtime
    return obj_dict


# ===========================================================================
# Main Entry Point
# ===========================================================================

def initialize_objects(raw_objects: List[Any]) -> List[SandboxObject]:
    """
    Transforms a raw, untrusted list of object payloads into normalized,
    validated, strongly-typed `SandboxObject` instances.
    """
    initialized_objects: List[SandboxObject] = []

    for idx, raw in enumerate(raw_objects):
        if not isinstance(raw, dict):
            continue

        # 1. Deep clone/copy to avoid mutating input params
        obj_dict = dict(raw)

        # 2. Insulate/generate primary IDs and names
        if not obj_dict.get("id"):
            obj_dict["id"] = f"object_{idx+1}_{str(uuid.uuid4())[:8]}"
        else:
            obj_dict["id"] = str(obj_dict["id"]).strip()

        if not obj_dict.get("name"):
            obj_dict["name"] = f"Object {idx+1}"

        # 3. Shape Classification & Normalization
        obj_dict = normalize_object_geometry(obj_dict)

        # Resolve role enum
        role_str = str(obj_dict.get("role", "body")).strip().lower()
        role = ObjectRole.BODY
        for preset in ObjectRole:
            if preset.value == role_str:
                role = preset
                break
        obj_dict["role"] = role

        # Ensure dynamic tags list
        if "tags" not in obj_dict or not isinstance(obj_dict["tags"], list):
            obj_dict["tags"] = []

        # 4. Check dynamic registry for custom processors
        object_type = str(obj_dict.get("object_type", "body")).strip()
        custom_builder = object_registry.get(object_type)
        if custom_builder:
            try:
                obj_dict = custom_builder(obj_dict)
            except Exception as e:
                logger.error(f"Custom builder failed for type {object_type}: {e}")

        # 5. Core defaults & conversions
        obj_dict = apply_visual_defaults(obj_dict)
        obj_dict = apply_physics_defaults(obj_dict)
        obj_dict = apply_runtime_defaults(obj_dict)

        # Education block
        edu = obj_dict.get("education") or {}
        if not isinstance(edu, dict):
            edu = {}
        
        # 6. Schema instantiation & strict validation
        physics_model = PhysicsProperties(**obj_dict["physics"])
        visuals_model = VisualHints(**obj_dict["visuals"])
        runtime_model = RuntimeMetadata(**obj_dict["runtime"])
        education_model = EducationalMetadata(
            concept_tags=edu.get("concept_tags", []),
            observable_ids=edu.get("observable_ids", []),
            notes=edu.get("notes"),
            difficulty=normalize_number(edu.get("difficulty", 1), 1)
        )

        # Coordinate formats
        pos_vec = normalize_vector_2d(obj_dict.get("position"))
        position = Vector2D(x=pos_vec["x"], y=pos_vec["y"])

        # Handle vertices mapping for polygons
        vertices_list = None
        if obj_dict.get("shape_type") == "polygon" and obj_dict.get("vertices"):
            vertices_list = [Vector2D(x=v["x"], y=v["y"]) for v in obj_dict["vertices"]]

        sandbox_obj = SandboxObject(
            id=obj_dict["id"],
            name=obj_dict["name"],
            shape_type=obj_dict["shape_type"],
            object_type=object_type,
            role=role,
            position=position,
            width=obj_dict.get("width"),
            height=obj_dict.get("height"),
            radius=obj_dict.get("radius"),
            vertices=vertices_list,
            is_static=bool(obj_dict.get("is_static", False)),
            tags=obj_dict["tags"],
            physics=physics_model,
            visuals=visuals_model,
            runtime=runtime_model,
            education=education_model
        )
        initialized_objects.append(sandbox_obj)

    return initialized_objects
