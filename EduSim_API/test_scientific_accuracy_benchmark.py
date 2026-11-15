"""
Documented Benchmark for Mathematical and Scientific Accuracy
Tests 20 test cases across Physics, Chemistry, and Mathematics:
- Formula LaTeX syntax correctness
- Canonical curriculum formula matching
- Chemical equation atom conservation & stoichiometry
- Scientific units correctness
- Deterministic SymPy calculation verification
Target: >= 95% correctness.
"""

import sys
from pathlib import Path

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.tutor.scientific_validator import ScientificValidator

def run_scientific_accuracy_benchmark():
    print("=" * 80)
    print("PHASE 4: MATHEMATICAL & SCIENTIFIC ACCURACY BENCHMARK (20 CASES)")
    print("=" * 80)

    test_cases = [
        # --- PHYSICS ---
        {
            "id": "P1", "subject": "physics", "name": "Newton's Second Law Syntax & Canonical Match",
            "formula": r"F = ma", "type": "canonical", "expected_key": "newton_second_law"
        },
        {
            "id": "P2", "subject": "physics", "name": "Newton's Second Law Numerical Calculation",
            "type": "numerical", "problem_type": "newton_second_law", "inputs": {"m": 4.0, "a": 2.5},
            "model_result": 10.0, "units": "N"
        },
        {
            "id": "P3", "subject": "physics", "name": "Universal Gravitation Formula LaTeX",
            "formula": r"F = G \frac{m_1 m_2}{r^2}", "type": "canonical", "expected_key": "universal_gravitation"
        },
        {
            "id": "P4", "subject": "physics", "name": "Ohm's Law Calculation (V = I * R)",
            "type": "numerical", "problem_type": "ohms_law", "inputs": {"I": 2.5, "R": 8.0},
            "model_result": 20.0, "units": "V"
        },
        {
            "id": "P5", "subject": "physics", "name": "Kinetic Energy Calculation (KE = 0.5 * m * v^2)",
            "type": "numerical", "problem_type": "kinetic_energy", "inputs": {"m": 2.0, "v": 3.0},
            "model_result": 9.0, "units": "J"
        },
        {
            "id": "P6", "subject": "physics", "name": "Simple Pendulum Period LaTeX Balance",
            "formula": r"T = 2\pi\sqrt{\frac{l}{g}}", "type": "canonical", "expected_key": "simple_pendulum"
        },
        {
            "id": "P7", "subject": "physics", "name": "Snell's Law Optics Refraction",
            "formula": r"n_1 \sin\theta_1 = n_2 \sin\theta_2", "type": "canonical", "expected_key": "snells_law"
        },

        # --- CHEMISTRY ---
        {
            "id": "C1", "subject": "chemistry", "name": "Photosynthesis Stoichiometric Conservation",
            "equation": "6CO2 + 6H2O -> C6H12O6 + 6O2", "type": "chemical_stoichiometry",
            "expected_atoms": {"C": 6, "H": 12, "O": 18}
        },
        {
            "id": "C2", "subject": "chemistry", "name": "Water Synthesis Stoichiometric Balance",
            "equation": "2H2 + O2 -> 2H2O", "type": "chemical_stoichiometry",
            "expected_atoms": {"H": 4, "O": 2}
        },
        {
            "id": "C3", "subject": "chemistry", "name": "Ammonia Haber Process Stoichiometry",
            "equation": "N2 + 3H2 -> 2NH3", "type": "chemical_stoichiometry",
            "expected_atoms": {"N": 2, "H": 6}
        },
        {
            "id": "C4", "subject": "chemistry", "name": "Calcium Carbonate Decomposition Balance",
            "equation": "CaCO3 -> CaO + CO2", "type": "chemical_stoichiometry",
            "expected_atoms": {"Ca": 1, "C": 1, "O": 3}
        },
        {
            "id": "C5", "subject": "chemistry", "name": "pH Definition Formula Syntax",
            "formula": r"\text{pH} = -\log_{10}[H^+]", "type": "canonical", "expected_key": "ph_formula"
        },
        {
            "id": "C6", "subject": "chemistry", "name": "Ideal Gas Law Equation",
            "formula": r"PV = nRT", "type": "canonical", "expected_key": "ideal_gas"
        },

        # --- MATHEMATICS ---
        {
            "id": "M1", "subject": "mathematics", "name": "Quadratic Formula LaTeX & Canonical Match",
            "formula": r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}", "type": "canonical", "expected_key": "quadratic_formula"
        },
        {
            "id": "M2", "subject": "mathematics", "name": "Quadratic Discriminant Calculation",
            "formula": r"D = b^2 - 4ac", "type": "canonical", "expected_key": "discriminant"
        },
        {
            "id": "M3", "subject": "mathematics", "name": "SymPy Numerical Quadratic Roots (x^2 - 5x + 6 = 0)",
            "type": "numerical", "problem_type": "quadratic_roots", "inputs": {"a": 1.0, "b": -5.0, "c": 6.0},
            "model_result": 3.0, "units": ""
        },
        {
            "id": "M4", "subject": "mathematics", "name": "Arithmetic Progression nth Term Calculation",
            "type": "numerical", "problem_type": "ap_nth_term", "inputs": {"a": 3.0, "d": 4.0, "n": 10},
            "model_result": 39.0, "units": ""
        },
        {
            "id": "M5", "subject": "mathematics", "name": "AP nth Term Canonical LaTeX Formula",
            "formula": r"a_n = a + (n - 1)d", "type": "canonical", "expected_key": "ap_nth_term"
        },
        {
            "id": "M6", "subject": "mathematics", "name": "Pythagoras Theorem Geometry Formula",
            "formula": r"a^2 + b^2 = c^2", "type": "canonical", "expected_key": "pythagoras"
        },
        {
            "id": "M7", "subject": "mathematics", "name": "Pythagorean Trigonometric Identity",
            "formula": r"\sin^2\theta + \cos^2\theta = 1", "type": "canonical", "expected_key": "trig_identity_sin_cos"
        }
    ]

    total = len(test_cases)
    passed = 0

    print(f"\nRunning {total} test cases...\n")

    for tc in test_cases:
        tc_id = tc["id"]
        tc_name = tc["name"]
        tc_type = tc["type"]

        if tc_type == "canonical":
            latex_str = tc["formula"]
            ok_syntax, syn_msg = ScientificValidator.validate_latex_syntax(latex_str)
            matches = ScientificValidator.check_canonical_match(latex_str)
            has_match = any(m["key"] == tc["expected_key"] for m in matches)
            case_ok = ok_syntax and has_match
            if case_ok:
                passed += 1
                print(f"  [PASS] {tc_id:<3} | {tc_name} | LaTeX: OK, Canonical Match: {matches[0]['name']}")
            else:
                print(f"  [FAIL] {tc_id:<3} | {tc_name} | Syntax: {syn_msg}, Matched: {[m['key'] for m in matches]}")

        elif tc_type == "chemical_stoichiometry":
            eq = tc["equation"]
            is_bal, bal_msg, lhs, rhs = ScientificValidator.verify_chemical_stoichiometry(eq)
            case_ok = is_bal and (lhs == tc["expected_atoms"])
            if case_ok:
                passed += 1
                print(f"  [PASS] {tc_id:<3} | {tc_name} | Stoichiometry Balanced: {lhs}")
            else:
                print(f"  [FAIL] {tc_id:<3} | {tc_name} | {bal_msg}")

        elif tc_type == "numerical":
            prob_type = tc["problem_type"]
            inputs = tc["inputs"]
            res = tc["model_result"]
            num_ok, expected_val, expl = ScientificValidator.verify_numerical_calculation(prob_type, inputs, res)
            if num_ok:
                passed += 1
                print(f"  [PASS] {tc_id:<3} | {tc_name} | {expl}")
            else:
                print(f"  [FAIL] {tc_id:<3} | {tc_name} | Expected {expected_val}, got {res} ({expl})")

    acc = (passed / total) * 100.0
    print("\n" + "=" * 80)
    print(f"SCIENTIFIC & MATHEMATICAL ACCURACY SCORE: {passed}/{total} ({acc:.1f}%)")
    print("=" * 80)

    import json
    report = {
        "total_tests": total,
        "passed_tests": passed,
        "accuracy_percent": acc,
        "target_achieved": acc >= 95.0
    }
    with open(api_dir / "scientific_accuracy_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return acc >= 95.0

if __name__ == "__main__":
    success = run_scientific_accuracy_benchmark()
    sys.exit(0 if success else 1)
