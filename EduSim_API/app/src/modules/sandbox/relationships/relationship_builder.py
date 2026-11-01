from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.relationships.relationship_builder")

"""
relationship_builder.py
=======================
Dynamic Relationship Builder for EduSim.

This module dynamically inspects sandbox scenarios (objects, constraints, environment,
and observables) and attaches appropriate educational physics relationships. 

Instead of using rigid, hardcoded scenario pipelines, it uses a modular, rule-based 
detection pattern. Each physical domain is handled by a dedicated "Detector" rule. 
This allows the system to seamlessly compose relationships for arbitrary, mixed-physics 
sandboxes (e.g., a rocket connected to a spring swinging inside a dense fluid).

IMPORTANT SPLIT:
- Matter.js runtime handles forces, collision stepping, and constraint updates.
- This builder handles ONLY the addition of educational relationship metadata 
  and property bindings for the Tutor AI and observable systems.

ARCHITECTURE & COMPOSITION
--------------------------
1. Rule Registration: The `RelationshipBuilder` coordinates multiple `RelationshipDetector` 
   plugins.
2. Property Path Grounding: Binds symbols (like 'm', 'g', 'k') to concrete dot-separated 
   paths in the sandbox state (e.g., 'objects[0].physics.mass', 'environment.gravity.y').
3. Observables Wiring: Automatically cross-references dynamic variable symbols with 
   available live observables (e.g., linking 'v' to a velocity observable).
4. Frictionless Extension: Supporting new physics (e.g., electromagnetic charges) 
   requires only registering a new detector class without altering the build loop.
"""


from typing import List

from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema
from app.src.modules.sandbox.schemas.relationship_schema import (
    EducationalRelationship,
    VariableBinding
)
from app.src.modules.sandbox.relationships.registry import registry


class RelationshipDetector:
    """
    Base class for educational relationship detectors.
    Plugins inherit from this to implement custom domain detection.
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        raise NotImplementedError("Detectors must implement detect_and_build")


# ===========================================================================
# Core Relationship Detector Plugins
# ===========================================================================

class UniversalNewtonianDetector(RelationshipDetector):
    """
    Detects any dynamic physics body and attaches Newton's Second Law (F = ma) 
    and Linear Momentum (p = mv) relationships.
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        relationships = []
        
        for obj in sandbox.objects:
            # Skip static anchors
            if obj.is_static:
                continue

            # 1. Newton's Second Law
            template = registry.get_template("newtons_second_law")
            if template:
                template.id = f"newton_2nd_{obj.id}"
                template.name = f"Newton's Second Law for {obj.name}"
                template.object_ids = [obj.id]
                
                # Check for an acceleration observable
                accel_obs = next((o for o in sandbox.observables if obj.id in o.target_object_ids and any(x in o.id.lower() for x in ["accel", "acceleration"])), None)
                accel_id = accel_obs.id if accel_obs else None
                
                template.variable_map = [
                    VariableBinding(
                        symbol="F",
                        description=f"Net Force acting on {obj.name}",
                        object_id=obj.id,
                        property_path="runtime.net_force", # Set by engine runtime
                        unit="N"
                    ),
                    VariableBinding(
                        symbol="m",
                        description=f"Mass of {obj.name}",
                        object_id=obj.id,
                        property_path="physics.mass",
                        unit="kg"
                    ),
                    VariableBinding(
                        symbol="a",
                        description=f"Live acceleration of {obj.name}",
                        object_id=obj.id,
                        observable_id=accel_id,
                        unit="m/s^2"
                    )
                ]
                relationships.append(template)

            # 2. Linear Momentum
            momentum_temp = registry.get_template("momentum")
            if momentum_temp:
                momentum_temp.id = f"momentum_{obj.id}"
                momentum_temp.name = f"Linear Momentum of {obj.name}"
                momentum_temp.object_ids = [obj.id]
                
                # Look for velocity observable
                vel_obs = next((o for o in sandbox.observables if obj.id in o.target_object_ids and any(x in o.id.lower() for x in ["vel", "velocity"])), None)
                vel_id = vel_obs.id if vel_obs else None
                
                momentum_temp.variable_map = [
                    VariableBinding(
                        symbol="p",
                        description=f"Momentum of {obj.name}",
                        object_id=obj.id,
                        property_path="runtime.momentum",
                        unit="kg*m/s"
                    ),
                    VariableBinding(
                        symbol="m",
                        description=f"Mass of {obj.name}",
                        object_id=obj.id,
                        property_path="physics.mass",
                        unit="kg"
                    ),
                    VariableBinding(
                        symbol="v",
                        description=f"Live velocity of {obj.name}",
                        object_id=obj.id,
                        observable_id=vel_id,
                        unit="m/s"
                    )
                ]
                relationships.append(momentum_temp)

        return relationships


