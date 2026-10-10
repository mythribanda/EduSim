"""
Automated unit tests for static deterministic physics simulation modules.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "EduSim_API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.src.modules.simulations.static.projectile_motion import compute as compute_projectile
from app.src.modules.simulations.static.pendulum import compute as compute_pendulum
from app.src.modules.simulations.static.free_fall import compute as compute_free_fall
from app.src.modules.simulations.static.simulation_registry import (
    list_static_simulations,
    get_static_simulation,
    run_static_simulation,
)


def test_projectile_motion():
    print("Testing Projectile Motion...")
    res = compute_projectile({
        "initial_velocity": 25.0,
        "launch_angle": 45.0,
        "gravity": 9.81,
        "mass": 2.0,
        "initial_height": 0.0,
    })

    assert "max_height" in res and res["max_height"] > 0
    assert "range" in res and res["range"] > 0
    assert "time_of_flight" in res and res["time_of_flight"] > 0
    assert "final_velocity" in res and res["final_velocity"] > 0
    assert "graph_data" in res and len(res["graph_data"]) == 60
    assert len(res["graph_data"][0]) == 5  # [t, x, y, vx, vy]
    assert "formulas_used" in res and len(res["formulas_used"]) > 0
    print("  -> Projectile Motion PASSED (Flight Time: %s s, Range: %s m, Samples: %s)" % (res["time_of_flight"], res["range"], len(res["graph_data"])))


def test_pendulum():
    print("Testing Pendulum...")
    res = compute_pendulum({
        "length": 2.5,
        "initial_angle": 30.0,
        "gravity": 9.81,
        "mass": 1.5,
        "damping": 0.02,
    })

    assert "period" in res and res["period"] > 0
    assert "max_speed" in res and res["max_speed"] > 0
    assert "max_height" in res and res["max_height"] > 0
    assert "graph_data" in res and len(res["graph_data"]) == 120
    assert len(res["graph_data"][0]) == 5  # [t, angle, angular_velocity, height, speed]
    assert "formulas_used" in res and len(res["formulas_used"]) == 2
    print("  -> Pendulum PASSED (Period: %s s, Max Speed: %s m/s, Max Height: %s m)" % (res["period"], res["max_speed"], res["max_height"]))


def test_free_fall():
    print("Testing Free Fall...")
    # 1. Without air resistance
    res_ideal = compute_free_fall({
        "initial_height": 50.0,
        "initial_velocity": 0.0,
        "gravity": 9.81,
        "mass": 1.0,
        "air_resistance": False,
    })

    assert "time_to_ground" in res_ideal and res_ideal["time_to_ground"] > 0
    assert "final_velocity" in res_ideal and res_ideal["final_velocity"] > 0
    assert "graph_data" in res_ideal and len(res_ideal["graph_data"]) == 60
    assert len(res_ideal["graph_data"][0]) == 4  # [t, height, velocity, acceleration]
    assert "formulas_used" in res_ideal and len(res_ideal["formulas_used"]) == 2

    # 2. With air resistance (Euler method)
    res_drag = compute_free_fall({
        "initial_height": 50.0,
        "initial_velocity": 0.0,
        "gravity": 9.81,
        "mass": 1.0,
        "air_resistance": True,
        "drag_coefficient": 0.47,
    })

    assert "time_to_ground" in res_drag and res_drag["time_to_ground"] > 0
    assert "final_velocity" in res_drag and res_drag["final_velocity"] > 0
    assert "graph_data" in res_drag and len(res_drag["graph_data"]) == 60
    assert len(res_drag["graph_data"][0]) == 4  # [t, height, velocity, acceleration]
    # Drag slows down the fall, so time to ground is longer
    assert res_drag["time_to_ground"] >= res_ideal["time_to_ground"]
    print("  -> Free Fall PASSED (Ideal Time: %s s, Drag Time: %s s, Ideal V: %s m/s, Drag V: %s m/s)" % (
        res_ideal["time_to_ground"], res_drag["time_to_ground"],
        res_ideal["final_velocity"], res_drag["final_velocity"]
    ))


def test_collision():
    print("Testing Collision...")
    from app.src.modules.simulations.static.collision import compute as compute_coll

    # 1. Elastic collision
    res_elastic = compute_coll({
        "mass1": 2.0,
        "mass2": 1.0,
        "velocity1": 5.0,
        "velocity2": 0.0,
        "collision_type": "elastic",
    })

    assert "final_velocity1" in res_elastic
    assert "final_velocity2" in res_elastic
    assert "kinetic_energy_before" in res_elastic
    assert "kinetic_energy_after" in res_elastic
    assert "energy_lost" in res_elastic
    assert "momentum_before" in res_elastic
    assert "momentum_after" in res_elastic
    assert "graph_data" in res_elastic and len(res_elastic["graph_data"]) == 60
    assert "formulas_used" in res_elastic and len(res_elastic["formulas_used"]) > 0
    # In elastic collision, energy lost is ~0 and momentum is conserved
    assert abs(res_elastic["energy_lost"]) < 1e-4
    assert abs(res_elastic["momentum_before"] - res_elastic["momentum_after"]) < 1e-4

    # 2. Perfectly Inelastic collision (objects stick together)
    res_inelastic = compute_coll({
        "mass1": 2.0,
        "mass2": 1.0,
        "velocity1": 6.0,
        "velocity2": 0.0,
        "collision_type": "perfectly_inelastic",
    })
    # Both objects have same final velocity
    assert abs(res_inelastic["final_velocity1"] - res_inelastic["final_velocity2"]) < 1e-4
    assert res_inelastic["energy_lost"] > 0
    assert abs(res_inelastic["momentum_before"] - res_inelastic["momentum_after"]) < 1e-4

    print("  -> Collision PASSED (Elastic v1: %s, v2: %s | Inelastic v: %s, energy lost: %s J)" % (
        res_elastic["final_velocity1"], res_elastic["final_velocity2"],
        res_inelastic["final_velocity1"], res_inelastic["energy_lost"]
    ))


def test_spring_mass():
    print("Testing Spring-Mass...")
    from app.src.modules.simulations.static.spring_mass import compute as compute_sm

    # 1. Undamped harmonic motion
    res_undamped = compute_sm({
        "spring_constant": 10.0,
        "mass": 0.5,
        "initial_displacement": 0.2,
        "initial_velocity": 0.0,
        "damping_coefficient": 0.0,
    })

    assert "natural_frequency" in res_undamped and res_undamped["natural_frequency"] > 0
    assert "period" in res_undamped and res_undamped["period"] > 0
    assert "amplitude" in res_undamped and res_undamped["amplitude"] > 0
    assert "graph_data" in res_undamped and len(res_undamped["graph_data"]) == 120
    assert len(res_undamped["graph_data"][0]) == 7  # [t, x, v, a, f_spring, ke, pe]
    assert "formulas_used" in res_undamped and len(res_undamped["formulas_used"]) == 3

    # 2. Damped harmonic motion
    res_damped = compute_sm({
        "spring_constant": 10.0,
        "mass": 0.5,
        "initial_displacement": 0.2,
        "initial_velocity": 0.0,
        "damping_coefficient": 0.2,
    })
    assert res_damped["period"] > 0
    # Damped final energy should be lower than initial energy
    assert res_damped["energy"]["total"] < res_undamped["energy"]["total"]

    print("  -> Spring-Mass PASSED (omega: %s rad/s, T: %s s, A: %s m)" % (
        res_undamped["natural_frequency"], res_undamped["period"], res_undamped["amplitude"]
    ))


def test_inclined_plane():
    print("Testing Inclined Plane...")
    from app.src.modules.simulations.static.inclined_plane import compute as compute_ip

    # 1. Frictionless motion
    res_frictionless = compute_ip({
        "mass": 2.0,
        "angle": 30.0,
        "gravity": 9.81,
        "friction_coefficient": 0.0,
        "initial_velocity": 0.0,
        "slope_length": 5.0,
    })

    assert "acceleration" in res_frictionless and res_frictionless["acceleration"] > 0
    assert "normal_force" in res_frictionless and res_frictionless["normal_force"] > 0
    assert "friction_force" in res_frictionless and res_frictionless["friction_force"] == 0.0
    assert "net_force" in res_frictionless and res_frictionless["net_force"] > 0
    assert "time_to_bottom" in res_frictionless and res_frictionless["time_to_bottom"] > 0
    assert "final_velocity" in res_frictionless and res_frictionless["final_velocity"] > 0
    assert res_frictionless["will_move"] is True
    assert "graph_data" in res_frictionless and len(res_frictionless["graph_data"]) == 60
    assert "formulas_used" in res_frictionless and len(res_frictionless["formulas_used"]) == 2

    # 2. Static friction exceeds gravity component
    res_static = compute_ip({
        "mass": 2.0,
        "angle": 15.0,
        "gravity": 9.81,
        "friction_coefficient": 0.8,
        "initial_velocity": 0.0,
        "slope_length": 5.0,
    })
    assert res_static["will_move"] is False
    assert res_static["acceleration"] == 0.0
    assert res_static["time_to_bottom"] == 0.0

    print("  -> Inclined Plane PASSED (a: %s m/s², t_bottom: %s s, v_final: %s m/s)" % (
        res_frictionless["acceleration"], res_frictionless["time_to_bottom"], res_frictionless["final_velocity"]
    ))


def test_registry():
    print("Testing Simulation Registry...")
    sims = list_static_simulations()
    assert len(sims) == 6
    ids = [s["id"] for s in sims]
    assert "projectile-motion" in ids
    assert "pendulum" in ids
    assert "free-fall" in ids
    assert "collision" in ids
    assert "spring-mass" in ids
    assert "inclined-plane" in ids

    sim_meta = get_static_simulation("inclined-plane")
    assert sim_meta is not None
    assert "parameters_schema" in sim_meta

    run_res = run_static_simulation("inclined-plane", {"angle": 45.0, "mass": 1.0})
    assert run_res["simulation_id"] == "inclined-plane"
    assert "state" in run_res
    print("  -> Simulation Registry PASSED")


def test_explain_simulation_endpoint():
    print("Testing AI Explain Endpoint...")
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    payload = {
        "simulation_id": "projectile-motion",
        "params": {"initial_velocity": 20, "launch_angle": 45, "gravity": 9.81},
        "result": {"max_height": 10.2, "range": 40.8, "time_of_flight": 2.89},
        "student_question": "Why did the ball go higher when I increased the angle?"
    }
    response = client.post("/api/simulations/explain", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "explanation" in data
    explanation = data["explanation"]
    assert isinstance(explanation, str)
    assert len(explanation) > 0
    words = explanation.split()
    assert len(words) <= 100
    # Ensure plain text (no markdown headings, code blocks, bold markers)
    assert "```" not in explanation
    assert "**" not in explanation
    assert not explanation.startswith("#")
    print(f"  -> AI Explain PASSED (words: {len(words)})")


if __name__ == "__main__":
    print("=" * 60)
    test_projectile_motion()
    test_pendulum()
    test_free_fall()
    test_collision()
    test_spring_mass()
    test_inclined_plane()
    test_registry()
    test_explain_simulation_endpoint()
    print("=" * 60)
    print("ALL STATIC SIMULATION TESTS PASSED SUCCESSFULLY!")


