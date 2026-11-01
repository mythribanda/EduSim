"""
educational_mappings.py
=======================
Educational Mappings system for EduSim.

This module maps runtime physics concepts, tags, and properties to rich educational
metadata. It acts as the conceptual bridge between the raw physics parameters (like 
velocity, tension, thrust) and their pedagogical significance (e.g., grade level 
relevance, learning objectives, common student misconceptions, and Socratic tutor prompts).

This layer is strictly metadata-driven and contains no runtime or physics-stepping logic.

ARCHITECTURE & SCALABILITY
--------------------------
1. Unified Concepts Dictionary: Provides a central registry (`CONCEPT_LIBRARY`) containing 
   learning targets, age-appropriate explanations, and common student errors.
2. Property-to-Concept Binding: Standardizes how specific properties (e.g., `physics.mass`)
   translate to pedagogical terms across different simulations (e.g., "Inertial Mass").
3. Anti-Gravity & Emerging Physics Ready: Allows adding new concepts like "Anti-Gravity" 
   or "Quantum Mechanics" by registering a new entry without refactoring any core pipelines.
"""


from __future__ import annotations
from typing import Dict, List, Any
from pydantic import BaseModel, Field
from app.src.modules.sandbox.schemas.relationship_schema import CurriculumLevel


class Misconception(BaseModel):
    """
    Representation of a common student misconception about a physics concept.
    """
    id: str = Field(..., description="Unique misconception code, e.g. 'force_needed_for_motion'")
    statement: str = Field(..., description="The erroneous belief statement")
    correction: str = Field(..., description="The scientifically correct physical explanation")
    tutor_intervention: str = Field(..., description="Suggested Socratic question or response to guide the student")


class ConceptDefinition(BaseModel):
    """
    Comprehensive educational definition of a physics concept.
    """
    id: str = Field(..., description="Unique concept tag identifier, e.g. 'hookes_law'")
    display_name: str = Field(..., description="Pedagogical title, e.g. 'Hooke\\'s Law and Elasticity'")
    description: str = Field(..., description="Student-friendly standard explanation of the concept")
    grade_levels: List[CurriculumLevel] = Field(..., description="Target curriculum levels")
    learning_objectives: List[str] = Field(..., description="What the student should master")
    misconceptions: List[Misconception] = Field(default_factory=list, description="Common misunderstandings")
    tutor_prompts: List[str] = Field(default_factory=list, description="Socratic questions used by the AI tutor")
    extra_context: Dict[str, Any] = Field(default_factory=dict, description="Extensible metadata bag")


# ===========================================================================
# Central Educational Concepts Library
# ===========================================================================

