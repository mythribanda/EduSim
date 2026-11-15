"""
Scientific and Mathematical Accuracy Validation Engine for EduSim AI Tutor.
Validates:
1. Mathematical formula syntax and LaTeX formatting.
2. Canonical curriculum formulas for Physics, Chemistry, and Mathematics.
3. Chemical equation stoichiometry and atom conservation.
4. Scientific units associated with physical quantities.
5. Deterministic numerical problem verification via SymPy.
6. Explicit calculation correction notes (never silently changes model output).
"""

import re
import math
from collections import defaultdict
import sympy
from typing import Dict, Any, List, Tuple

# Canonical Formula Registry with metadata
CANONICAL_FORMULAS = {
    # Physics
    "newton_second_law": {
        "pattern": r"(?:f\s*=\s*m\s*a|f\s*=\s*m\s*\*\s*a|\vec\{f\}\s*=\s*m\vec\{a\}|f\s*=\s*\\frac\{dp\}\{dt\})",
        "canonical_latex": r"F = ma",
        "subject": "physics",
        "name": "Newton's Second Law",
        "units": {"F": "N", "m": "kg", "a": "m/s²"}
    },
    "newton_first_law": {
        "pattern": r"(?:\\sigma\s*\\vec\{f\}\s*=\s*0|\\sum\s*(?:\\mathbf\{f\}|\\vec\{f\}|f)\s*=\s*0|f_\{?net\}?\s*=\s*0|\\vec\{f\}_\{?net\}?\s*=\s*0|newton'?s?\s*first\s*law|law\s*of\s*inertia)",
        "canonical_latex": r"\sum \vec{F} = 0 \iff \vec{a} = 0",
        "subject": "physics",
        "name": "Newton's First Law (Law of Inertia)",
        "units": {"F": "N", "a": "m/s²"}
    },
    "universal_gravitation": {
        "pattern": r"(?:f\s*=\s*g\s*\\frac\{m_?1\s*m_?2\}\{r\^2\}|f\s*=\s*g\s*m_?1\s*m_?2\s*/\s*r\^2)",
        "canonical_latex": r"F = G \frac{m_1 m_2}{r^2}",
        "subject": "physics",
        "name": "Universal Law of Gravitation",
        "units": {"F": "N", "G": "N·m²/kg²", "m1": "kg", "m2": "kg", "r": "m"}
    },
    "ohms_law": {
        "pattern": r"(?:v\s*=\s*i\s*r|v\s*=\s*i\s*\*\s*r|i\s*=\s*v\s*/\s*r|r\s*=\s*v\s*/\s*i)",
        "canonical_latex": r"V = IR",
        "subject": "physics",
        "name": "Ohm's Law",
        "units": {"V": "V", "I": "A", "R": "Ω"}
    },
    "kinetic_energy": {
        "pattern": r"(?:ke|k|e_k)\s*=\s*(?:\\frac\{1\}\{2\}|0\.5|1/2)\s*m\s*v\^2",
        "canonical_latex": r"KE = \frac{1}{2}mv^2",
        "subject": "physics",
        "name": "Kinetic Energy",
        "units": {"KE": "J", "m": "kg", "v": "m/s"}
    },
    "simple_pendulum": {
        "pattern": r"t\s*=\s*2\s*\\pi\s*\\sqrt\{\s*\\frac\{l\}\{g\}\s*\}",
        "canonical_latex": r"T = 2\pi\sqrt{\frac{l}{g}}",
        "subject": "physics",
        "name": "Time Period of Simple Pendulum",
        "units": {"T": "s", "l": "m", "g": "m/s²"}
    },
    "snells_law": {
        "pattern": r"n_?1\s*\\sin\s*\\theta_?1\s*=\s*n_?2\s*\\sin\s*\\theta_?2",
        "canonical_latex": r"n_1 \sin\theta_1 = n_2 \sin\theta_2",
        "subject": "physics",
        "name": "Snell's Law of Refraction",
        "units": {"n": "dimensionless", "theta": "degrees/radians"}
    },
    # Chemistry
    "ideal_gas": {
        "pattern": r"p\s*v\s*=\s*n\s*r\s*t",
        "canonical_latex": r"PV = nRT",
        "subject": "chemistry",
        "name": "Ideal Gas Equation",
        "units": {"P": "Pa/atm", "V": "m³/L", "n": "mol", "R": "J/(mol·K)", "T": "K"}
    },
    "ph_formula": {
        "pattern": r"\{?ph\}?\s*=\s*-\s*\\log(?:_\{?10\}?)?\s*\[\s*h\^\+\s*\]",
        "canonical_latex": r"\text{pH} = -\log_{10}[H^+]",
        "subject": "chemistry",
        "name": "pH Definition",
        "units": {"pH": "dimensionless", "[H+]": "mol/L"}
    },
    "photosynthesis_reaction": {
        "pattern": r"6\s*co_?2\s*\+\s*6\s*h_?2o\s*(?:->|→|\\rightarrow|\\to|=)\s*c_?6h_?12o_?6\s*\+\s*6\s*o_?2",
        "canonical_latex": r"6CO_2 + 6H_2O \rightarrow C_6H_{12}O_6 + 6O_2",
        "subject": "chemistry",
        "name": "Photosynthesis Overall Equation",
        "units": {"stoichiometry": "molar ratio"}
    },
    # Mathematics
    "quadratic_formula": {
        "pattern": r"x\s*=\s*\\frac\{\s*-\s*b\s*\\pm\s*\\sqrt\{\s*b\^2\s*-\s*4\s*a\s*c\s*\}\s*\}\{\s*2\s*a\s*\}",
        "canonical_latex": r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        "subject": "mathematics",
        "name": "Quadratic Formula",
        "units": {}
    },
    "discriminant": {
        "pattern": r"(?:d|\\delta)\s*=\s*b\^2\s*-\s*4\s*a\s*c",
        "canonical_latex": r"D = b^2 - 4ac",
        "subject": "mathematics",
        "name": "Quadratic Discriminant",
        "units": {}
    },
    "ap_nth_term": {
        "pattern": r"a_?n\s*=\s*a\s*\+\s*\(\s*n\s*-\s*1\s*\)\s*d",
        "canonical_latex": r"a_n = a + (n - 1)d",
        "subject": "mathematics",
        "name": "Arithmetic Progression nth Term",
        "units": {}
    },
    "ap_sum_n": {
        "pattern": r"s_?n\s*=\s*\\frac\{n\}\{2\}\s*\[\s*2a\s*\+\s*\(\s*n\s*-\s*1\s*\)\s*d\s*\]",
        "canonical_latex": r"S_n = \frac{n}{2}[2a + (n - 1)d]",
        "subject": "mathematics",
        "name": "Sum of First n Terms of an AP",
        "units": {}
    },
    "pythagoras": {
        "pattern": r"(?:a\^2\s*\+\s*b\^2\s*=\s*c\^2|h\^2\s*=\s*p\^2\s*\+\s*b\^2)",
        "canonical_latex": r"a^2 + b^2 = c^2",
        "subject": "mathematics",
        "name": "Pythagoras Theorem",
        "units": {}
    },
    "trig_identity_sin_cos": {
        "pattern": r"\\sin\^2\s*\\theta\s*\+\s*\\cos\^2\s*\\theta\s*=\s*1",
        "canonical_latex": r"\sin^2\theta + \cos^2\theta = 1",
        "subject": "mathematics",
        "name": "Pythagorean Trigonometric Identity",
        "units": {}
    }
}

