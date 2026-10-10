import math
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field


class PendulumParams(BaseModel):
    length: float = Field(default=1.0, ge=0.1, le=5.0, description="Pendulum length in meters (0.1–5.0)")
    initial_angle: float = Field(default=30.0, ge=1.0, le=90.0, description="Initial release angle in degrees (1–90)")
    gravity: float = Field(default=9.81, description="Gravitational acceleration in m/s²")
    mass: float = Field(default=0.5, description="Bob mass in kg")
    damping: float = Field(default=0.0, ge=0.0, le=1.0, description="Damping coefficient (0–1, 0 = no air resistance)")


def compute(params: Union[PendulumParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic simple & damped pendulum simulation computation using pure mathematics.
    
    Returns:
      - period: float (seconds)
      - max_speed: float (m/s at bottom)
      - max_height: float (m above rest position)
      - graph_data: list of [t, angle, angular_velocity, height, speed] for 2 full periods sampled at 120 points
      - formulas_used: ["T = 2π√(L/g)", "v_max = √(2gL(1-cosθ))"]
    """
    if isinstance(params, dict):
        parsed_params = PendulumParams(**params)
    else:
        parsed_params = params

    L = float(parsed_params.length)
    theta0_deg = float(parsed_params.initial_angle)
    g = float(parsed_params.gravity)
    m = float(parsed_params.mass)
    damping = float(parsed_params.damping)

    theta0_rad = math.radians(theta0_deg)

    # 1. Theoretical period T = 2π√(L/g)
    period = 2.0 * math.pi * math.sqrt(L / g) if g > 0 and L > 0 else 0.0

    # 2. Maximum height above rest position: h_max = L * (1 - cos(theta0))
    max_height = L * (1.0 - math.cos(theta0_rad))

    # 3. Maximum speed at bottom (conservation of energy): v_max = √(2gL(1 - cos(theta0)))
    max_speed = math.sqrt(max(0.0, 2.0 * g * max_height))

    # 4. Two full periods duration
    total_duration = 2.0 * period if period > 0 else 2.0
    num_samples = 120

    omega0 = math.sqrt(g / L) if L > 0 and g > 0 else 0.0
    gamma = (damping * omega0) / 2.0  # Damping rate per second
    omega_d = math.sqrt(max(0.0001, omega0 * omega0 - gamma * gamma)) if omega0 > gamma else omega0

    graph_data: List[List[float]] = []
    pos_x_series: List[List[float]] = []
    pos_y_series: List[List[float]] = []
    vel_x_series: List[List[float]] = []
    vel_y_series: List[List[float]] = []

    for i in range(num_samples):
        t = (i / (num_samples - 1)) * total_duration if num_samples > 1 else 0.0

        if damping > 0:
            decay = math.exp(-gamma * t)
            theta_t = theta0_rad * decay * math.cos(omega_d * t)
            omega_t = -theta0_rad * decay * (gamma * math.cos(omega_d * t) + omega_d * math.sin(omega_d * t))
        else:
            theta_t = theta0_rad * math.cos(omega0 * t)
            omega_t = -theta0_rad * omega0 * math.sin(omega0 * t)

        angle_deg = math.degrees(theta_t)
        height = L * (1.0 - math.cos(theta_t))
        speed = abs(L * omega_t)

        graph_data.append([
            round(t, 4),
            round(angle_deg, 4),
            round(omega_t, 4),
            round(height, 4),
            round(speed, 4),
        ])

        # Cartesian coordinates for UI canvas visualization
        x = L * math.sin(theta_t)
        y = -L * math.cos(theta_t)
        vx = L * omega_t * math.cos(theta_t)
        vy = L * omega_t * math.sin(theta_t)
        pos_x_series.append([round(t, 4), round(x, 4)])
        pos_y_series.append([round(t, 4), round(y, 4)])
        vel_x_series.append([round(t, 4), round(vx, 4)])
        vel_y_series.append([round(t, 4), round(vy, 4)])

    formulas_used = [
        "T = 2π√(L/g)",
        "v_max = √(2gL(1-cosθ))",
    ]

    final_theta = math.radians(graph_data[-1][1])
    final_omega = graph_data[-1][2]
    final_x = L * math.sin(final_theta)
    final_y = -L * math.cos(final_theta)
    final_vx = L * final_omega * math.cos(final_theta)
    final_vy = L * final_omega * math.sin(final_theta)
    final_ke = 0.5 * m * (final_vx * final_vx + final_vy * final_vy)
    final_pe = m * g * (L * (1.0 - math.cos(final_theta)))

    return {
        "period": round(period, 4),
        "max_speed": round(max_speed, 4),
        "max_height": round(max_height, 4),
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended attributes for complete sandbox compatibility
        "position": {
            "x": round(final_x, 4),
            "y": round(final_y, 4),
        },
        "velocity": {
            "x": round(final_vx, 4),
            "y": round(final_vy, 4),
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
        "time_elapsed": round(total_duration, 4),
        "metrics": {
            "theoretical_period": round(period, 4),
            "max_speed": round(max_speed, 4),
            "max_height": round(max_height, 4),
            "length": round(L, 4),
            "damping": round(damping, 4),
        },
    }
