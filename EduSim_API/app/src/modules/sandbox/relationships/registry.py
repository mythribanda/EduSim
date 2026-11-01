"""
registry.py
===========
Centralized Educational Relationship Registry for EduSim.

This module acts as the authoritative central repository for educational relationship 
templates. It allows the simulation compiler, AI generator, and tutor layers to 
dynamically query, lookup, and compose relationships based on educational levels, 
physics concepts, or specific scenario demands.

It stores standard templates that are then hydrated/bound to concrete sandbox 
properties and object IDs by the `RelationshipBuilder`.

ARCHITECTURE & SCALABILITY
--------------------------
1. Unified Template Library: Pre-populates a dictionary of production-grade 
   `EducationalRelationship` templates mapped by their canonical IDs.
2. Tag-Based & Level-Based Queries: Exposes search utilities to easily filter 
   relationships (e.g., retrieving all 'energy_conservation' relationships for 
   'high_school' level).
3. Dynamic Custom Relationships: Supports runtime registration of novel relationships 
   without touching any static files, ensuring future unknown scenarios (like 
   quantum entanglement sandbox) are fully supported.
"""


from __future__ import annotations
from typing import Dict, List, Optional

from app.src.modules.sandbox.schemas.relationship_schema import (
    EducationalRelationship,
    RelationshipScope,
    CurriculumLevel
)


