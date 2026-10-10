import math
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field


class ProjectileMotionParams(BaseModel):
    initial_velocity: float = Field(default=20.0, ge=1.0, le=100.0, description="Initial velocity in m/s (1–100)")
    launch_angle: float = Field(default=45.0, ge=0.0, le=90.0, description="Launch angle in degrees (0–90)")
    gravity: float = Field(default=9.81, description="Gravitational acceleration in m/s²")
    mass: float = Field(default=1.0, description="Object mass in kg")
    initial_height: float = Field(default=0.0, ge=0.0, description="Initial vertical height in meters")


def compute(params: Union[ProjectileMotionParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic projectile motion computation using pure mathematics.
    
    Returns:
      - max_height: float (m)
      - range: float (m)
      - time_of_flight: float (s)
      - final_velocity: float (m/s)
      - graph_data: list of [t, x, y, vx, vy] sampled at 60 points across flight
      - formulas_used: list of formula strings shown to the student
    """
    if isinstance(params, dict):
        d = dict(params)
        if "velocity" in d and "initial_velocity" not in d:
            d["initial_velocity"] = d.pop("velocity")
        if "angle" in d and "launch_angle" not in d:
            d["launch_angle"] = d.pop("angle")
        parsed_params = ProjectileMotionParams(**d)
    else:
        parsed_params = params

    v0 = float(parsed_params.initial_velocity)
    angle_deg = float(parsed_params.launch_angle)
    g = float(parsed_params.gravity)
    m = float(parsed_params.mass)
    y0 = max(0.0, float(parsed_params.initial_height))

    # Angle conversion
    angle_rad = math.radians(angle_deg)
    v0x = v0 * math.cos(angle_rad)
    v0y = v0 * math.sin(angle_rad)

    # Calculate time of flight
    if g > 0:
        discriminant = v0y * v0y + 2.0 * g * y0
        t_flight = (v0y + math.sqrt(max(0.0, discriminant))) / g if discriminant >= 0 else 0.0
        max_height = y0 + (v0y * v0y) / (2.0 * g) if v0y > 0 else y0
    else:
        t_flight = 10.0
        max_height = y0 + v0y * t_flight

    total_range = v0x * t_flight
    v_fx = v0x
    v_fy = v0y - g * t_flight
    final_velocity = math.sqrt(v_fx * v_fx + v_fy * v_fy)

    # Sample 60 points across the flight trajectory: [t, x, y, vx, vy]
    num_points = 60
    graph_data: List[List[float]] = []

    for i in range(num_points):
        t = (i / (num_points - 1)) * t_flight if num_points > 1 and t_flight > 0 else 0.0
        x = v0x * t
        y = max(0.0, y0 + v0y * t - 0.5 * g * t * t)
        vx = v0x
        vy = v0y - g * t if t < t_flight else v_fy

        graph_data.append([
            round(t, 4),
            round(x, 4),
            round(y, 4),
            round(vx, 4),
            round(vy, 4)
        ])

    formulas_used = [
        "x = v₀ · cos(θ) · t",
        "y = y₀ + v₀ · sin(θ) · t - ½gt²",
        "v_x = v₀ · cos(θ)",
        "v_y = v₀ · sin(θ) - gt",
        "t_flight = (v₀ · sin(θ) + √(v₀² · sin²(θ) + 2gy₀)) / g",
        "H_max = y₀ + (v₀² · sin²(θ)) / (2g)",
        "R = v₀ · cos(θ) · t_flight",
        "v_final = √(v_x² + v_y²)",
    ]

    final_ke = 0.5 * m * (final_velocity * final_velocity)
    final_pe = 0.0

    return {
        "max_height": round(max_height, 4),
        "range": round(total_range, 4),
        "time_of_flight": round(t_flight, 4),
        "final_velocity": round(final_velocity, 4),
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended attributes for complete sandbox compatibility
        "position": {
            "x": round(total_range, 4),
            "y": 0.0,
        },
        "velocity": {
            "x": round(v_fx, 4),
            "y": round(v_fy, 4),
        },
        "acceleration": {
            "x": 0.0,
            "y": -round(g, 4),
        },
        "energy": {
            "kinetic": round(final_ke, 4),
            "potential": round(final_pe, 4),
            "total": round(final_ke + final_pe, 4),
        },
        "time_elapsed": round(t_flight, 4),
        "metrics": {
            "max_height": round(max_height, 4),
            "range": round(total_range, 4),
            "flight_time": round(t_flight, 4),
            "initial_velocity_x": round(v0x, 4),
            "initial_velocity_y": round(v0y, 4),
            "final_velocity": round(final_velocity, 4),
        },
    }

