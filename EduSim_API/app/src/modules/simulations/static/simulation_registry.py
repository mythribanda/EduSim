"""
Static Simulation Registry
==========================
Defines deterministic, LLM-free physics simulation schemas and orchestrates execution.
"""

from typing import Any, Callable, Dict, List, Optional
from .projectile_motion import compute as compute_projectile_motion
from .pendulum import compute as compute_pendulum
from .free_fall import compute as compute_free_fall

STATIC_SIMULATIONS: List[Dict[str, Any]] = [
    {
        "id": "projectile-motion",
        "title": "Projectile Motion Simulation",
        "description": "Calculates 2D trajectory, range, maximum apex height, flight time, and kinetic/potential energy profiles under constant gravity.",
        "category": "Kinematics & Dynamics",
        "difficulty": "Intermediate",
        "has_graphs": True,
        "parameters_schema": {
            "velocity": {
                "type": "number",
                "default": 20.0,
                "min": 0.1,
                "max": 100.0,
                "step": 0.5,
                "unit": "m/s",
                "label": "Launch Velocity",
                "description": "Initial velocity magnitude of the projectile."
            },
            "angle": {
                "type": "number",
                "default": 45.0,
                "min": 0.0,
                "max": 90.0,
                "step": 1.0,
                "unit": "°",
                "label": "Launch Angle",
                "description": "Elevation angle relative to the horizontal ground."
            },
            "gravity": {
                "type": "number",
                "default": 9.81,
                "min": 0.0,
                "max": 30.0,
                "step": 0.1,
                "unit": "m/s²",
                "label": "Gravity Acceleration",
                "description": "Gravitational field acceleration (Earth: 9.81, Moon: 1.62, Jupiter: 24.79)."
            },
            "mass": {
                "type": "number",
                "default": 1.0,
                "min": 0.01,
                "max": 100.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Projectile Mass",
                "description": "Mass of the projectile for kinetic/potential energy computation."
            },
            "initial_height": {
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 200.0,
                "step": 1.0,
                "unit": "m",
                "label": "Initial Launch Height",
                "description": "Vertical starting altitude above ground level."
            },
            "time_step": {
                "type": "number",
                "default": 0.02,
                "min": 0.005,
                "max": 0.1,
                "step": 0.005,
                "unit": "s",
                "label": "Time Step dt",
                "description": "Resolution interval for discrete sampling and trajectory curves."
            }
        }
    },
    {
        "id": "pendulum",
        "title": "Simple & Damped Pendulum",
        "description": "Simulates angular oscillation, RK4 numerical trajectory, period, restoration forces, and damping energy dissipation.",
        "category": "Oscillations & Harmonic Motion",
        "difficulty": "Intermediate",
        "has_graphs": True,
        "parameters_schema": {
            "length": {
                "type": "number",
                "default": 2.0,
                "min": 0.1,
                "max": 10.0,
                "step": 0.1,
                "unit": "m",
                "label": "Pendulum Arm Length",
                "description": "Distance between the pivot point and the center of mass."
            },
            "initial_angle": {
                "type": "number",
                "default": 30.0,
                "min": -90.0,
                "max": 90.0,
                "step": 1.0,
                "unit": "°",
                "label": "Initial Release Angle",
                "description": "Initial angular displacement from the vertical resting position."
            },
            "gravity": {
                "type": "number",
                "default": 9.81,
                "min": 0.0,
                "max": 30.0,
                "step": 0.1,
                "unit": "m/s²",
                "label": "Gravity Acceleration",
                "description": "Downward gravitational acceleration field."
            },
            "mass": {
                "type": "number",
                "default": 1.0,
                "min": 0.05,
                "max": 50.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Bob Mass",
                "description": "Mass of the swinging pendulum bob."
            },
            "damping": {
                "type": "number",
                "default": 0.05,
                "min": 0.0,
                "max": 2.0,
                "step": 0.01,
                "unit": "kg/s",
                "label": "Damping Coefficient",
                "description": "Frictional / aerodynamic air resistance resisting angular velocity."
            },
            "duration": {
                "type": "number",
                "default": 10.0,
                "min": 1.0,
                "max": 60.0,
                "step": 0.5,
                "unit": "s",
                "label": "Simulation Duration",
                "description": "Total duration window for oscillation computation."
            },
            "time_step": {
                "type": "number",
                "default": 0.02,
                "min": 0.005,
                "max": 0.05,
                "step": 0.005,
                "unit": "s",
                "label": "Integration Step dt",
                "description": "Runge-Kutta integration time interval."
            }
        }
    },
    {
        "id": "free-fall",
        "title": "Free Fall & Drag Simulation",
        "description": "Computes vertical 1D drop kinematics, impact time, terminal velocity, and energy conservation with optional aerodynamic resistance.",
        "category": "Kinematics & Dynamics",
        "difficulty": "Beginner",
        "has_graphs": True,
        "parameters_schema": {
            "height": {
                "type": "number",
                "default": 100.0,
                "min": 1.0,
                "max": 1000.0,
                "step": 1.0,
                "unit": "m",
                "label": "Drop Height",
                "description": "Initial vertical altitude above the impact surface."
            },
            "initial_velocity": {
                "type": "number",
                "default": 0.0,
                "min": -100.0,
                "max": 100.0,
                "step": 1.0,
                "unit": "m/s",
                "label": "Initial Velocity (+ up, - down)",
                "description": "Initial vertical speed (positive indicates upward toss, negative indicates downward throw)."
            },
            "gravity": {
                "type": "number",
                "default": 9.81,
                "min": 0.0,
                "max": 30.0,
                "step": 0.1,
                "unit": "m/s²",
                "label": "Gravity Acceleration",
                "description": "Gravitational acceleration constant."
            },
            "mass": {
                "type": "number",
                "default": 1.0,
                "min": 0.01,
                "max": 100.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Object Mass",
                "description": "Mass of the falling body."
            },
            "air_resistance": {
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 2.0,
                "step": 0.01,
                "unit": "kg/s",
                "label": "Air Resistance Drag Coefficient",
                "description": "Linear drag factor opposing velocity (0 = ideal vacuum)."
            },
            "time_step": {
                "type": "number",
                "default": 0.02,
                "min": 0.005,
                "max": 0.1,
                "step": 0.005,
                "unit": "s",
                "label": "Time Step dt",
                "description": "Discrete temporal calculation resolution."
            }
        }
    },
    {
        "id": "collision",
        "title": "1D Momentum & Energy Collision",
        "description": "Simulates elastic, inelastic, and perfectly inelastic collisions with momentum and kinetic energy conservation.",
        "category": "Kinematics & Dynamics",
        "difficulty": "Intermediate",
        "has_graphs": True,
        "parameters_schema": {
            "mass1": {
                "type": "number",
                "default": 2.0,
                "min": 0.1,
                "max": 100.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Mass 1",
                "description": "Mass of object 1."
            },
            "mass2": {
                "type": "number",
                "default": 1.0,
                "min": 0.1,
                "max": 100.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Mass 2",
                "description": "Mass of object 2."
            },
            "velocity1": {
                "type": "number",
                "default": 5.0,
                "min": -50.0,
                "max": 50.0,
                "step": 0.5,
                "unit": "m/s",
                "label": "Velocity 1",
                "description": "Initial velocity of object 1."
            },
            "velocity2": {
                "type": "number",
                "default": 0.0,
                "min": -50.0,
                "max": 50.0,
                "step": 0.5,
                "unit": "m/s",
                "label": "Velocity 2",
                "description": "Initial velocity of object 2."
            },
            "collision_type": {
                "type": "string",
                "default": "elastic",
                "options": ["elastic", "inelastic", "perfectly_inelastic"],
                "label": "Collision Type",
                "description": "Elastic (e=1), inelastic (0<e<1), or perfectly inelastic (e=0)."
            },
            "coefficient_of_restitution": {
                "type": "number",
                "default": 0.5,
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "unit": "",
                "label": "Coefficient of Restitution",
                "description": "Restitution factor e (for inelastic collisions)."
            }
        }
    },
    {
        "id": "spring-mass",
        "title": "Spring-Mass Harmonic Oscillator",
        "description": "Simulates simple and damped harmonic motion of a mass-spring system, calculating frequency, period, restorative forces, and energy states.",
        "category": "Oscillations & Harmonic Motion",
        "difficulty": "Intermediate",
        "has_graphs": True,
        "parameters_schema": {
            "spring_constant": {
                "type": "number",
                "default": 10.0,
                "min": 0.1,
                "max": 500.0,
                "step": 1.0,
                "unit": "N/m",
                "label": "Spring Constant k",
                "description": "Stiffness rating of the spring."
            },
            "mass": {
                "type": "number",
                "default": 0.5,
                "min": 0.05,
                "max": 50.0,
                "step": 0.05,
                "unit": "kg",
                "label": "Attached Mass m",
                "description": "Inertial mass attached to the spring."
            },
            "initial_displacement": {
                "type": "number",
                "default": 0.2,
                "min": -5.0,
                "max": 5.0,
                "step": 0.05,
                "unit": "m",
                "label": "Initial Displacement x₀",
                "description": "Initial stretch or compression from resting equilibrium position."
            },
            "initial_velocity": {
                "type": "number",
                "default": 0.0,
                "min": -20.0,
                "max": 20.0,
                "step": 0.1,
                "unit": "m/s",
                "label": "Initial Velocity v₀",
                "description": "Initial launch velocity."
            },
            "damping_coefficient": {
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 10.0,
                "step": 0.05,
                "unit": "kg/s",
                "label": "Damping Coefficient c",
                "description": "Viscous damping resisting velocity."
            }
        }
    },
    {
        "id": "inclined-plane",
        "title": "Inclined Plane & Friction Dynamics",
        "description": "Analyzes gravitational forces, normal reactions, static/kinetic friction, and kinematic trajectories along an inclined surface.",
        "category": "Kinematics & Dynamics",
        "difficulty": "Beginner",
        "has_graphs": True,
        "parameters_schema": {
            "mass": {
                "type": "number",
                "default": 2.0,
                "min": 0.1,
                "max": 100.0,
                "step": 0.1,
                "unit": "kg",
                "label": "Block Mass",
                "description": "Mass of the sliding block."
            },
            "angle": {
                "type": "number",
                "default": 30.0,
                "min": 1.0,
                "max": 89.0,
                "step": 1.0,
                "unit": "°",
                "label": "Incline Angle",
                "description": "Angle of the slope relative to the horizontal floor."
            },
            "friction_coefficient": {
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 1.0,
                "step": 0.02,
                "unit": "μ",
                "label": "Friction Coefficient μ",
                "description": "Coefficient of friction between surface and object."
            },
            "initial_velocity": {
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 50.0,
                "step": 0.5,
                "unit": "m/s",
                "label": "Initial Velocity v₀",
                "description": "Initial downward velocity."
            },
            "slope_length": {
                "type": "number",
                "default": 5.0,
                "min": 0.5,
                "max": 50.0,
                "step": 0.5,
                "unit": "m",
                "label": "Slope Length",
                "description": "Total distance from apex to bottom."
            }
        }
    }
]

