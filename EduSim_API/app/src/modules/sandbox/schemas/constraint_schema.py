"""
constraint_schema.py
====================
Universal physics constraint schema for EduSim sandbox_v2.

ARCHITECTURE PHILOSOPHY
-----------------------
A constraint is a mathematical relationship BETWEEN two bodies (or a body and
a fixed world-space point) that restricts their relative motion.  Matter.js
represents these as `Matter.Constraint`.

One schema — `SandboxConstraint` — covers every current and future constraint
type:
  - distance rope      (pendulum string, tether)
  - spring             (Hooke's law restoring force)
  - pivot / hinge      (pin joint, axle)
  - pulley             (two-rope mechanical advantage)
  - slider / prismatic (constrained linear motion)
  - custom             (future types via `extra_params`)

EXTENSIBILITY MECHANISM
-----------------------
`constraint_type` is a free string, not a closed enum.  New types are added
by the service layer without any schema rewrite.

`extra_params: Dict[str, Any]` absorbs future parameters (e.g., pulley ratio,
motor speed, break threshold) without adding new optional fields.

ANTI-PATTERNS AVOIDED
---------------------
- No SpringConstraintSchema, RopeConstraintSchema, etc.
- No runtime physics integration (length updates, force accumulation).
- No hardcoded scenario assumptions.
"""


from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Anchor point (local-space offset on a body)
# ---------------------------------------------------------------------------

class ConstraintAnchor(BaseModel):
    """
    Defines where a constraint attaches to a body, expressed as an offset
    from the body's centre of mass in local body-space coordinates (pixels).

    world_point is used when the constraint attaches to a fixed world-space
    position (e.g., a pivot pin screwed to the ceiling) rather than a body.
    Exactly one of `body_id` + `offset` OR `world_point` must be set per side.
    """
    body_id: Optional[str] = Field(default=None, description="ID of the SandboxObject this anchor belongs to")
    offset: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="Local-space offset from the body centre (px)"
    )
    world_point: Optional[Dict[str, float]] = Field(
        default=None,
        description="Fixed world-space point; set when not attaching to a body"
    )

    @model_validator(mode="after")
    def check_anchor_target(self) -> "ConstraintAnchor":
        has_body = self.body_id is not None
        has_world = self.world_point is not None
        if not has_body and not has_world:
            raise ValueError("ConstraintAnchor must specify either 'body_id' or 'world_point'.")
        if has_body and has_world:
            raise ValueError("ConstraintAnchor cannot have both 'body_id' and 'world_point'.")
        return self


# ---------------------------------------------------------------------------
# Educational metadata for constraints
# ---------------------------------------------------------------------------

class ConstraintEducation(BaseModel):
    """
    Tutor-facing metadata attached to a constraint.
    Invisible to Matter.js runtime.

    formula     — the physics formula this constraint embodies
    concept_tags — curriculum concepts illustrated (e.g. "tension", "hookes_law")
    display_name — label shown in the sandbox UI (e.g. "String", "Spring")
    """
    formula: Optional[str]       = Field(default=None, description="Physics formula, e.g. 'F = -kx'")
    concept_tags: List[str]      = Field(default_factory=list)
    display_name: Optional[str]  = Field(default=None, description="Human-readable constraint label")
    notes: Optional[str]         = Field(default=None, description="Tutor annotation")


# ---------------------------------------------------------------------------
# Core Schema
# ---------------------------------------------------------------------------

class SandboxConstraint(BaseModel):
    """
    THE universal constraint.

    Covers ropes, springs, pivots, hinges, pulleys, sliders, and any future
    constraint through the open `constraint_type` string and `extra_params`.

    KEY FIELDS
    ----------
    id               — unique within the sandbox
    constraint_type  — semantic type string, e.g. "distance", "spring", "pivot",
                       "pulley", "slider", "custom"
    anchor_a         — attachment point on the first body (or world space)
    anchor_b         — attachment point on the second body (or world space)
    stiffness        — [0, 1] — 1.0 = perfectly rigid, < 1 = springy
    damping          — energy dissipation coefficient [0, 1]
    length           — target rest length (px); None = current distance at spawn
    is_visible       — whether to draw the constraint as a line/spring graphic
    extra_params     — open dict for future or type-specific parameters
    education        — tutor metadata

    MATTER.JS MAPPING
    -----------------
    stiffness → Matter.Constraint.stiffness
    damping   → Matter.Constraint.damping
    length    → Matter.Constraint.length
    anchor_a  → Matter.Constraint.bodyA + pointA
    anchor_b  → Matter.Constraint.bodyB + pointB
    """
    model_config = ConfigDict(use_enum_values=True)

    # --- Identity ---
    id: str              = Field(..., description="Unique constraint ID")
    constraint_type: str = Field(..., description="Type: 'distance' | 'spring' | 'pivot' | 'pulley' | 'slider' | 'custom'")

    # --- Attachment ---
    anchor_a: ConstraintAnchor = Field(..., description="First attachment point")
    anchor_b: ConstraintAnchor = Field(..., description="Second attachment point")

    # --- Physics parameters ---
    stiffness: float         = Field(default=1.0,  ge=0, le=1,  description="Constraint stiffness [0,1]")
    damping: float           = Field(default=0.1,  ge=0, le=1,  description="Damping coefficient [0,1]")
    length: Optional[float]  = Field(default=None, ge=0,         description="Rest length in px; None=auto from spawn positions")

    # --- Rendering ---
    is_visible: bool = Field(default=True, description="Render the constraint as a line or spring graphic")

    # --- Extensibility ---
    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open dict for type-specific or future parameters, e.g. {'pulley_ratio': 2.0}"
    )

    # --- Education ---
    education: ConstraintEducation = Field(default_factory=ConstraintEducation)

    @model_validator(mode="after")
    def validate_pulley_params(self) -> "SandboxConstraint":
        """
        Light constraint-type–specific validation.
        Pulley constraints require a pulley_ratio in extra_params.
        """
        if self.constraint_type == "pulley" and "pulley_ratio" not in self.extra_params:
            # Default to mechanical advantage of 1 if not supplied.
            self.extra_params["pulley_ratio"] = 1.0
        return self
