import json
import re

def sanitize_json_escapes(raw_json: str) -> str:
    """
    Sanitizes unescaped LaTeX backslashes in a JSON string.
    Replaces any backslash not followed by valid JSON escape chars (", \, /, b, f, n, r, t, uXXXX)
    with double backslash so json.loads succeeds.
    """
    pattern = re.compile(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})')
    return pattern.sub(r'\\\\', raw_json)

sample = r'''{
  "title": "Newton's First Law",
  "explanation": "Formula: $\sum \vec{F} = 0 \iff \vec{a} = 0$. Example \frac{1}{2}.",
  "formulas": [
    {
      "formula": "\sum \vec{F} = 0 \iff \vec{a} = 0",
      "name": "Newton's First Law",
      "topic": "Physics",
      "meaning": "Zero net force"
    }
  ],
  "summary": "Law of inertia"
}'''

try:
    json.loads(sample)
    print("Direct loads worked")
except Exception as e:
    print("Direct loads failed:", e)

sanitized = sanitize_json_escapes(sample)
parsed = json.loads(sanitized)
print("Sanitized loads SUCCESS!")
print("Parsed explanation:", parsed["explanation"])
print("Parsed formula:", parsed["formulas"][0]["formula"])