from .collision import compute as compute_collision
from .spring_mass import compute as compute_spring_mass
from .inclined_plane import compute as compute_inclined_plane

_DISPATCH_MAP: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "projectile-motion": compute_projectile_motion,
    "projectile_motion": compute_projectile_motion,
    "pendulum": compute_pendulum,
    "free-fall": compute_free_fall,
    "free_fall": compute_free_fall,
    "collision": compute_collision,
    "spring-mass": compute_spring_mass,
    "spring_mass": compute_spring_mass,
    "inclined-plane": compute_inclined_plane,
    "inclined_plane": compute_inclined_plane,
}


def list_static_simulations() -> List[Dict[str, Any]]:
    """Return all registered static physics simulations metadata."""
    return STATIC_SIMULATIONS


def get_static_simulation(simulation_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata and parameter schema for a specific static simulation."""
    norm_id = simulation_id.strip().lower()
    for sim in STATIC_SIMULATIONS:
        if sim["id"] == norm_id or sim["id"].replace("-", "_") == norm_id.replace("-", "_"):
            return sim
    return None


def run_static_simulation(simulation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute deterministic physics calculation for the given simulation ID.
    """
    norm_id = simulation_id.strip().lower()
    compute_fn = _DISPATCH_MAP.get(norm_id) or _DISPATCH_MAP.get(norm_id.replace("-", "_"))

    if not compute_fn:
        available = list(_DISPATCH_MAP.keys())
        raise ValueError(f"Unknown static simulation ID: '{simulation_id}'. Available: {available}")

    input_params = params or {}
    state_result = compute_fn(input_params)

    return {
        "simulation_id": norm_id,
        "parameters": input_params,
        "state": state_result,
    }