CONCEPT_LIBRARY: Dict[str, ConceptDefinition] = {
    "forces": ConceptDefinition(
        id="forces",
        display_name="Force Systems and Equilibrium",
        description="A force is a push or pull acting upon an object as a result of its interaction with another object.",
        grade_levels=[CurriculumLevel.MIDDLE_SCHOOL, CurriculumLevel.HIGH_SCHOOL],
        learning_objectives=[
            "Identify different types of forces acting on a body (gravity, normal force, tension, friction).",
            "Construct free-body diagrams representing force systems.",
            "Distinguish between balanced and unbalanced forces."
        ],
        misconceptions=[
            Misconception(
                id="force_needed_for_motion",
                statement="An object requires a continuous force to remain in motion.",
                correction="According to Newton's First Law, an object in motion continues in motion with constant velocity unless acted upon by a net external force.",
                tutor_intervention="If you turn off the thruster in vacuum, why does the rocket keep moving forever? What force is slowing it down on Earth?"
            ),
            Misconception(
                id="normal_force_equals_gravity",
                statement="The normal force is always equal and opposite to gravity.",
                correction="The normal force is equal to the component of gravity perpendicular to the contact surface. On ramps or during vertical acceleration, it changes.",
                tutor_intervention="If you press down hard on a block resting on a table, does the table push back with a normal force equal to gravity, or is it stronger?"
            )
        ],
        tutor_prompts=[
            "What external objects are interacting with this body to exert forces on it?",
            "If all forces on this body are balanced, what can you say about its speed?",
            "Look at the direction of the net force arrow. How is it related to the motion?"
        ]
    ),
    "newtons_laws": ConceptDefinition(
        id="newtons_laws",
        display_name="Newton's Laws of Motion",
        description="Three fundamental laws that describe the relationship between the motion of an object and the forces acting upon it.",
        grade_levels=[CurriculumLevel.MIDDLE_SCHOOL, CurriculumLevel.HIGH_SCHOOL, CurriculumLevel.UNDERGRADUATE],
        learning_objectives=[
            "Explain inertia and how mass resists change in motion (1st Law).",
            "Calculate force, mass, or acceleration using F = ma (2nd Law).",
            "Identify action-reaction force pairs (3rd Law)."
        ],
        misconceptions=[
            Misconception(
                id="action_reaction_cancel",
                statement="Action and reaction forces act on the same object and cancel each other out, preventing motion.",
                correction="Action-reaction force pairs act on two completely different objects, so they never cancel each other out on a single free body.",
                tutor_intervention="When a rocket expels fuel gas, does the reaction force act on the gas or on the rocket body?"
            ),
            Misconception(
                id="mass_and_weight_identical",
                statement="Mass and weight are the exact same property.",
                correction="Mass is an intrinsic property measuring inertia (resistance to acceleration), while weight is the gravitational force acting on that mass.",
                tutor_intervention="If we teleport this pendulum to the Moon, does the mass of the bob change? What about its weight?"
            )
        ],
        tutor_prompts=[
            "If you double the force acting on the mass, what happens to its rate of acceleration?",
            "Identify the action and reaction forces when two blocks collide."
        ]
    ),
    "simple_harmonic_motion": ConceptDefinition(
        id="simple_harmonic_motion",
        display_name="Simple Harmonic Motion and Oscillations",
        description="A special type of periodic motion where the restoring force is directly proportional to the displacement.",
        grade_levels=[CurriculumLevel.HIGH_SCHOOL, CurriculumLevel.UNDERGRADUATE],
        learning_objectives=[
            "Identify simple harmonic motion in pendulums and mass-spring systems.",
            "Relate frequency, period, and amplitude.",
            "Determine how physical factors (length, mass, gravity) influence periodic timing."
        ],
        misconceptions=[
            Misconception(
                id="amplitude_affects_period",
                statement="Increasing the starting displacement/amplitude of a pendulum makes it swing faster, increasing the period.",
                correction="For small angles, the period of a pendulum is completely independent of the amplitude. The higher release point increases velocity, compensating for the extra distance.",
                tutor_intervention="Try releasing the pendulum from 5 degrees and then 15 degrees. Does the period change? Why do you think that is?"
            ),
            Misconception(
                id="pendulum_mass_affects_period",
                statement="A heavier pendulum bob will swing faster than a lighter one due to stronger gravity.",
                correction="While a heavier bob experiences a stronger gravitational force, it also has proportionately higher inertia. These effects cancel out, leaving the period dependent only on L and g.",
                tutor_intervention="If you replace a wood bob with a lead bob of the exact same size, does the pendulum swing faster? Why does mass cancel out?"
            )
        ],
        tutor_prompts=[
            "Where in the swing is the restoring force at its maximum? Where is it zero?",
            "What physical parameter can we modify to change the time it takes for one full oscillation?"
        ]
    ),
    "energy_conservation": ConceptDefinition(
        id="energy_conservation",
        display_name="Conservation of Mechanical Energy",
        description="The total mechanical energy in a closed system remains constant, transitioning between potential and kinetic forms.",
        grade_levels=[CurriculumLevel.MIDDLE_SCHOOL, CurriculumLevel.HIGH_SCHOOL, CurriculumLevel.UNDERGRADUATE],
        learning_objectives=[
            "Trace conversion between kinetic energy (KE) and gravitational/elastic potential energy (PE).",
            "Demonstrate that total mechanical energy remains constant in frictionless systems.",
            "Analyze how non-conservative forces (friction, drag) convert mechanical energy into thermal energy."
        ],
        misconceptions=[
            Misconception(
                id="energy_consumed",
                statement="Energy is actively consumed or used up as an object slows down.",
                correction="Energy is never created or destroyed; it only changes forms. Friction converts kinetic energy into thermal/internal energy.",
                tutor_intervention="When the block slides to a stop due to friction, where did its kinetic energy go? Did it disappear, or did the surface get warmer?"
            )
        ],
        tutor_prompts=[
            "At which point in the pendulum's trajectory is the kinetic energy at its absolute maximum?",
            "Compare the total energy at the release point to the total energy at the lowest point. What do you notice?"
        ]
    ),
    "propulsion": ConceptDefinition(
        id="propulsion",
        display_name="Thrust, Propulsion and Momentum Exchange",
        description="The concept of propelling an object forward by ejecting mass backward, governed by conservation of momentum.",
        grade_levels=[CurriculumLevel.HIGH_SCHOOL, CurriculumLevel.UNDERGRADUATE],
        learning_objectives=[
            "Relate ejected fuel mass and exhaust velocity to rocket thrust.",
            "Explain thrust using Newton's Third Law and momentum conservation."
        ],
        misconceptions=[
            Misconception(
                id="rocket_pushes_air",
                statement="Rockets require atmospheric air to push against in order to generate thrust and move forward.",
                correction="Rockets operate through momentum exchange. The thrust force is the reaction to ejecting fuel mass backward, which works perfectly in empty space.",
                tutor_intervention="If there is no air in space, what is the rocket pushing against? How does ejecting fuel gas backward propel the rocket forward?"
            )
        ],
        tutor_prompts=[
            "How does increasing the fuel burning rate affect the force of thrust?",
            "As the rocket burns fuel, its total mass decreases. If thrust remains constant, what happens to the rate of acceleration?"
        ]
    ),
    "anti_gravity": ConceptDefinition(
        id="anti_gravity",
        display_name="Advanced Dynamics & Weightlessness",
        description="Systems where standard gravitational forces are manipulated, cancelled, or inverted, highlighting mass-independent dynamics.",
        grade_levels=[CurriculumLevel.HIGH_SCHOOL, CurriculumLevel.UNDERGRADUATE, CurriculumLevel.ADVANCED],
        learning_objectives=[
            "Understand how gravity scale manipulation affects buoyancy and free-fall trajectory.",
            "Distinguish between zero-gravity free-fall and the removal of inertial mass."
        ],
        misconceptions=[
            Misconception(
                id="anti_gravity_removes_inertia",
                statement="Under anti-gravity or weightlessness, objects lose their mass and inertia.",
                correction="Anti-gravity only cancels or inverts gravitational force. The body still retains its full inertial mass and requires the same force to accelerate.",
                tutor_intervention="If you push a floating astronaut in zero gravity, do they instantly accelerate to infinite speed, or do they still resist your push?"
            )
        ],
        tutor_prompts=[
            "If gravity scale is set to zero, how does a pendulum behave when released?",
            "Why does a rocket accelerate faster when its gravity scale is reduced to zero?"
        ]
    )
}
