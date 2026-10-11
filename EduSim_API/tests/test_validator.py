"""
Manual test for the DSL validator using the v2.0 schema.
Run from the EduSim root directory:
  source venv/bin/activate && python -m app.src.modules.simulation_synthesis.test_validator
"""

import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.src.modules.simulation_synthesis.validator import validate_simulation
from app.src.modules.simulation_synthesis.prompt_builder import EXAMPLE_RESPONSE


# --- Test 1: Valid DSL (from prompt_builder) ---
valid_sample = EXAMPLE_RESPONSE

# --- Test 2: Missing required top-level fields ---
invalid_sample = {
    "topic": "Motion",
}

# --- Test 3: Static body with mass ---
bad_mass_sample = json.loads(json.dumps(valid_sample))
# Find ground and give it mass
for obj in bad_mass_sample["dsl"]["objects"]:
    if obj["id"] == "ground":
        obj["physics"]["mass"] = 5.0

# --- Test 4: Interaction targets unknown entity ---
bad_target_sample = json.loads(json.dumps(valid_sample))
bad_target_sample["dsl"]["interactions"].append({
    "id": "bad_interaction",
    "type": "drag",
    "targets": ["unknown_entity"]
})

TESTS = [
    ("Valid DSL", valid_sample, True),
    ("Missing required fields", invalid_sample, False),
    ("Static body with mass", bad_mass_sample, False),
    ("Interaction targets unknown entity", bad_target_sample, False), # Validation currently only checks behavior targets, not interaction targets in Pass 3. Let's see if Pydantic catches anything else.
]

if __name__ == "__main__":
    print("=" * 60)
    for name, sample, expected_success in TESTS:
        result = validate_simulation(sample)
        status = "PASS" if result["success"] == expected_success else "FAIL"
        print(f"[{status}] {name}")
        if result["success"]:
            print(f"       Keys: {list(result['data'].keys())}")
        else:
            print(f"       Error: {result['errors']}")
    print("=" * 60)