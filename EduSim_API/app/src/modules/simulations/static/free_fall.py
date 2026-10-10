import math
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field


class FreeFallParams(BaseModel):
    initial_height: float = Field(default=50.0, ge=1.0, le=500.0, description="Initial release height in meters (1–500)")
    initial_velocity: float = Field(default=0.0, ge=0.0, description="Initial downward velocity in m/s")
    gravity: float = Field(default=9.81, description="Gravitational acceleration in m/s²")
    mass: float = Field(default=1.0, description="Object mass in kg")
    air_resistance: bool = Field(default=False, description="Whether aerodynamic drag is enabled")
    drag_coefficient: float = Field(default=0.47, ge=0.0, description="Drag coefficient Cd (default 0.47 for sphere)")


def compute(params: Union[FreeFallParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic free fall simulation computation with optional aerodynamic drag.
    
    Returns:
      - time_to_ground: float (seconds)
      - final_velocity: float (m/s)
      - graph_data: list of [t, height, velocity, acceleration] sampled at 60 points
      - formulas_used: ["h = h₀ + v₀t - ½gt²", "v = v₀ + gt"]
    """
    if isinstance(params, dict):
        d = dict(params)
        # Support aliases
        if "height" in d and "initial_height" not in d:
            d["initial_height"] = d.pop("height")
        if isinstance(d.get("air_resistance"), (int, float)):
            val = float(d["air_resistance"])
            d["air_resistance"] = val > 0
            if val > 0:
                d["drag_coefficient"] = val
        parsed_params = FreeFallParams(**d)
    else:
        parsed_params = params

    h0 = float(parsed_params.initial_height)
    v0 = float(parsed_params.initial_velocity)
    g = float(parsed_params.gravity)
    m = float(parsed_params.mass)
    has_drag = bool(parsed_params.air_resistance)
    cd = float(parsed_params.drag_coefficient)

    rho = 1.225  # Air density in kg/m³
    num_samples = 60
    graph_data: List[List[float]] = []

    if not has_drag:
        # Analytical solution without air resistance
        discriminant = v0 * v0 + 2.0 * g * h0
        time_to_ground = (-v0 + math.sqrt(max(0.0, discriminant))) / g if g > 0 else 0.0
        final_velocity = v0 + g * time_to_ground

        for i in range(num_samples):
            t = (i / (num_samples - 1)) * time_to_ground if num_samples > 1 and time_to_ground > 0 else 0.0
            h = max(0.0, h0 - (v0 * t + 0.5 * g * t * t))
            v = v0 + g * t
            a = g

            graph_data.append([
                round(t, 4),
                round(h, 4),
                round(v, 4),
                round(a, 4),
            ])
    else:
        # Iterative Euler method with drag force = 0.5 * Cd * rho * v²
        dt = 0.001
        t_sim = 0.0
        y_sim = h0
        v_sim = v0
        
        trajectory: List[tuple[float, float, float, float]] = []
        # Initial state
        f_drag_init = 0.5 * cd * rho * (v_sim * v_sim)
        a_init = max(0.0, g - (f_drag_init / m))
        trajectory.append((t_sim, y_sim, v_sim, a_init))

        max_allowed_time = 300.0
        while y_sim > 0.0 and t_sim <= max_allowed_time:
            f_drag = 0.5 * cd * rho * (v_sim * v_sim)
            a = g - (f_drag / m)
            v_sim += a * dt
            y_sim -= v_sim * dt
            t_sim += dt

            trajectory.append((t_sim, max(0.0, y_sim), v_sim, a))

        time_to_ground = t_sim
        final_velocity = v_sim

        # Resample trajectory to exactly 60 points
        total_steps = len(trajectory)
        for i in range(num_samples):
            idx = int(round((i / (num_samples - 1)) * (total_steps - 1))) if num_samples > 1 else 0
            t_val, h_val, v_val, a_val = trajectory[idx]
            graph_data.append([
                round(t_val, 4),
                round(h_val, 4),
                round(v_val, 4),
                round(a_val, 4),
            ])

    formulas_used = [
        "h = h₀ + v₀t - ½gt²",
        "v = v₀ + gt",
    ]

    final_ke = 0.5 * m * (final_velocity * final_velocity)
    final_pe = 0.0

    return {
        "time_to_ground": round(time_to_ground, 4),
        "final_velocity": round(final_velocity, 4),
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended attributes for complete sandbox compatibility
        "position": {
            "x": 0.0,
            "y": 0.0,
        },
        "velocity": {
            "x": 0.0,
            "y": -round(final_velocity, 4),
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
        "time_elapsed": round(time_to_ground, 4),
        "metrics": {
            "initial_height": round(h0, 4),
            "time_to_ground": round(time_to_ground, 4),
            "impact_velocity": round(final_velocity, 4),
        },
    }