class PendulumDetector(RelationshipDetector):
    """
    Detects simple pendulum compositions:
    - Looking for a dynamic body with tag "pendulum_bob" or similar.
    - Resolving its length from any connected distance constraints.
    - Attaches Period (T = 2pi*sqrt(L/g)) and Energy Conservation relationships.
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        relationships = []
        
        # Look for pendulum bob objects
        bobs = [obj for obj in sandbox.objects if "pendulum_bob" in obj.tags or obj.object_type == "pendulum_bob"]
        
        for bob in bobs:
            # Look for a constraint connecting this bob to a pivot/anchor
            constraint = next((c for c in sandbox.constraints if c.anchor_a.body_id == bob.id or c.anchor_b.body_id == bob.id), None)
            
            # 1. Pendulum Period Relationship
            period_temp = registry.get_template("pendulum_period")
            if period_temp:
                period_temp.id = f"pendulum_period_{bob.id}"
                period_temp.name = f"Swing Period for {bob.name}"
                period_temp.object_ids = [bob.id]
                
                prop_path = None
                if constraint:
                    period_temp.object_ids.append(constraint.id)
                    # Length is bound to the constraint stiffness or geometric length property
                    prop_path = "length" # Path inside SandboxConstraint
                
                period_temp.variable_map = [
                    VariableBinding(
                        symbol="T",
                        description=f"Period of oscillation for {bob.name}",
                        object_id=bob.id,
                        property_path="runtime.period",
                        unit="s"
                    ),
                    VariableBinding(
                        symbol="L",
                        description="Length of the pendulum string",
                        object_id=constraint.id if constraint else None,
                        property_path=prop_path,
                        unit="m"
                    ),
                    VariableBinding(
                        symbol="g",
                        description="Local acceleration of gravity",
                        object_id=None, # Global/Environment gravity
                        property_path="gravity.y",
                        unit="m/s^2"
                    )
                ]
                relationships.append(period_temp)

            # 2. Kinetic & Potential Energy Conservation
            ke_temp = registry.get_template("kinetic_energy")
            pe_temp = registry.get_template("gravitational_potential_energy")
            
            vel_obs = next((o for o in sandbox.observables if bob.id in o.target_object_ids and any(x in o.id.lower() for x in ["vel", "velocity"])), None)
            vel_id = vel_obs.id if vel_obs else None
            
            if ke_temp:
                ke_temp.id = f"kinetic_energy_{bob.id}"
                ke_temp.name = f"Kinetic Energy of {bob.name}"
                ke_temp.object_ids = [bob.id]
                ke_temp.variable_map = [
                    VariableBinding(symbol="KE", description="Energy of motion", object_id=bob.id, property_path="runtime.kinetic_energy", unit="J"),
                    VariableBinding(symbol="m", description="Bob mass", object_id=bob.id, property_path="physics.mass", unit="kg"),
                    VariableBinding(symbol="v", description="Bob velocity", object_id=bob.id, observable_id=vel_id, unit="m/s")
                ]
                relationships.append(ke_temp)
                
            if pe_temp:
                pe_temp.id = f"potential_energy_{bob.id}"
                pe_temp.name = f"Gravitational Potential Energy of {bob.name}"
                pe_temp.object_ids = [bob.id]
                pe_temp.variable_map = [
                    VariableBinding(symbol="PE", description="Potential energy of position", object_id=bob.id, property_path="runtime.potential_energy", unit="J"),
                    VariableBinding(symbol="m", description="Bob mass", object_id=bob.id, property_path="physics.mass", unit="kg"),
                    VariableBinding(symbol="g", description="Gravity constant", object_id=None, property_path="gravity.y", unit="m/s^2"),
                    VariableBinding(symbol="h", description="Height above low point", object_id=bob.id, property_path="position.y", unit="m")
                ]
                relationships.append(pe_temp)

        return relationships


class RocketPropulsionDetector(RelationshipDetector):
    """
    Detects rockets (carrying object_type == "rocket_body" or tagged "rocket")
    and attaches Propulsion acceleration formula: a = (T - mg)/m.
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        relationships = []
        rockets = [obj for obj in sandbox.objects if "rocket" in obj.tags or obj.object_type == "rocket_body"]

        for rocket in rockets:
            template = registry.get_template("rocket_acceleration")
            if template:
                template.id = f"rocket_thrust_{rocket.id}"
                template.name = f"Propulsion Dynamics for {rocket.name}"
                template.object_ids = [rocket.id]

                # Check for an acceleration observable
                accel_obs = next((o for o in sandbox.observables if rocket.id in o.target_object_ids and any(x in o.id.lower() for x in ["accel", "acceleration"])), None)
                accel_id = accel_obs.id if accel_obs else None

                # Find any control thrust binding
                template.variable_map = [
                    VariableBinding(
                        symbol="a",
                        description=f"Upward acceleration of {rocket.name}",
                        object_id=rocket.id,
                        observable_id=accel_id,
                        unit="m/s^2"
                    ),
                    VariableBinding(
                        symbol="T",
                        description="Engine thrust force",
                        object_id=rocket.id,
                        property_path="physics.thrust", # Extensible physics property
                        unit="N"
                    ),
                    VariableBinding(
                        symbol="m",
                        description="Total mass (casing + fuel)",
                        object_id=rocket.id,
                        property_path="physics.mass",
                        unit="kg"
                    ),
                    VariableBinding(
                        symbol="g",
                        description="Gravity pulling down",
                        object_id=None,
                        property_path="gravity.y",
                        unit="m/s^2"
                    )
                ]
                relationships.append(template)

        return relationships


