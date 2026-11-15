from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "EduSim_API"))

import json
import re

# Simulate what Ollama outputs when generating JSON with LaTeX
raw_ollama_output = r'''{
  "title": "Newton's First Law of Motion",
  "queryType": "concept",
  "concepts": ["Inertia", "Net Force", "Equilibrium"],
  "formulas": [
    {
      "formula": "\sum \vec{F} = 0 \iff \vec{a} = 0",
      "name": "Newton's First Law Condition",
      "topic": "Newton's Laws of Motion",
      "meaning": "When net external force is zero, acceleration is zero."
    }
  ],
  "explanation": "Newton's first law of motion, often called the law of inertia, states that an object remains at rest or in uniform motion unless acted upon by a net external force. Mathematically: $\sum \vec{F} = 0 \iff \vec{a} = 0$.\n\nThree real-life examples:\n1. A passenger jerking forward when a bus stops.\n2. A hockey puck gliding on ice.\n3. A book resting on a table.",
  "summary": "Newton's first law defines inertia: without an unbalanced external force, an object's velocity remains constant."
}'''

print("Raw string length:", len(raw_ollama_output))
try:
    parsed = json.loads(raw_ollama_output)
    print("Direct json.loads SUCCESS")
except Exception as e:
    print("Direct json.loads FAILED:", e)

# Test with current repair_truncated_json
from EduSim_API.app.src.modules.tutor.service import repair_truncated_json, parse_structured_tutor_response

parsed, is_trunc = repair_truncated_json(raw_ollama_output)
print("repair_truncated_json returned:", "None" if parsed is None else list(parsed.keys()), "is_truncated:", is_trunc)

res = parse_structured_tutor_response(raw_ollama_output, "Explain Newton's first law with its mathematical representation and three real-life examples.")
print("parse_structured_tutor_response result keys:", list(res.keys()))
print("explanation type and sample:", type(res.get("explanation")), repr(res.get("explanation"))[:200])
print("formulas count:", len(res.get("formulas", [])))
print("formulas:", res.get("formulas"))