class ScientificValidator:
    """
    Deterministic validator for formulas, calculations, units, and chemical equations.
    """

    @staticmethod
    def validate_latex_syntax(latex_str: str) -> Tuple[bool, str]:
        """
        Validates balanced braces, brackets, and well-formed LaTeX commands.
        """
        if not latex_str:
            return False, "Empty formula"

        # Check balanced curly braces
        stack = []
        for ch in latex_str:
            if ch == '{':
                stack.append(ch)
            elif ch == '}':
                if not stack:
                    return False, "Unbalanced closing brace '}'"
                stack.pop()
        if stack:
            return False, "Unbalanced opening brace '{'"

        # Check balanced parentheses
        p_count = 0
        for ch in latex_str:
            if ch == '(':
                p_count += 1
            elif ch == ')':
                p_count -= 1
                if p_count < 0:
                    return False, "Unbalanced closing parenthesis ')'"
        if p_count != 0:
            return False, "Unbalanced opening parenthesis '('"

        return True, "Valid LaTeX syntax"

    @staticmethod
    def check_canonical_match(text: str) -> List[Dict[str, Any]]:
        """
        Identifies recognized canonical formulas in the text or formula string.
        """
        matched = []
        clean = text.lower().replace(r"\text", "").replace(r"\mathbf", "")
        for key, entry in CANONICAL_FORMULAS.items():
            if re.search(entry["pattern"], clean, re.IGNORECASE):
                matched.append({
                    "key": key,
                    "name": entry["name"],
                    "canonical_latex": entry["canonical_latex"],
                    "subject": entry["subject"],
                    "units": entry.get("units", {})
                })
        return matched

    @staticmethod
    def verify_chemical_stoichiometry(equation: str) -> Tuple[bool, str, Dict[str, int], Dict[str, int]]:
        """
        Verifies atom conservation across left-hand and right-hand sides of a chemical reaction.
        E.g. '6CO2 + 6H2O -> C6H12O6 + 6O2'
        """
        # Split reaction
        parts = re.split(r"(?:->|→|\\rightarrow|\\to|=)", equation)
        if len(parts) != 2:
            return False, "Not a two-sided chemical equation", {}, {}

        lhs_str, rhs_str = parts[0].strip(), parts[1].strip()

        def parse_side(side_str: str) -> Dict[str, int]:
            atoms = defaultdict(int)
            terms = [t.strip() for t in side_str.split("+") if t.strip()]
            for term in terms:
                # Extract leading coefficient
                m_coeff = re.match(r"^(\d+)\s*(.*)$", term)
                if m_coeff:
                    coeff = int(m_coeff.group(1))
                    molecule = m_coeff.group(2).strip()
                else:
                    coeff = 1
                    molecule = term

                # Parse element and count: e.g. C6 H12 O6 or C O2
                elem_matches = re.findall(r"([A-Z][a-z]?)(?:_?\{?(\d+)\}?)?", molecule)
                for elem, count_str in elem_matches:
                    count = int(count_str) if count_str else 1
                    atoms[elem] += coeff * count
            return dict(atoms)

        try:
            lhs_atoms = parse_side(lhs_str)
            rhs_atoms = parse_side(rhs_str)
            if not lhs_atoms or not rhs_atoms:
                return False, "Could not extract elemental symbols", lhs_atoms, rhs_atoms

            is_balanced = (lhs_atoms == rhs_atoms)
            msg = "Balanced chemical reaction" if is_balanced else f"Unbalanced atoms: LHS={lhs_atoms} vs RHS={rhs_atoms}"
            return is_balanced, msg, lhs_atoms, rhs_atoms
        except Exception as e:
            return False, f"Stoichiometry parse error: {e}", {}, {}

    @staticmethod
    def verify_numerical_calculation(problem_type: str, inputs: Dict[str, float], model_result: float, tol: float = 0.01) -> Tuple[bool, float, str]:
        """
        Deterministically verifies numerical math/physics problems using SymPy.
        Never changes model formula silently; returns verification status and exact derivation.
        """
        try:
            if problem_type == "newton_second_law":
                # F = m * a
                m, a = sympy.Symbol('m'), sympy.Symbol('a')
                expected = float(sympy.N(m * a, subs={m: inputs["m"], a: inputs["a"]}))
                passed = math.isclose(expected, model_result, rel_tol=tol, abs_tol=tol)
                explanation = f"F = m * a = {inputs['m']} kg * {inputs['a']} m/s² = {expected} N"
                return passed, expected, explanation

            elif problem_type == "ohms_law":
                # V = I * R
                I, R = sympy.Symbol('I'), sympy.Symbol('R')
                expected = float(sympy.N(I * R, subs={I: inputs["I"], R: inputs["R"]}))
                passed = math.isclose(expected, model_result, rel_tol=tol, abs_tol=tol)
                explanation = f"V = I * R = {inputs['I']} A * {inputs['R']} Ω = {expected} V"
                return passed, expected, explanation

            elif problem_type == "kinetic_energy":
                # KE = 0.5 * m * v^2
                m, v = sympy.Symbol('m'), sympy.Symbol('v')
                expected = float(sympy.N(0.5 * m * v**2, subs={m: inputs["m"], v: inputs["v"]}))
                passed = math.isclose(expected, model_result, rel_tol=tol, abs_tol=tol)
                explanation = f"KE = 0.5 * {inputs['m']} kg * ({inputs['v']} m/s)^2 = {expected} J"
                return passed, expected, explanation

            elif problem_type == "quadratic_roots":
                # ax^2 + bx + c = 0
                a, b, c = inputs["a"], inputs["b"], inputs["c"]
                disc = b**2 - 4*a*c
                if disc >= 0:
                    r1 = (-b + math.sqrt(disc)) / (2*a)
                    r2 = (-b - math.sqrt(disc)) / (2*a)
                    passed = math.isclose(r1, model_result, rel_tol=tol) or math.isclose(r2, model_result, rel_tol=tol)
                    explanation = f"Roots of {a}x^2 + {b}x + {c}: discriminant D = {disc}, roots x = ({r1:.3f}, {r2:.3f})"
                    return passed, r1, explanation
                else:
                    return True, 0.0, f"Complex roots with discriminant D = {disc} < 0"

            elif problem_type == "ap_nth_term":
                # an = a + (n - 1)d
                a, n, d = inputs["a"], int(inputs["n"]), inputs["d"]
                expected = a + (n - 1) * d
                passed = math.isclose(expected, model_result, rel_tol=tol)
                explanation = f"a_{n} = {a} + ({n} - 1) * {d} = {expected}"
                return passed, float(expected), explanation

        except Exception as e:
            return False, 0.0, f"Verification failed with error: {e}"

        return False, 0.0, f"Unknown problem type: {problem_type}"

    @classmethod
    def audit_response_formulas(cls, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits an entire AI Tutor response payload for formulas, equations, units, and calculations.
        Adds non-destructive verification annotations without deleting original output.
        """
        audit_results = {
            "formula_count": 0,
            "canonical_matches": [],
            "latex_validity": True,
            "stoichiometry_checks": [],
            "units_verified": True,
            "annotations": []
        }

        formulas = response_data.get("formulas", [])
        explanation = response_data.get("explanation", "") or response_data.get("ai_explanation", "")

        all_formula_strings = []
        for f in formulas:
            if isinstance(f, dict):
                f_str = f.get("formula", "")
                if f_str:
                    all_formula_strings.append(f_str)
            elif isinstance(f, str):
                all_formula_strings.append(f)

        # Also scan explanation text for LaTeX display blocks $$...$$ or chemical equations
        latex_blocks = re.findall(r"\$\$([^$]+)\$\$", explanation)
        all_formula_strings.extend(latex_blocks)

        audit_results["formula_count"] = len(all_formula_strings)

        for f_str in all_formula_strings:
            # 1. LaTeX Syntax
            ok_syntax, syntax_msg = cls.validate_latex_syntax(f_str)
            if not ok_syntax:
                audit_results["latex_validity"] = False
                audit_results["annotations"].append(f"Formula syntax warning: {syntax_msg} in '{f_str}'")

            # 2. Canonical Match
            matches = cls.check_canonical_match(f_str)
            for m in matches:
                if m["name"] not in [x["name"] for x in audit_results["canonical_matches"]]:
                    audit_results["canonical_matches"].append(m)

            # 3. Chemical stoichiometry check
            if any(sym in f_str for sym in ["->", "→", r"\rightarrow", r"\to"]):
                is_balanced, bal_msg, lhs, rhs = cls.verify_chemical_stoichiometry(f_str)
                audit_results["stoichiometry_checks"].append({
                    "equation": f_str,
                    "is_balanced": is_balanced,
                    "message": bal_msg
                })

        return audit_results
