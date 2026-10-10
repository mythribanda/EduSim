
from __future__ import annotations
import logging
import asyncio
from enum import Enum
from typing import Any

# other imports...
logger = logging.getLogger("EduSim.modules.sandbox.initialization.pipeline")

from typing import Any, Dict, List, Optional
from copy import deepcopy

from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema, SandboxMetadata
from app.src.modules.sandbox.schemas.control_schema import SandboxControl, ControlBinding, SliderConfig, SelectConfig
from app.src.modules.sandbox.schemas.observable_schema import SandboxObservable, ObservableSourceBinding, ObservableDisplay
from app.src.modules.sandbox.initialization.normalizers import normalize_sandbox_payload, normalize_number
from app.src.modules.sandbox.initialization.environment_initializer import initialize_environment
from app.src.modules.sandbox.initialization.object_initializer import initialize_objects
from app.src.modules.sandbox.initialization.dependency_resolver import DependencyResolver
from app.src.modules.sandbox.relationships import RelationshipBuilder


class PipelineContext:
    """
    Carries execution state across stages.
    Allows passing raw payloads, hydrated schema nodes, and custom key-value 
    pairs for plugin communication.
    """
    def __init__(self, raw_payload: Dict[str, Any]) -> None:
        self.raw_payload: Dict[str, Any] = deepcopy(raw_payload)
        self.sandbox: Optional[SandboxSchema] = None
        self.metadata_store: Dict[str, Any] = {}


class PipelineStage:
    """
    Abstract interface for single compilation stages.
    """
    def execute(self, context: PipelineContext) -> None:
        raise NotImplementedError("Pipeline stages must implement execute()")


# ===========================================================================
# Pipeline Concrete Stages
# ===========================================================================

class NormalizeStage(PipelineStage):
    """
    1. Defensive structural healing. Rescues coordinates, missing properties, 
    incorrect types, and malformed fields from AI payloads.
    """
    def execute(self, context: PipelineContext) -> None:
        context.raw_payload = normalize_sandbox_payload(context.raw_payload)


class EnvironmentStage(PipelineStage):
    """
    2. Builds the environment, resolving gravity parameters and wind properties.
    """
    def execute(self, context: PipelineContext) -> None:
        raw_env = context.raw_payload.get("environment", {})
        environment_model = initialize_environment(raw_env)

        # Initialize the baseline SandboxSchema container if not yet created
        raw_meta = context.raw_payload.get("metadata", {})
        metadata_model = SandboxMetadata.model_validate(raw_meta) if raw_meta else SandboxMetadata()

        context.sandbox = SandboxSchema(
            metadata=metadata_model,
            environment=environment_model
        )


class ObjectsStage(PipelineStage):
    """
    3. Factory hydration for SandboxObjects. Resolves geometries, defaults, and roles.
    """
    def execute(self, context: PipelineContext) -> None:
        if not context.sandbox:
            raise ValueError("SandboxSchema container not initialized. EnvironmentStage must run before ObjectsStage.")

        raw_objs = context.raw_payload.get("objects", [])
        context.sandbox.objects = initialize_objects(raw_objs)

        # Hydrate constraints safely
        raw_constraints = context.raw_payload.get("constraints", [])
        from app.src.modules.sandbox.schemas.constraint_schema import SandboxConstraint
        hydrated_constraints = []
        for raw_c in raw_constraints:
            try:
                # Direct validation
                c_model = SandboxConstraint.model_validate(raw_c)
                hydrated_constraints.append(c_model)
            except Exception as e:
                logger.info(f"Skipping malformed constraint in ObjectsStage: {e}")
        context.sandbox.constraints = hydrated_constraints


class ObservablesStage(PipelineStage):
    """
    4. Validates and parses raw observables, converting them to Pydantic objects.
    """
    def execute(self, context: PipelineContext) -> None:
        if not context.sandbox:
            return

        raw_observables = context.raw_payload.get("observables", [])
        hydrated_observables = []

        for obs in raw_observables:
            if not isinstance(obs, dict):
                continue
            
            # Reconstruct display config
            disp = obs.get("display") or {}
            display_model = ObservableDisplay(
                display_mode=disp.get("display_mode", "numeric"),
                label=disp.get("label", obs.get("name", "Observable")),
                unit=disp.get("unit", ""),
                color=disp.get("color", "#00D4FF"),
                decimal_places=normalize_number(disp.get("decimal_places", 2), 2),
                min_value=normalize_number(disp.get("min_value")) if "min_value" in disp else None,
                max_value=normalize_number(disp.get("max_value")) if "max_value" in disp else None,
                show_in_panel=bool(disp.get("show_in_panel", True)),
                show_on_canvas=bool(disp.get("show_on_canvas", False))
            )

            # Reconstruct source bindings
            bindings = []
            for b in obs.get("source_bindings", []):
                bindings.append(ObservableSourceBinding(
                    symbol=b.get("symbol", ""),
                    object_id=b.get("object_id"),
                    property_path=b.get("property_path"),
                    observable_id=b.get("observable_id")
                ))

            # Reconstruct tutor meta
            raw_tutor = obs.get("tutor") or {}
            from app.src.modules.sandbox.schemas.observable_schema import ObservableTutorMeta
            tutor_model = ObservableTutorMeta(
                concept_tags=raw_tutor.get("concept_tags", []),
                tutor_questions=raw_tutor.get("tutor_questions", []),
                importance=normalize_number(raw_tutor.get("importance", 3), 3)
            )

            observable_model = SandboxObservable(
                id=obs.get("id", "obs_unknown"),
                name=obs.get("name", "Observable"),
                observable_type=obs.get("observable_type", "direct"),
                target_object_ids=obs.get("target_object_ids", []),
                derivation_formula=obs.get("derivation_formula"),
                source_bindings=bindings,
                aggregate_fn=obs.get("aggregate_fn"),
                delta_source_id=obs.get("delta_source_id"),
                display=display_model,
                tutor=tutor_model
            )
            hydrated_observables.append(observable_model)

        context.sandbox.observables = hydrated_observables


