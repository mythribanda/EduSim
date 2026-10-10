"""
registry.py
===========
Authoritative registry and metadata for deterministic, LLM-free static physics simulations.
"""

from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel

from .static.projectile_motion import compute as compute_projectile, ProjectileMotionParams
from .static.pendulum import compute as compute_pendulum, PendulumParams
from .static.free_fall import compute as compute_free_fall, FreeFallParams
from .static.collision import compute as compute_collision, CollisionParams
from .static.spring_mass import compute as compute_spring_mass, SpringMassParams
from .static.inclined_plane import compute as compute_inclined_plane, InclinedPlaneParams

SIMULATION_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "projectile-motion",
        "title": "Projectile Motion",
        "emoji": "🏀",
        "description": "Launch objects and watch them fly through the air",
        "category": "Mechanics",
        "difficulty": "beginner",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["velocity", "gravity", "trajectory", "range"],
        "grade_levels": ["9", "10", "11"],
        "module": "projectile_motion"
    },
    {
        "id": "pendulum",
        "title": "Simple & Damped Pendulum",
        "emoji": "⏱️",
        "description": "Explore periodic oscillations, restoring gravity forces, and damping energy dissipation",
        "category": "Oscillations",
        "difficulty": "intermediate",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["period", "frequency", "restoring_force", "damping", "amplitude"],
        "grade_levels": ["10", "11", "12"],
        "module": "pendulum"
    },
    {
        "id": "free-fall",
        "title": "Free Fall & Air Resistance",
        "emoji": "🪂",
        "description": "Drop objects from heights with optional aerodynamic drag and terminal velocity",
        "category": "Mechanics",
        "difficulty": "beginner",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["gravity", "acceleration", "air_resistance", "terminal_velocity"],
        "grade_levels": ["9", "10", "11"],
        "module": "free_fall"
    },
    {
        "id": "collision",
        "title": "1D Momentum & Energy Collision",
        "emoji": "💥",
        "description": "Simulate elastic, inelastic, and perfectly inelastic collisions between two objects",
        "category": "Mechanics",
        "difficulty": "intermediate",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["momentum", "kinetic_energy", "restitution", "conservation_laws"],
        "grade_levels": ["10", "11", "12"],
        "module": "collision"
    },
    {
        "id": "spring-mass",
        "title": "Spring-Mass Harmonic Oscillator",
        "emoji": "🌀",
        "description": "Observe simple and damped harmonic motion of a mass attached to a spring",
        "category": "Oscillations",
        "difficulty": "intermediate",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["spring_constant", "hookes_law", "natural_frequency", "damping"],
        "grade_levels": ["10", "11", "12"],
        "module": "spring_mass"
    },
    {
        "id": "inclined-plane",
        "title": "Inclined Plane & Friction Dynamics",
        "emoji": "📐",
        "description": "Analyze gravitational forces, normal reactions, and friction along a slope",
        "category": "Mechanics",
        "difficulty": "beginner",
        "has_graphs": True,
        "has_guided_mode": True,
        "key_concepts": ["normal_force", "friction", "parallel_force", "incline_angle"],
        "grade_levels": ["9", "10", "11"],
        "module": "inclined_plane"
    }
]

SIMULATION_MODELS: Dict[str, Type[BaseModel]] = {
    "projectile-motion": ProjectileMotionParams,
    "projectile_motion": ProjectileMotionParams,
    "pendulum": PendulumParams,
    "free-fall": FreeFallParams,
    "free_fall": FreeFallParams,
    "collision": CollisionParams,
    "spring-mass": SpringMassParams,
    "spring_mass": SpringMassParams,
    "inclined-plane": InclinedPlaneParams,
    "inclined_plane": InclinedPlaneParams,
}

SIMULATION_COMPUTE: Dict[str, Callable[[Any], Dict[str, Any]]] = {
    "projectile-motion": compute_projectile,
    "projectile_motion": compute_projectile,
    "pendulum": compute_pendulum,
    "free-fall": compute_free_fall,
    "free_fall": compute_free_fall,
    "collision": compute_collision,
    "spring-mass": compute_spring_mass,
    "spring_mass": compute_spring_mass,
    "inclined-plane": compute_inclined_plane,
    "inclined_plane": compute_inclined_plane,
}


def get_simulation_meta(simulation_id: str) -> Optional[Dict[str, Any]]:
    norm = simulation_id.strip().lower()
    for item in SIMULATION_REGISTRY:
        if item["id"] == norm or item["id"].replace("-", "_") == norm.replace("-", "_"):
            return item
    return None


def get_simulation_schema(simulation_id: str) -> Optional[Dict[str, Any]]:
    norm = simulation_id.strip().lower()
    model_cls = SIMULATION_MODELS.get(norm) or SIMULATION_MODELS.get(norm.replace("-", "_"))
    if model_cls:
        return model_cls.model_json_schema()
    return None


def run_simulation(simulation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    norm = simulation_id.strip().lower()
    compute_fn = SIMULATION_COMPUTE.get(norm) or SIMULATION_COMPUTE.get(norm.replace("-", "_"))
    if not compute_fn:
        available = [item["id"] for item in SIMULATION_REGISTRY]
        raise ValueError(f"Unknown static simulation ID: '{simulation_id}'. Available: {available}")
    return compute_fn(params or {})
