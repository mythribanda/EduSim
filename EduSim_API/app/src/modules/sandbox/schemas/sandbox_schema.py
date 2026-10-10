"""
sandbox_schema.py
=================
THE Universal Sandbox Contract — the root schema for EduSim sandbox_v2.

ARCHITECTURE PHILOSOPHY
-----------------------
`SandboxSchema` is the single, authoritative data structure that:

1. The BACKEND produces (service.py → initializer → serializer).
2. The FRONTEND consumes to build the Matter.js world and PixiJS scene.
3. The TUTOR AI reads to understand the current scenario.
4. The RAG system uses for context injection.
5. The VALIDATOR checks for logical consistency.
6. The PERSISTENCE layer saves/loads.

It is THE contract between every subsystem in EduSim.

COMPOSITION
-----------
SandboxSchema is a composition of all sub-schemas:

  objects        — list of SandboxObject (physics bodies)
  constraints    — list of SandboxConstraint (joints, springs, ropes)
  environment    — SandboxEnvironment (gravity, wind, atmosphere, …)
  relationships  — list of EducationalRelationship (for Tutor AI)
  observables    — list of SandboxObservable (what to track and display)
  controls       — list of SandboxControl (UI interaction declarations)
  metadata       — SandboxMetadata (versioning, authorship, AI context)

DESIGN PRINCIPLES
-----------------
1. COMPOSABLE: Any subset of these six components can be non-empty for a
   given scenario.  A minimal sandbox needs only objects + environment.

2. VERSIONABLE: `schema_version` enables forward/backward compatibility.

3. TUTOR-AWARE: `relationships` and `observables` are first-class citizens
   at the root level — not buried inside objects.

4. AI-FRIENDLY: `metadata.ai_context` is a structured block the AI uses
   when generating or modifying the sandbox state.

5. PERSISTENCE-READY: Can be round-tripped through JSON with `model_dump()` /
   `model_validate()`.

6. FRONTEND-COMPATIBLE: Serialised form is a plain JSON object the frontend
   can parse without any special handling.

ANTI-PATTERNS AVOIDED
---------------------
- No subclasses per scenario (PendulumSandbox, RocketSandbox, etc.)
- No runtime execution logic.
- No flat untyped Dict for core fields.
- No version-less schema (breaks persistence).
"""


from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .constraint_schema import SandboxConstraint
from .control_schema import SandboxControl
from .environment_schema import SandboxEnvironment
from .object_schema import SandboxObject
from .observable_schema import SandboxObservable
from .relationship_schema import EducationalRelationship


# ---------------------------------------------------------------------------
# Metadata sub-schema
# ---------------------------------------------------------------------------

class AIContext(BaseModel):
    """
    Structured context block that the AI reads when generating or modifying
    a sandbox.  It is NOT used by the physics engine or renderer.

    original_prompt    — the user or system prompt that produced this sandbox
    scenario_name      — descriptive scenario title (e.g. "Double Pendulum")
    scenario_tags      — semantic scenario tags for retrieval (e.g. ["oscillation"])
    curriculum_topics  — curriculum topics this sandbox addresses
    difficulty         — overall scenario difficulty [1, 5]
    generation_model   — which LLM generated this sandbox state
    generation_notes   — freeform notes from the AI about design decisions
    """
    original_prompt: Optional[str]     = Field(default=None)
    scenario_name: str                 = Field(default="Untitled Scenario")
    scenario_tags: List[str]           = Field(default_factory=list)
    curriculum_topics: List[str]       = Field(default_factory=list)
    difficulty: int                    = Field(default=1, ge=1, le=5)
    generation_model: Optional[str]    = Field(default=None)
    generation_notes: Optional[str]    = Field(default=None)
    extra: Dict[str, Any]             = Field(default_factory=dict)