class ControlsStage(PipelineStage):
    """
    5. Validates and parses raw UI controls, completing bindings and ranges.
    """
    def execute(self, context: PipelineContext) -> None:
        if not context.sandbox:
            return

        raw_controls = context.raw_payload.get("controls", [])
        hydrated_controls = []

        for ctrl in raw_controls:
            if not isinstance(ctrl, dict):
                continue
            
            # Reconstruct binding
            raw_bind = ctrl.get("binding") or {}
            binding_model = ControlBinding(
                scope=raw_bind.get("scope", "object"),
                object_id=raw_bind.get("object_id"),
                property_path=raw_bind.get("property_path"),
                action=raw_bind.get("action")
            )

            # Reconstruct widget config depending on type
            widget_type = ctrl.get("widget_type", "slider")
            raw_config = ctrl.get("widget_config") or {}
            widget_config_model = None

            if widget_type == "slider":
                widget_config_model = SliderConfig(
                    min_value=normalize_number(raw_config.get("min_value", 0.0), 0.0),
                    max_value=normalize_number(raw_config.get("max_value", 10.0), 10.0),
                    step=normalize_number(raw_config.get("step", 0.1), 0.1),
                    default_value=normalize_number(raw_config.get("default_value", 5.0), 5.0),
                    unit=raw_config.get("unit")
                )
            elif widget_type == "select":
                widget_config_model = SelectConfig(
                    options=raw_config.get("options", []),
                    default_value=raw_config.get("default_value", "")
                )
            else:
                widget_config_model = raw_config

            control_model = SandboxControl(
                id=ctrl.get("id", "control_unknown"),
                label=ctrl.get("label", "Control"),
                widget_type=widget_type,
                widget_config=widget_config_model,
                binding=binding_model,
                is_enabled=bool(ctrl.get("is_enabled", True)),
                is_visible=bool(ctrl.get("is_visible", True)),
                group=str(ctrl.get("group", "General")),
                display_order=normalize_number(ctrl.get("display_order", 0), 0),
                tooltip=ctrl.get("tooltip"),
                educational_impact=ctrl.get("educational_impact", [])
            )
            hydrated_controls.append(control_model)

        context.sandbox.controls = hydrated_controls


class RelationshipsStage(PipelineStage):
    """
    6. Educational auto-compilation. Dynamically traces sandbox composition 
    and appends relevant physics formulas and concept bindings.
    """
    def execute(self, context: PipelineContext) -> None:
        if not context.sandbox:
            return
        
        # Hydrate pre-existing relationships from raw payload
        raw_relationships = context.raw_payload.get("relationships", [])
        from app.src.modules.sandbox.schemas.relationship_schema import EducationalRelationship
        hydrated_rels = []
        for r in raw_relationships:
            try:
                hydrated_rels.append(EducationalRelationship.model_validate(r))
            except Exception as e:
                logger.info(f"Skipping malformed explicit relationship: {e}")
        context.sandbox.relationships = hydrated_rels

        # Run dynamic RelationshipBuilder to compile/attach contextual relationships
        builder = RelationshipBuilder()
        context.sandbox = builder.attach_relationships(context.sandbox)


class DependencyStage(PipelineStage):
    """
    7. Integrity validation. Topologically sorts observables and relationships,
    verifying reference chains and raising clear errors if circular loops exist.
    """
    def execute(self, context: PipelineContext) -> None:
        if not context.sandbox:
            return

        # Perform reference checks
        DependencyResolver.validate_integrity(context.sandbox)

        # Topological sorting of dependent systems
        context.sandbox.observables = DependencyResolver.sort_observables(context.sandbox)
        context.sandbox.relationships = DependencyResolver.sort_relationships(context.sandbox)


# ===========================================================================
# Pipeline Engine Coordinator
# ===========================================================================

class InitializationPipeline:
    """
    Manages and sequences registered compilation stages.
    Supports dynamic hook insertions and custom plugins.
    """
    def __init__(self) -> None:
        self.stages: List[PipelineStage] = [
            NormalizeStage(),
            EnvironmentStage(),
            ObjectsStage(),
            ObservablesStage(),
            ControlsStage(),
            RelationshipsStage(),
            DependencyStage()
        ]

    def add_stage(self, stage: PipelineStage, index: Optional[int] = None) -> None:
        """Appends or inserts a custom plugin compilation stage."""
        if index is not None:
            self.stages.insert(index, stage)
        else:
            self.stages.append(stage)

    def execute(self, raw_payload: Dict[str, Any]) -> SandboxSchema:
        """Runs the entire compilation sequence, yielding a validated SandboxSchema."""
        context = PipelineContext(raw_payload)
        for stage in self.stages:
            stage.execute(context)

        if not context.sandbox:
            raise ValueError("Sandbox compilation failed: Pipeline completed with empty schema.")

        return context.sandbox
