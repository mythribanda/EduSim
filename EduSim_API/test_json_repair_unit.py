import os
import sys
import json
import re

api_dir = r"c:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API"
os.chdir(api_dir)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.src.modules.tutor.scientific_validator import ScientificValidator, CANONICAL_FORMULAS

def repair_truncated_json(raw_text: str) -> tuple[dict | None, bool]:
    """
    Attempts to repair and parse a truncated or slightly malformed JSON string.
    Returns (parsed_dict, is_truncated).
    """
    if not raw_text or not raw_text.strip():
        return None, False

    text = raw_text.strip()
    
    # Strip markdown code blocks
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    start_idx = text.find("{")
    if start_idx == -1:
        return None, False

    candidate = text[start_idx:]

    # 1. Try strict JSON parse first
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed, False
    except json.JSONDecodeError:
        pass

    # 2. Try strict parse up to the last '}'
    last_brace = candidate.rfind("}")
    if last_brace != -1 and last_brace > 0:
        try:
            parsed = json.loads(candidate[: last_brace + 1])
            if isinstance(parsed, dict):
                return parsed, False
        except json.JSONDecodeError:
            pass

    # 3. Deterministic truncation repair:
    # Scan characters, track state (inside string, escaping), and unclosed containers (brackets/braces)
    stack = []
    in_string = False
    escape = False

    for ch in candidate:
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    repaired = candidate.rstrip()

    # If truncated inside a string literal, close the quote
    if in_string:
        # Avoid closing quote right after an escape backslash
        if repaired.endswith("\\"):
            repaired = repaired[:-1]
        repaired += '"'

    # Remove any dangling trailing commas or colons before closing containers
    repaired = re.sub(r',\s*$', '', repaired)
    repaired = re.sub(r':\s*$', ': ""', repaired)

    # Close open containers in LIFO order
    close_map = {"{": "}", "[": "]"}
    while stack:
        open_ch = stack.pop()
        # Clean any trailing comma before container close
        repaired = re.sub(r',\s*$', '', repaired)
        repaired += close_map[open_ch]

    try:
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return parsed, True
    except json.JSONDecodeError:
        pass

    # 4. Fallback: regex key-value extraction for partial salvage
    salvaged = {}
    title_m = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if title_m:
        salvaged["title"] = title_m.group(1).encode().decode('unicode_escape')

    qt_m = re.search(r'"queryType"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if qt_m:
        salvaged["queryType"] = qt_m.group(1).encode().decode('unicode_escape')

    # Extract concepts
    concepts_m = re.search(r'"concepts"\s*:\s*\[(.*?)\]', candidate, re.DOTALL)
    if concepts_m:
        raw_items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', concepts_m.group(1))
        salvaged["concepts"] = [it.encode().decode('unicode_escape') for it in raw_items]

    # Extract formulas array if present
    formulas_m = re.search(r'"formulas"\s*:\s*\[(.*?)\]', candidate, re.DOTALL)
    if formulas_m:
        # Try parsing formulas snippet as json array
        try:
            parsed_f = json.loads(f"[{formulas_m.group(1)}]")
            if isinstance(parsed_f, list):
                salvaged["formulas"] = parsed_f
        except Exception:
            pass

    # Extract explanation text up to end or next key
    exp_m = re.search(r'"explanation"\s*:\s*"(.*)', candidate, re.DOTALL)
    if exp_m:
        raw_exp = exp_m.group(1)
        # If it contains closing quote followed by summary
        sub_m = re.search(r'^(.*?)(?:"\s*,\s*"summary"|"\s*\})', raw_exp, re.DOTALL)
        if sub_m:
            salvaged["explanation"] = sub_m.group(1).replace(r'\"', '"').replace(r'\n', '\n')
        else:
            # Strip trailing quotes/braces if any
            salvaged["explanation"] = raw_exp.rstrip('"} \n\r\t').replace(r'\"', '"').replace(r'\n', '\n')

    summary_m = re.search(r'"summary"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if summary_m:
        salvaged["summary"] = summary_m.group(1).replace(r'\"', '"').replace(r'\n', '\n')

    if salvaged:
        return salvaged, True

    return None, False


print("repair_truncated_json defined successfully")
# Test Case 1: Valid strict JSON
tc1 = '{"title": "Test Title", "queryType": "concept", "concepts": ["c1", "c2"], "formulas": [{"formula": "F=ma", "name": "Force", "topic": "Physics", "meaning": "Newton"}], "explanation": "Valid text", "summary": "Valid summary"}'
p1, tr1 = repair_truncated_json(tc1)
assert p1 is not None and not tr1, f"TC1 failed: {p1}, {tr1}"
print("TC1 Passed (Valid JSON)")

# Test Case 2: JSON inside Markdown code fence
tc2 = '```json\n{"title": "Fence Title", "queryType": "concept", "concepts": ["c1"], "formulas": [], "explanation": "Fenced text", "summary": "Fenced summary"}\n```'
p2, tr2 = repair_truncated_json(tc2)
assert p2 is not None and not tr2 and p2["title"] == "Fence Title", f"TC2 failed: {p2}"
print("TC2 Passed (Markdown fence)")

# Test Case 3: Truncated inside explanation string (the user's exact issue!)
tc3 = '{"title": "Newton\'s First Law", "queryType": "concept", "concepts": ["Inertia", "Force"], "formulas": [{"formula": "\\\\Sigma \\\\vec{F} = 0", "name": "First Law", "topic": "Mechanics", "meaning": "Net force zero"}], "explanation": "Newton\'s First Law states that an object remains at rest unless acted upon by an external force.\\n\\nReal life examples:\\n1. Passengers in a bus.\\n2. A Car Braking: When a car brakes suddenly,'
p3, tr3 = repair_truncated_json(tc3)
assert p3 is not None and tr3 is True, f"TC3 failed to parse: {p3}"
assert p3["title"] == "Newton's First Law"
assert "Car Braking" in p3["explanation"]
assert len(p3["concepts"]) == 2
assert len(p3["formulas"]) == 1
print("TC3 Passed (Truncated inside string)")

# Test Case 4: Truncated inside formulas array
tc4 = '{"title": "Newton\'s Laws", "concepts": ["Inertia"], "formulas": [{"formula": "F=ma", "name": "Force"'
p4, tr4 = repair_truncated_json(tc4)
assert p4 is not None and tr4 is True, f"TC4 failed: {p4}"
assert p4["title"] == "Newton's Laws"
print("TC4 Passed (Truncated inside array)")

# Test Case 5: Completely non-JSON text
tc5 = "Here is an explanation of Newton's first law without any JSON."
p5, tr5 = repair_truncated_json(tc5)
assert p5 is None and tr5 is False
print("TC5 Passed (Completely non-JSON text)")

print("All repair_truncated_json unit tests passed successfully!")