class TutorContext(BaseModel):
    """
    Tutor-facing session metadata.

    learning_objectives  — what the student should understand after this scenario
    key_concepts         — primary physics concepts being demonstrated
    prerequisite_ids     — sandbox or relationship IDs the student should know first
    assessment_questions — pre-defined assessment questions linked to this sandbox
    """
    learning_objectives: List[str]   = Field(default_factory=list)
    key_concepts: List[str]          = Field(default_factory=list)
    prerequisite_ids: List[str]      = Field(default_factory=list)
    assessment_questions: List[str]  = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    """
    Frontend runtime configuration hints.

    canvas_width / canvas_height — target canvas dimensions in pixels
    pixels_per_meter             — scale factor; e.g. 100 px = 1 m
    simulation_speed             — initial time-scale multiplier (1.0 = real time)
    max_fps                      — target frame rate cap
    show_debug_overlay           — render Matter.js wireframes and vectors
    enable_sleeping              — allow bodies to sleep when inactive
    substeps                     — physics substeps per frame (higher = more accurate)
    """
    canvas_width: int        = Field(default=1280, gt=0)
    canvas_height: int       = Field(default=720,  gt=0)
    pixels_per_meter: float  = Field(default=100.0, gt=0, description="Scale: px per SI metre")
    simulation_speed: float  = Field(default=1.0,   gt=0, description="Time-scale multiplier")
    max_fps: int             = Field(default=60,    gt=0)
    show_debug_overlay: bool = Field(default=False)
    enable_sleeping: bool    = Field(default=True)
    substeps: int            = Field(default=1, ge=1, le=10)


class SandboxMetadata(BaseModel):
    """
    Root-level metadata for the sandbox.

    id              — globally unique sandbox ID (UUID4)
    schema_version  — semver string; used for migration compatibility
    created_at      — ISO 8601 UTC timestamp
    updated_at      — ISO 8601 UTC timestamp
    author          — user or system that created this sandbox
    is_template     — True if this is a reusable template primitive
    ai_context      — AI generation context
    tutor_context   — Tutor/curriculum metadata
    runtime_config  — Frontend runtime configuration
    """
    id: str                    = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str        = Field(default="2.0.0", description="Semver schema version")
    created_at: str            = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC creation timestamp"
    )
    updated_at: str            = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC last-modified timestamp"
    )
    author: str                = Field(default="system", description="Creator: 'user', 'ai', or user ID")
    is_template: bool          = Field(default=False,     description="True if this is a reusable template")
    ai_context: AIContext      = Field(default_factory=AIContext)
    tutor_context: TutorContext = Field(default_factory=TutorContext)
    runtime_config: RuntimeConfig = Field(default_factory=RuntimeConfig)


# ---------------------------------------------------------------------------
# Root Schema
# ---------------------------------------------------------------------------

