import math
from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, Field


class CollisionParams(BaseModel):
    mass1: float = Field(default=2.0, gt=0.0, description="Mass of object 1 in kg")
    mass2: float = Field(default=1.0, gt=0.0, description="Mass of object 2 in kg")
    velocity1: float = Field(default=5.0, description="Initial velocity of object 1 in m/s")
    velocity2: float = Field(default=0.0, description="Initial velocity of object 2 in m/s")
    collision_type: Literal["elastic", "inelastic", "perfectly_inelastic"] = Field(
        default="elastic",
        description="Collision regime: elastic (e=1), inelastic (0<e<1), or perfectly_inelastic (e=0)"
    )
    coefficient_of_restitution: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Coefficient of restitution e (0–1, only applied when collision_type is 'inelastic')"
    )


def compute(params: Union[CollisionParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic 1D collision computation using conservation of momentum and energy.
    
    Returns:
      - final_velocity1: float (m/s)
      - final_velocity2: float (m/s)
      - kinetic_energy_before: float (Joules)
      - kinetic_energy_after: float (Joules)
      - energy_lost: float (Joules)
      - momentum_before: float (kg·m/s)
      - momentum_after: float (kg·m/s)
      - graph_data: list of [t, pos1, pos2, vel1, vel2] showing approach, impact, and separation
      - formulas_used: list of formula strings
    """
    if isinstance(params, dict):
        parsed_params = CollisionParams(**params)
    else:
        parsed_params = params

    m1 = float(parsed_params.mass1)
    m2 = float(parsed_params.mass2)
    u1 = float(parsed_params.velocity1)
    u2 = float(parsed_params.velocity2)
    c_type = parsed_params.collision_type

    # Determine coefficient of restitution e
    if c_type == "elastic":
        e = 1.0
    elif c_type == "perfectly_inelastic":
        e = 0.0
    else:
        e = float(parsed_params.coefficient_of_restitution)

    # 1. Total initial momentum & kinetic energy
    p_before = m1 * u1 + m2 * u2
    ke_before = 0.5 * m1 * (u1 * u1) + 0.5 * m2 * (u2 * u2)

    # 2. Final velocities using general 1D collision formula:
    # v1 = (m1*u1 + m2*u2 - m2*e*(u1 - u2)) / (m1 + m2)
    # v2 = (m1*u1 + m2*u2 + m1*e*(u1 - u2)) / (m1 + m2)
    total_mass = m1 + m2
    v1 = (m1 * u1 + m2 * u2 - m2 * e * (u1 - u2)) / total_mass
    v2 = (m1 * u1 + m2 * u2 + m1 * e * (u1 - u2)) / total_mass

    # 3. Final momentum & kinetic energy
    p_after = m1 * v1 + m2 * v2
    ke_after = 0.5 * m1 * (v1 * v1) + 0.5 * m2 * (v2 * v2)
    energy_lost = max(0.0, ke_before - ke_after)

    # 4. Trajectory Generation: Approach, Collision, and Separation
    # Initial separation: object 1 at x = 0.0, object 2 at x = 10.0
    x1_0 = 0.0
    x2_0 = 10.0
    rel_v = u1 - u2

    if rel_v > 0.0001:
        t_coll = (x2_0 - x1_0) / rel_v
        t_total = 2.0 * t_coll
    else:
        # If not moving towards each other, run standard timeline
        t_coll = 2.0
        t_total = 4.0

    num_samples = 60
    graph_data: List[List[float]] = []

    for i in range(num_samples):
        t = (i / (num_samples - 1)) * t_total if num_samples > 1 else 0.0

        if t <= t_coll:
            pos1 = x1_0 + u1 * t
            pos2 = x2_0 + u2 * t
            current_v1 = u1
            current_v2 = u2
        else:
            dt_after = t - t_coll
            x_impact = x1_0 + u1 * t_coll
            pos1 = x_impact + v1 * dt_after
            pos2 = x_impact + v2 * dt_after
            current_v1 = v1
            current_v2 = v2

        graph_data.append([
            round(t, 4),
            round(pos1, 4),
            round(pos2, 4),
            round(current_v1, 4),
            round(current_v2, 4),
        ])

    formulas_used = [
        "p_total = m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂",
        "e = (v₂ - v₁) / (u₁ - u₂)",
        "v₁ = (m₁u₁ + m₂u₂ - m₂e(u₁ - u₂)) / (m₁ + m₂)",
        "v₂ = (m₁u₁ + m₂u₂ + m₁e(u₁ - u₂)) / (m₁ + m₂)",
        "KE_before = ½m₁u₁² + ½m₂u₂²",
        "KE_after = ½m₁v₁² + ½m₂v₂²",
        "ΔE = KE_before - KE_after",
    ]

    return {
        "final_velocity1": round(v1, 4),
        "final_velocity2": round(v2, 4),
        "kinetic_energy_before": round(ke_before, 4),
        "kinetic_energy_after": round(ke_after, 4),
        "energy_lost": round(energy_lost, 4),
        "momentum_before": round(p_before, 4),
        "momentum_after": round(p_after, 4),
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended sandbox compatibility attributes
        "position": {
            "x": round(graph_data[-1][1], 4),
            "y": 0.0,
        },
        "velocity": {
            "x": round(v1, 4),
            "y": 0.0,
        },
        "acceleration": {
            "x": 0.0,
            "y": 0.0,
        },
        "energy": {
            "kinetic": round(ke_after, 4),
            "potential": 0.0,
            "total": round(ke_after, 4),
        },
        "time_elapsed": round(t_total, 4),
        "metrics": {
            "final_velocity1": round(v1, 4),
            "final_velocity2": round(v2, 4),
            "momentum_before": round(p_before, 4),
            "momentum_after": round(p_after, 4),
            "kinetic_energy_before": round(ke_before, 4),
            "kinetic_energy_after": round(ke_after, 4),
            "energy_lost": round(energy_lost, 4),
            "restitution_coefficient": round(e, 4),
        },
    }