class RelationshipRegistry:
    """
    Authoritative registry for querying and managing educational relationships templates.
    """
    
    def __init__(self) -> None:
        self._templates: Dict[str, EducationalRelationship] = {}
        self._initialize_default_templates()

    def register(self, template: EducationalRelationship) -> None:
        """
        Dynamically register a new educational relationship template.
        """
        if not template.id:
            raise ValueError("Template ID cannot be empty.")
        self._templates[template.id] = template

    def get_template(self, template_id: str) -> Optional[EducationalRelationship]:
        """
        Retrieve a deep copy of a specific relationship template by its ID.
        """
        template = self._templates.get(template_id)
        if template is None:
            return None
        # Return a copy to prevent accidental mutation of the static registry
        return template.model_copy(deep=True)

    def list_templates(self) -> List[EducationalRelationship]:
        """
        List all registered templates.
        """
        return [t.model_copy(deep=True) for t in self._templates.values()]

    def find_by_tag(self, tag: str) -> List[EducationalRelationship]:
        """
        Find all templates associated with a specific concept tag.
        """
        return [
            t.model_copy(deep=True)
            for t in self._templates.values()
            if tag in t.concept_tags
        ]

    def find_by_level(self, level: CurriculumLevel) -> List[EducationalRelationship]:
        """
        Find all templates matching an educational curriculum level.
        """
        return [
            t.model_copy(deep=True)
            for t in self._templates.values()
            if t.curriculum_level == level
        ]

    def _initialize_default_templates(self) -> None:
        """
        Pre-populates the registry with standard, canonical educational physics relationships.
        """
        
        # 1. Newton's Second Law
        self.register(
            EducationalRelationship(
                id="newtons_second_law",
                name="Newton's Second Law",
                formula_latex="F = m a",
                formula_sympy="F - m * a",
                formula_description="Acceleration of an object is proportional to the net force acting on it and inversely proportional to its mass.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["forces", "newtons_laws"],
                tutor_hints=[
                    "What is the total sum of all forces acting on this object?",
                    "If you double the mass but keep the force the same, what happens to the acceleration?",
                    "Does the net force vector point in the same direction as the acceleration?"
                ],
                rag_query_template="Explain Newton's Second Law and inertia for {curriculum_level} students."
            )
        )

        # 2. Hooke's Law
        self.register(
            EducationalRelationship(
                id="hookes_law",
                name="Hooke's Law",
                formula_latex="F = -k x",
                formula_sympy="F + k * x",
                formula_description="The spring's restoring force is proportional to and in the opposite direction of its displacement.",
                scope=RelationshipScope.PAIRWISE,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["springs", "simple_harmonic_motion", "forces"],
                tutor_hints=[
                    "Why is there a negative sign in the formula? What does it say about the direction of the force?",
                    "If we increase the stiffness (k) of the spring, what happens to the restoring force?",
                    "Where does the block experience zero force? What is that position called?"
                ],
                rag_query_template="Explain Hooke's Law, restoring force and spring constants for {curriculum_level} courses."
            )
        )

        # 3. Kinetic Energy
        self.register(
            EducationalRelationship(
                id="kinetic_energy",
                name="Kinetic Energy",
                formula_latex="KE = \\frac{1}{2} m v^2",
                formula_sympy="KE - 0.5 * m * v**2",
                formula_description="The work needed to accelerate a body of a given mass from rest to its stated velocity.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["energy", "energy_conservation"],
                tutor_hints=[
                    "How does doubling the speed affect the kinetic energy? Hint: Look at the exponent of velocity.",
                    "If a body is at complete rest, what is its kinetic energy?",
                    "Where does the kinetic energy come from when a falling body speeds up?"
                ],
                rag_query_template="Introduce Kinetic Energy and mechanical work for {curriculum_level} physics."
            )
        )

        # 4. Gravitational Potential Energy
        self.register(
            EducationalRelationship(
                id="gravitational_potential_energy",
                name="Gravitational Potential Energy",
                formula_latex="PE = m g h",
                formula_sympy="PE - m * g * h",
                formula_description="Energy stored in an object due to its height relative to a zero reference level in a gravitational field.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["energy", "energy_conservation", "gravity"],
                tutor_hints=[
                    "If you lift an object twice as high, what happens to its stored potential energy?",
                    "Does potential energy depend on the path taken to get to that height?",
                    "How does potential energy change as the gravity scale of the environment is altered?"
                ],
                rag_query_template="Explain Gravitational Potential Energy and reference height for {curriculum_level}."
            )
        )

        # 5. Simple Pendulum Period
        self.register(
            EducationalRelationship(
                id="pendulum_period",
                name="Pendulum Period",
                formula_latex="T = 2 \\pi \\sqrt{\\frac{L}{g}}",
                formula_sympy="T - 2 * pi * sqrt(L / g)",
                formula_description="The period of a simple pendulum depends only on its pendulum arm length and local gravity acceleration.",
                scope=RelationshipScope.PAIRWISE,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["pendulum", "simple_harmonic_motion"],
                tutor_hints=[
                    "If you make the pendulum string four times longer, does the time of swing double or quadruple?",
                    "Why does the mass of the bob not appear anywhere in this period equation?",
                    "How would a pendulum swing on the Moon, where g is much smaller?"
                ],
                rag_query_template="Explain simple pendulum period and small angle approximation for {curriculum_level}."
            )
        )

        # 6. Momentum
        self.register(
            EducationalRelationship(
                id="momentum",
                name="Linear Momentum",
                formula_latex="p = m v",
                formula_sympy="p - m * v",
                formula_description="The quantity of motion of a moving body, measured as a product of its mass and velocity.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.MIDDLE_SCHOOL,
                concept_tags=["momentum", "collisions"],
                tutor_hints=[
                    "If two moving objects collide, what can we say about their combined momentum?",
                    "Which has more momentum: a slow-moving heavy truck, or a fast-moving light bullet?"
                ],
                rag_query_template="Explain momentum conservation and impulse for {curriculum_level}."
            )
        )

        # 7. Rocket Propulsion & Acceleration
        self.register(
            EducationalRelationship(
                id="rocket_acceleration",
                name="Rocket Thrust Acceleration",
                formula_latex="a = \\frac{T - m g}{m}",
                formula_sympy="a - (T - m * g) / m",
                formula_description="The vertical acceleration of a rocket is determined by thrust minus gravity, divided by the rocket's current mass.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["propulsion", "forces", "newtons_laws"],
                tutor_hints=[
                    "What happens to the rocket acceleration as it burns fuel and its mass decreases?",
                    "If the thrust is exactly equal to the weight (m * g), what is the resulting acceleration?",
                    "Does a rocket accelerate faster in zero gravity? Why?"
                ],
                rag_query_template="Explain rocket acceleration, thrust, and Tsiolkovsky equation for {curriculum_level}."
            )
        )

        # 8. Fluid Drag Force
        self.register(
            EducationalRelationship(
                id="drag_force",
                name="Fluid Drag Force",
                formula_latex="F_d = \\frac{1}{2} \\rho v^2 C_d A",
                formula_sympy="F_d - 0.5 * rho * v**2 * C_d * A",
                formula_description="The resistive force exerted by a fluid on a moving object, proportional to the square of relative speed.",
                scope=RelationshipScope.OBJECT,
                curriculum_level=CurriculumLevel.HIGH_SCHOOL,
                concept_tags=["drag", "forces", "fluids"],
                tutor_hints=[
                    "How does doubling the speed affect the drag force? Why is driving at high speed so air-resistant?",
                    "What happens to terminal velocity when you increase the cross-sectional area (A) like opening a parachute?",
                    "How does entering standard water density versus earth air density change the drag experience?"
                ],
                rag_query_template="Explain fluid drag, quadratic air resistance, and terminal velocity for {curriculum_level}."
            )
        )


# Global singleton instance of the registry for simple application access
registry = RelationshipRegistry()