class SandboxSchema(BaseModel):
    """
    THE Universal Sandbox Contract.

    This is the root output of the EduSim backend and the root input of the
    EduSim frontend.  Every physics scenario — from a single pendulum to a
    multi-stage rocket with pulley-driven landing gear — is expressed as an
    instance of this schema.

    COMPONENT SUMMARY
    -----------------
    metadata      — versioning, AI context, tutor context, runtime hints
    environment   — world conditions (gravity, wind, atmosphere, …)
    objects       — physics bodies
    constraints   — joints, springs, ropes, hinges, pulleys
    relationships — educational physics relationships (for Tutor AI)
    observables   — measurable quantities (for UI and Tutor)
    controls      — UI widget declarations (for frontend rendering)

    LIFECYCLE
    ---------
    1. service.py generates a SandboxSchema from a prompt + templates.
    2. validators/sandbox_validator.py validates it.
    3. serializers/sandbox_serializer.py converts it to frontend JSON.
    4. Frontend ingests it, builds the Matter.js world, and starts the loop.
    5. State updates flow back via the state-sync API as partial updates.
    """

    metadata: SandboxMetadata                   = Field(default_factory=SandboxMetadata)
    environment: SandboxEnvironment             = Field(default_factory=SandboxEnvironment)
    objects: List[SandboxObject]                = Field(default_factory=list)
    constraints: List[SandboxConstraint]        = Field(default_factory=list)
    relationships: List[EducationalRelationship] = Field(default_factory=list)
    observables: List[SandboxObservable]        = Field(default_factory=list)
    controls: List[SandboxControl]              = Field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Cross-reference validators (structural integrity)
    # ---------------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_constraint_references(self) -> "SandboxSchema":
        """
        Every constraint anchor that references a body_id must resolve to a
        real SandboxObject in this sandbox.
        """
        object_ids = {obj.id for obj in self.objects}
        for constraint in self.constraints:
            for anchor_name, anchor in [("anchor_a", constraint.anchor_a), ("anchor_b", constraint.anchor_b)]:
                if anchor.body_id and anchor.body_id not in object_ids:
                    raise ValueError(
                        f"Constraint '{constraint.id}' {anchor_name}.body_id='{anchor.body_id}' "
                        f"does not reference a known SandboxObject."
                    )
        return self

    @model_validator(mode="after")
    def validate_observable_target_references(self) -> "SandboxSchema":
        """
        Every observable that targets object IDs must resolve to known objects.
        """
        object_ids = {obj.id for obj in self.objects}
        for observable in self.observables:
            for obj_id in observable.target_object_ids:
                if obj_id not in object_ids:
                    raise ValueError(
                        f"Observable '{observable.id}' targets unknown object '{obj_id}'."
                    )
        return self

    @model_validator(mode="after")
    def validate_control_object_references(self) -> "SandboxSchema":
        """
        Controls with OBJECT scope must reference a known SandboxObject.
        """
        object_ids = {obj.id for obj in self.objects}
        for control in self.controls:
            if control.binding.scope == "object" and control.binding.object_id:
                if control.binding.object_id not in object_ids:
                    raise ValueError(
                        f"Control '{control.id}' binds to unknown object '{control.binding.object_id}'."
                    )
        return self

    @model_validator(mode="after")
    def validate_relationship_object_references(self) -> "SandboxSchema":
        """
        Relationships may reference objects that don't yet exist (e.g., global
        relationships), but non-empty object_ids lists are validated.
        """
        object_ids = {obj.id for obj in self.objects}
        for rel in self.relationships:
            for obj_id in rel.object_ids:
                if obj_id not in object_ids:
                    raise ValueError(
                        f"Relationship '{rel.id}' references unknown object '{obj_id}'."
                    )
        return self

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "SandboxSchema":
        """
        All top-level IDs must be unique across their own collections.
        Cross-collection ID uniqueness is not enforced (objects and constraints
        may share namespaced prefixes, e.g. 'spring_1').
        """
        self._check_unique("objects", [o.id for o in self.objects])
        self._check_unique("constraints", [c.id for c in self.constraints])
        self._check_unique("observables", [o.id for o in self.observables])
        self._check_unique("controls", [c.id for c in self.controls])
        self._check_unique("relationships", [r.id for r in self.relationships])
        return self

    @staticmethod
    def _check_unique(collection_name: str, ids: List[str]) -> None:
        seen: set = set()
        for item_id in ids:
            if item_id in seen:
                raise ValueError(
                    f"Duplicate ID '{item_id}' found in '{collection_name}' collection."
                )
            seen.add(item_id)

    # ---------------------------------------------------------------------------
    # Convenience helpers (read-only, no side effects)
    # ---------------------------------------------------------------------------

    def get_object(self, object_id: str) -> Optional[SandboxObject]:
        """Return a SandboxObject by ID, or None if not found."""
        return next((o for o in self.objects if o.id == object_id), None)

    def get_constraint(self, constraint_id: str) -> Optional[SandboxConstraint]:
        """Return a SandboxConstraint by ID, or None if not found."""
        return next((c for c in self.constraints if c.id == constraint_id), None)

    def get_observable(self, observable_id: str) -> Optional[SandboxObservable]:
        """Return a SandboxObservable by ID, or None if not found."""
        return next((o for o in self.observables if o.id == observable_id), None)

    def get_objects_by_tag(self, tag: str) -> List[SandboxObject]:
        """Return all SandboxObjects that carry a specific tag."""
        return [o for o in self.objects if tag in o.tags]

    def get_relationships_for_object(self, object_id: str) -> List[EducationalRelationship]:
        """Return all educational relationships that involve a given object."""
        return [r for r in self.relationships if object_id in r.object_ids]
