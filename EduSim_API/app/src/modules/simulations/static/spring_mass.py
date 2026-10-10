import math
from typing import Any, Dict, List, Union
from pydantic import BaseModel, Field


class SpringMassParams(BaseModel):
    spring_constant: float = Field(default=10.0, gt=0.0, description="Spring stiffness constant k in N/m")
    mass: float = Field(default=0.5, gt=0.0, description="Mass m in kg")
    initial_displacement: float = Field(default=0.2, description="Initial displacement x₀ from equilibrium in meters")
    initial_velocity: float = Field(default=0.0, description="Initial velocity v₀ in m/s")
    damping_coefficient: float = Field(default=0.0, ge=0.0, description="Damping coefficient c (0 = no damping)")


def compute(params: Union[SpringMassParams, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic spring-mass harmonic oscillator simulation computation.
    
    Returns:
      - natural_frequency: float (rad/s)
      - period: float (s)
      - amplitude: float (m)
      - graph_data: list of [t, displacement, velocity, acceleration, spring_force, kinetic_energy, potential_energy] for 3 full periods
      - formulas_used: ["ω = √(k/m)", "x(t) = A·cos(ωt + φ)", "F = -kx"]
    """
    if isinstance(params, dict):
        d = dict(params)
        if "k" in d and "spring_constant" not in d:
            d["spring_constant"] = d.pop("k")
        if "m" in d and "mass" not in d:
            d["mass"] = d.pop("m")
        if "x0" in d and "initial_displacement" not in d:
            d["initial_displacement"] = d.pop("x0")
        if "v0" in d and "initial_velocity" not in d:
            d["initial_velocity"] = d.pop("v0")
        if "c" in d and "damping_coefficient" not in d:
            d["damping_coefficient"] = d.pop("c")
        parsed_params = SpringMassParams(**d)
    else:
        parsed_params = params

    k = float(parsed_params.spring_constant)
    m = float(parsed_params.mass)
    x0 = float(parsed_params.initial_displacement)
    v0 = float(parsed_params.initial_velocity)
    c = float(parsed_params.damping_coefficient)

    # 1. Natural angular frequency & period
    omega_n = math.sqrt(k / m) if (k > 0 and m > 0) else 0.0
    period = (2.0 * math.pi / omega_n) if omega_n > 0 else 0.0

    # Damping rate
    gamma = c / (2.0 * m) if m > 0 else 0.0

    # 2. Amplitude calculation
    if omega_n > 0:
        if c == 0.0 or gamma < omega_n:
            omega_d = math.sqrt(omega_n * omega_n - gamma * gamma) if gamma < omega_n else omega_n
            c1 = x0
            c2 = (v0 + gamma * x0) / omega_d if omega_d > 0 else 0.0
            amplitude = math.sqrt(c1 * c1 + c2 * c2)
        else:
            amplitude = abs(x0)
            omega_d = 0.0
    else:
        amplitude = abs(x0)
        omega_d = 0.0

    # 3. 3 Full periods simulation duration
    total_duration = 3.0 * period if period > 0 else 3.0
    num_samples = 120
    graph_data: List[List[float]] = []

    for i in range(num_samples):
        t = (i / (num_samples - 1)) * total_duration if num_samples > 1 else 0.0

        if c == 0.0 or gamma == 0.0:
            # Pure harmonic oscillator
            x_t = x0 * math.cos(omega_n * t) + (v0 / omega_n) * math.sin(omega_n * t) if omega_n > 0 else x0
            v_t = -x0 * omega_n * math.sin(omega_n * t) + v0 * math.cos(omega_n * t) if omega_n > 0 else v0
            a_t = -(k / m) * x_t
        elif gamma < omega_n:
            # Underdamped oscillation
            decay = math.exp(-gamma * t)
            cos_term = math.cos(omega_d * t)
            sin_term = math.sin(omega_d * t)
            x_t = decay * (c1 * cos_term + c2 * sin_term)
            v_t = -gamma * x_t + decay * (-c1 * omega_d * sin_term + c2 * omega_d * cos_term)
            a_t = -(k / m) * x_t - (c / m) * v_t
        else:
            # Critically damped or overdamped
            decay = math.exp(-gamma * t)
            x_t = decay * (x0 + (v0 + gamma * x0) * t)
            v_t = -gamma * x_t + decay * (v0 + gamma * x0)
            a_t = -(k / m) * x_t - (c / m) * v_t

        f_spring = -k * x_t
        ke = 0.5 * m * (v_t * v_t)
        pe = 0.5 * k * (x_t * x_t)

        graph_data.append([
            round(t, 4),
            round(x_t, 4),
            round(v_t, 4),
            round(a_t, 4),
            round(f_spring, 4),
            round(ke, 4),
            round(pe, 4),
        ])

    formulas_used = [
        "ω = √(k/m)",
        "x(t) = A·cos(ωt + φ)",
        "F = -kx",
    ]

    last_pt = graph_data[-1]
    final_x = last_pt[1]
    final_v = last_pt[2]
    final_a = last_pt[3]
    final_ke = last_pt[5]
    final_pe = last_pt[6]

    return {
        "natural_frequency": round(omega_n, 4),
        "period": round(period, 4),
        "amplitude": round(amplitude, 4),
        "graph_data": graph_data,
        "formulas_used": formulas_used,
        # Extended sandbox compatibility attributes
        "position": {
            "x": round(final_x, 4),
            "y": 0.0,
        },
        "velocity": {
            "x": round(final_v, 4),
            "y": 0.0,
        },
        "acceleration": {
            "x": round(final_a, 4),
            "y": 0.0,
        },
        "energy": {
            "kinetic": round(final_ke, 4),
            "potential": round(final_pe, 4),
            "total": round(final_ke + final_pe, 4),
        },
        "time_elapsed": round(total_duration, 4),
        "metrics": {
            "natural_frequency": round(omega_n, 4),
            "period": round(period, 4),
            "amplitude": round(amplitude, 4),
            "spring_constant": round(k, 4),
            "mass": round(m, 4),
            "damping_coefficient": round(c, 4),
        },
    }
