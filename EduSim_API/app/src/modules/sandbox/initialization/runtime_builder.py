"""
runtime_builder.py
==================
Frontend Runtime Payload Builder for EduSim.

This module serializes the validated `SandboxSchema` into a highly optimized,
frontend-compatible JSON payload. It acts as the final "code generation" phase 
of our physics compiler, mapping backend Pydantic states to standard JSON contracts 
consumable by generic Matter.js/PixiJS runtime engines.
"""


from __future__ import annotations
import json
from typing import Any, Dict, Optional
from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema


class RuntimeBuilder:
    """
    Transforms backend SandboxSchema configurations into serialized contracts 
    for the Matter.js / PixiJS frontend runtime.
    """

    @staticmethod
    def build_runtime_payload(sandbox: SandboxSchema) -> Dict[str, Any]:
        """
        Serializes and prepares the final runtime payload.
        Ensures Pydantic models are parsed into native dicts, cleans up 
        any legacy fields, and configures the standard runtime contract structure.
        """
        # 1. Standard model dump (resolves enums and serializes types recursively)
        raw_dict = sandbox.model_dump(mode="json")

        # 2. Extract structured components
        environment = raw_dict.get("environment", {})
        objects = raw_dict.get("objects", [])
        constraints = raw_dict.get("constraints", [])
        relationships = raw_dict.get("relationships", [])
        controls = raw_dict.get("controls", [])
        observables = raw_dict.get("observables", [])
        metadata = raw_dict.get("metadata", {})

        # 3. Create generic 'runtime' state block for Matter.js frame coordinator
        # The frontend reads this to set initial simulation step sizes, bounds, and locks.
        runtime_config = metadata.get("runtime_config", {})
        runtime_state = {
            "is_paused": True, # Always spawn sandboxes initially paused
            "current_frame": 0,
            "simulated_time_s": 0.0,
            "time_delta": 1.0 / float(runtime_config.get("max_fps", 60)),
            "substeps": runtime_config.get("substeps", 1),
            "speed_multiplier": runtime_config.get("simulation_speed", 1.0),
            "state_sync_token": None,
            "bounds": {
                "min": {"x": 0.0, "y": 0.0},
                "max": {
                    "x": float(runtime_config.get("canvas_width", 1280)),
                    "y": float(runtime_config.get("canvas_height", 720))
                }
            }
        }

        # 4. Construct output payload in generic frontend contract order
        payload = {
            "metadata": {
                "id": metadata.get("id"),
                "schema_version": metadata.get("schema_version", "2.0.0"),
                "created_at": metadata.get("created_at"),
                "updated_at": metadata.get("updated_at"),
                "author": metadata.get("author", "system"),
                "is_template": metadata.get("is_template", False),
                "ai_context": metadata.get("ai_context", {}),
                "tutor_context": metadata.get("tutor_context", {})
            },
            "environment": environment,
            "objects": objects,
            "constraints": constraints,
            "relationships": relationships,
            "controls": controls,
            "observables": observables,
            "runtime": runtime_state
        }

        return payload

    @classmethod
    def serialize_to_json(cls, sandbox: SandboxSchema, indent: Optional[int] = None) -> str:
        """Helper to output as standard compressed or formatted JSON string."""
        payload = cls.build_runtime_payload(sandbox)
        return json.dumps(payload, indent=indent)