class SpringElasticDetector(RelationshipDetector):
    """
    Detects elastic springs or spring constraints and attaches Hooke's Law (F = -kx).
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        relationships = []
        
        # In Sandbox Schema v2, constraints representing springs are modeled as standard SandboxConstraint
        # We look for constraints tagged 'spring' or having type 'spring' or custom stiffness properties
        springs = [c for c in sandbox.constraints if "spring" in c.education.concept_tags or c.constraint_type == "spring"]

        for idx, spring in enumerate(springs):
            template = registry.get_template("hookes_law")
            if template:
                template.id = f"spring_force_{spring.id}"
                template.name = f"Hooke's Law for {spring.id}"
                template.object_ids = [spring.id]
                if spring.anchor_a.body_id:
                    template.object_ids.append(spring.anchor_a.body_id)
                if spring.anchor_b.body_id:
                    template.object_ids.append(spring.anchor_b.body_id)

                template.variable_map = [
                    VariableBinding(
                        symbol="F",
                        description="Restoring force of the spring",
                        object_id=spring.id,
                        property_path="runtime.restoring_force",
                        unit="N"
                    ),
                    VariableBinding(
                        symbol="k",
                        description="Spring stiffness coefficient",
                        object_id=spring.id,
                        property_path="stiffness",
                        unit="N/m"
                    ),
                    VariableBinding(
                        symbol="x",
                        description="Displacement from equilibrium length",
                        object_id=spring.id,
                        property_path="runtime.displacement",
                        unit="m"
                    )
                ]
                relationships.append(template)

        return relationships


class FluidDragDetector(RelationshipDetector):
    """
    Detects objects submerged inside a fluid field or standard atmospheric wind resistance
    and attaches Fluid Drag Force relationship.
    """
    def detect_and_build(self, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        relationships = []
        
        # Check if environment has density
        density_path = None
        if sandbox.environment.fluid.enabled:
            density_path = "fluid.density"
        elif sandbox.environment.atmosphere.air_density > 0:
            density_path = "atmosphere.air_density"

        if not density_path:
            return relationships

        # Apply to any active dynamic body
        for obj in sandbox.objects:
            if obj.is_static:
                continue

            template = registry.get_template("drag_force")
            if template:
                template.id = f"drag_{obj.id}"
                template.name = f"Fluid Drag on {obj.name}"
                template.object_ids = [obj.id]

                vel_obs = next((o for o in sandbox.observables if obj.id in o.target_object_ids and any(x in o.id.lower() for x in ["vel", "velocity"])), None)
                vel_id = vel_obs.id if vel_obs else None

                template.variable_map = [
                    VariableBinding(
                        symbol="F_d",
                        description=f"Fluid drag resistance on {obj.name}",
                        object_id=obj.id,
                        property_path="runtime.drag_force",
                        unit="N"
                    ),
                    VariableBinding(
                        symbol="rho",
                        description="Density of the surrounding medium",
                        object_id=None,
                        property_path=density_path,
                        unit="kg/m^3"
                    ),
                    VariableBinding(
                        symbol="v",
                        description=f"Velocity of {obj.name} relative to medium",
                        object_id=obj.id,
                        observable_id=vel_id,
                        unit="m/s"
                    ),
                    VariableBinding(
                        symbol="C_d",
                        description="Shape drag coefficient",
                        object_id=obj.id,
                        property_path="physics.drag_coefficient", # Extensible physics property
                        unit="dimensionless"
                    ),
                    VariableBinding(
                        symbol="A",
                        description="Projected frontal area",
                        object_id=obj.id,
                        property_path="physics.cross_sectional_area", # Extensible physics property
                        unit="m^2"
                    )
                ]
                relationships.append(template)

        return relationships


# ===========================================================================
# Relationship Builder Coordinator
# ===========================================================================

class RelationshipBuilder:
    """
    Main builder coordinating the dynamic inspection and compilation of educational 
    relationships inside Sandbox schemas.
    """
    def __init__(self) -> None:
        self.detectors: List[RelationshipDetector] = [
            UniversalNewtonianDetector(),
            PendulumDetector(),
            RocketPropulsionDetector(),
            SpringElasticDetector(),
            FluidDragDetector()
        ]

    def register_detector(self, detector: RelationshipDetector) -> None:
        """Register a novel detector class to support future physical domains."""
        self.detectors.append(detector)

    def attach_relationships(self, sandbox: SandboxSchema) -> SandboxSchema:
        """
        Scans the given SandboxSchema, dynamically detects physical contexts, 
        and attaches relevant Pydantic `EducationalRelationship` elements to the 
        `sandbox.relationships` field.
        
        Mutates the sandbox schema in-place and returns it.
        """
        # Initialize relationships container if empty
        if not sandbox.relationships:
            sandbox.relationships = []

        existing_ids = {r.id for r in sandbox.relationships}

        # Run all detectors
        for detector in self.detectors:
            try:
                new_relationships = detector.detect_and_build(sandbox)
                for rel in new_relationships:
                    # Prevent duplicate relationship attachments
                    if rel.id not in existing_ids:
                        sandbox.relationships.append(rel)
                        existing_ids.add(rel.id)
            except Exception as e:
                # Robust error isolation: one failing detector shouldn't crash the entire compilation
                logger.error(f"Error compiling relationships with {detector.__class__.__name__}: {e}")

        # Post-processing/Validation of object ID references to ensure integrity
        valid_object_ids = {obj.id for obj in sandbox.objects}
        valid_constraint_ids = {c.id for c in sandbox.constraints}
        valid_ids = valid_object_ids.union(valid_constraint_ids)

        for rel in sandbox.relationships:
            # Clean up object_ids references that do not exist in the sandbox
            rel.object_ids = [oid for oid in rel.object_ids if oid in valid_ids or oid == "environment" or oid is None]

        return sandbox
