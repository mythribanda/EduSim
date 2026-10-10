"""
schemas/__init__.py
===================
Public API for the EduSim sandbox_v2 schemas package.

Import from here in all other modules to avoid deep relative imports
and to make refactoring easier — only this file needs updating if a
module is renamed.

Usage:
    from app.src.modules.sandbox.schemas import SandboxSchema, SandboxObject
"""

from .object_schema import (
    SandboxObject,
    ObjectRole,
    ShapeType,
    PhysicsProperties,
    VisualHints,
    RuntimeMetadata,
    EducationalMetadata,
    Vector2D,
)

from .constraint_schema import (
    SandboxConstraint,
    ConstraintAnchor,
    ConstraintEducation,
)

from .environment_schema import (
    SandboxEnvironment,
    GravityField,
    WindField,
    AtmosphereField,
    MagneticField,
    FluidField,
    LightingEnvironment,
    AtmosphereType,
)

from .relationship_schema import (
    EducationalRelationship,
    VariableBinding,
    RelationshipScope,
    CurriculumLevel,
)

from .observable_schema import (
    SandboxObservable,
    ObservableType,
    ObservableDisplayMode,
    ObservableDisplay,
    ObservableTutorMeta,
    ObservableSourceBinding,
    AggregateFunction,
)

from .control_schema import (
    SandboxControl,
    ControlBinding,
    ControlScope,
    WidgetType,
    SliderConfig,
    SelectConfig,
    SelectOption,
)

from .sandbox_schema import (
    SandboxSchema,
    SandboxMetadata,
    AIContext,
    TutorContext,
    RuntimeConfig,
)

__all__ = [
    # --- Object ---
    "SandboxObject",
    "ObjectRole",
    "ShapeType",
    "PhysicsProperties",
    "VisualHints",
    "RuntimeMetadata",
    "EducationalMetadata",
    "Vector2D",
    # --- Constraint ---
    "SandboxConstraint",
    "ConstraintAnchor",
    "ConstraintEducation",
    # --- Environment ---
    "SandboxEnvironment",
    "GravityField",
    "WindField",
    "AtmosphereField",
    "MagneticField",
    "FluidField",
    "LightingEnvironment",
    "AtmosphereType",
    # --- Relationship ---
    "EducationalRelationship",
    "VariableBinding",
    "RelationshipScope",
    "CurriculumLevel",
    # --- Observable ---
    "SandboxObservable",
    "ObservableType",
    "ObservableDisplayMode",
    "ObservableDisplay",
    "ObservableTutorMeta",
    "ObservableSourceBinding",
    "AggregateFunction",
    # --- Control ---
    "SandboxControl",
    "ControlBinding",
    "ControlScope",
    "WidgetType",
    "SliderConfig",
    "SelectConfig",
    "SelectOption",
    # --- Sandbox (root) ---
    "SandboxSchema",
    "SandboxMetadata",
    "AIContext",
    "TutorContext",
    "RuntimeConfig",
]
