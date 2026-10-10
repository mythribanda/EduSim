import math
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field


class InclinedPlaneParams(BaseModel):
    mass: float = Field(default=2.0, gt=0.0, description="Mass of object in kg")
    angle: float = Field(default=30.0, ge=1.0, le=89.0, description="Incline slope angle in degrees (1–89)")
    gravity: float = Field(default=9.81, description="Gravitational acceleration in m/s²")
    friction_coefficient: float = Field(default=0.0, ge=0.0, le=1.0, description="Kinetic/static friction coefficient μ (0–1)")
    initial_velocity: float = Field(default=0.0, ge=0.0, description="Initial velocity down the slope in m/s")
    slope_length: float = Field(default=5.0, gt=0.0, description="Total length of the inclined slope in meters")


def compute(params: Union[InclinedPlaneParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic inclined plane sliding mechanics computation.
    
    Returns:
      - acceleration: float (m/s² along slope)
      - normal_force: float (N)
      - friction_force: float (N)
      - net_force: float (N)
      - time_to_bottom: float (s)
      - final_velocity: float (m/s)
      - will_move: bool (False if friction overcomes gravity component)
      - graph_data: list of [t, position, velocity, acceleration] along slope sampled at 60 points
      - formulas_used: ["a = g(sinθ - μcosθ)", "F_net = mg sinθ - μmg cosθ"]
    """
    if isinstance(params, dict):
        d = dict(params)
        if "mu" in d and "friction_coefficient" not in d:
            d["friction_coefficient"] = d.pop("mu")
        if "length" in d and "slope_length" not in d:
            d["slope_length"] = d.pop("length")
        parsed_params = InclinedPlaneParams(**d)
    else:
        parsed_params = params

    m = float(parsed_params.mass)
    theta_deg = float(parsed_params.angle)
    g = float(parsed_params.gravity)
    mu = float(parsed_params.friction_coefficient)
    v0 = float(parsed_params.initial_velocity)
    length = float(parsed_params.slope_length)

    theta_rad = math.radians(theta_deg)
    sin_theta = math.sin(theta_rad)
    cos_theta = math.cos(theta_rad)

    # Normal force N = m * g * cos(theta)
    normal_force = m * g * cos_theta
    # Gravity parallel component
    f_gravity_parallel = m * g * sin_theta
    # Max friction force F_f = mu * N
    max_friction = mu * normal_force

    will_move = True
    if v0 <= 0.0 and f_gravity_parallel <= max_friction:
        # Object remains static
        will_move = False
        acceleration = 0.0
        friction_force = f_gravity_parallel
        net_force = 0.0
        time_to_bottom = 0.0
        final_velocity = 0.0
    else:
        friction_force = max_friction
        net_force = max(0.0, f_gravity_parallel - friction_force)
        acceleration = (net_force / m) if m > 0 else 0.0

        if acceleration > 0.0:
            discriminant = v0 * v0 + 2.0 * acceleration * length
            time_to_bottom = (-v0 + math.sqrt(max(0.0, discriminant))) / acceleration
            final_velocity = math.sqrt(max(0.0, discriminant))
        elif v0 > 0.0:
            time_to_bottom = length / v0
            final_velocity = v0
        else:
            time_to_bottom = 0.0
            final_velocity = 0.0

    # Sample 60 graph points along the slope
    num_samples = 60
    graph_data: List[List[float]] = []

    for i in range(num_samples):
        t = (i / (num_samples - 1)) * time_to_bottom if (num_samples > 1 and time_to_bottom > 0) else 0.0
        pos = min(length, v0 * t + 0.5 * acceleration * t * t)
        vel = v0 + acceleration * t
        acc = acceleration

        graph_data.append([
            round(t, 4),
            round(pos, 4),
            round(vel, 4),
            round(acc, 4),
        ])

    formulas_used = [
        "a = g(sinθ - μcosθ)",
        "F_net = mg sinθ - μmg cosθ",
    ]

    final_ke = 0.5 * m * (final_velocity * final_velocity)
    final_h = length * sin_theta

    return {
        "acceleration": round(acceleration, 4),
        "normal_force": round(normal_force, 4),
        "friction_force": round(friction_force, 4),
        "net_force": round(net_force, 4),
        "time_to_bottom": round(time_to_bottom, 4),
        "final_velocity": round(final_velocity, 4),
        "will_move": will_move,
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended sandbox compatibility attributes
        "position": {
            "x": round(length * cos_theta, 4),
            "y": 0.0,
        },
        "velocity": {
            "x": round(final_velocity * cos_theta, 4),
            "y": -round(final_velocity * sin_theta, 4),
        },
        "energy": {
            "kinetic": round(final_ke, 4),
            "potential": 0.0,
            "total": round(final_ke, 4),
        },
        "time_elapsed": round(time_to_bottom, 4),
        "metrics": {
            "acceleration": round(acceleration, 4),
            "normal_force": round(normal_force, 4),
            "friction_force": round(friction_force, 4),
            "net_force": round(net_force, 4),
            "time_to_bottom": round(time_to_bottom, 4),
            "final_velocity": round(final_velocity, 4),
            "slope_length": round(length, 4),
            "angle_deg": round(theta_deg, 4),
        },
    }
