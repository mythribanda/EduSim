import json
import re

def sanitize_json_escapes(raw_json: str) -> str:
    """
    Sanitizes unescaped LaTeX backslashes in a JSON string.
    1. Escapes common LaTeX commands starting with standard escape characters (\f, \t, \r, \n, \b).
    2. Escapes any backslash not followed by valid JSON escape chars (", \, /, b, f, n, r, t, uXXXX).
    """
    # 1. LaTeX commands that start with JSON escape letters
    # e.g. \frac, \text, \tau, \theta, \times, \to, \tan, \right, \rho, \nabla, \nu, \beta, \bar, \begin
    latex_conflicts = [
        r"frac", r"forall",
        r"text", r"tau", r"theta", r"times", r"to", r"tan", r"top", r"tilde",
        r"right", r"rho", r"root", r"rangle",
        r"nabla", r"nu", r"neq", r"not", r"notin",
        r"beta", r"bar", r"begin", r"bf", r"bm", r"boldsymbol", r"bullet"
    ]
    # Regex: backslash followed by one of these words
    conflict_pattern = re.compile(r'\\(' + '|'.join(latex_conflicts) + r')\b')
    text = conflict_pattern.sub(r'\\\\\1', raw_json)

    # 2. Any backslash not followed by valid JSON escape character
    pattern = re.compile(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})')
    return pattern.sub(r'\\\\', text)

sample = r'''{
  "title": "Newton's First Law",
  "explanation": "Formula: $\sum \vec{F} = 0 \iff \vec{a} = 0$. Fraction: $\frac{1}{2}$ and Text: $\text{m/s}$ and $\beta$ and $\right$.",
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

sanitized = sanitize_json_escapes(sample)
parsed = json.loads(sanitized)
print("Sanitized loads SUCCESS!")
print("Parsed explanation:", parsed["explanation"])
print("Parsed formula:", parsed["formulas"][0]["formula"])
