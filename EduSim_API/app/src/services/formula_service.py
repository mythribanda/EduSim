import re
import json
import logging
import sympy
import difflib
import os
import hashlib
from typing import Dict, Any
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication
from app.src.modules.legacy_rag.generator import generate_llm_text_async
from app.src.models.formula_models import FormulaLabResponse, FormulaVariable, FormulaControl, FormulaExample

logger = logging.getLogger("EduSim.formula_service")

FORMULA_GROUP_CACHE = {}

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "formula_extraction_cache.json")

def load_persistent_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_persistent_cache(cache: Dict[str, Any]):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("[Cache] Error saving persistent cache: %s", e)

def get_cache_key(text: str, query: str = None) -> str:
    key_str = f"q:{query or ''}|t:{text or ''}"
    return hashlib.md5(key_str.encode("utf-8")).hexdigest()



FORMULA_REGISTRY = {
    "F=ma": {
        "title": "Newton's Second Law",
        "description": "The rate of change of momentum of a body over time is directly proportional to the force applied, and occurs in the same direction as the applied force.",
        "variables": [
            {"symbol": "F", "label": "Force", "unit": "N", "meaning": "Force applied"},
            {"symbol": "m", "label": "Mass", "unit": "kg", "meaning": "Mass of the object"},
            {"symbol": "a", "label": "Acceleration", "unit": "m/s²", "meaning": "Acceleration"}
        ],
        "resultSymbol": "F"
    },
    "V=IR": {
        "title": "Ohm's Law",
        "description": "The current through a conductor between two points is directly proportional to the voltage across the two points.",
        "variables": [
            {"symbol": "V", "label": "Voltage", "unit": "V", "meaning": "Voltage"},
            {"symbol": "I", "label": "Current", "unit": "A", "meaning": "Current"},
            {"symbol": "R", "label": "Resistance", "unit": "Ω", "meaning": "Resistance"}
        ],
        "resultSymbol": "V"
    },
    "N_1(\\THETA_1)=N_2(\\THETA_2)": {
        "title": "Snell's Law",
        "description": "A formula used to describe the relationship between the angles of incidence and refraction, when referring to light or other waves passing through a boundary between two different isotropic media.",
        "variables": [
            {"symbol": "n_1", "label": "Refractive Index 1", "unit": "", "meaning": "Refractive index of first medium"},
            {"symbol": "\\theta_1", "label": "Angle of Incidence", "unit": "°", "meaning": "Angle of incidence"},
            {"symbol": "n_2", "label": "Refractive Index 2", "unit": "", "meaning": "Refractive index of second medium"},
            {"symbol": "\\theta_2", "label": "Angle of Refraction", "unit": "°", "meaning": "Angle of refraction"}
        ],
        "resultSymbol": "n_2"
    },
}

def strip_latex(s: str) -> str:
    # Replace relation operators with '='
    s = re.sub(r"\\approx|\\propto|approx|propto|≈|∝|\\le|\\ge|\\leq|\\geq|≤|≥", "=", s)
    # Remove function dependency notation on the LHS (e.g., theta(t) = ... -> theta = ...)
    s = re.sub(r"([a-zA-Z_]+)\([a-zA-Z_]\)\s*=", r"\1 =", s)

    # Handle fraction parsing
    s = re.sub(r"\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}", r"(\1)/(\2)", s)
    
    # Translate Greek letters and math constants
    s = re.sub(r"\\sin", "sin", s)
    s = re.sub(r"\\cos", "cos", s)
    s = re.sub(r"\\tan", "tan", s)
    s = re.sub(r"\\theta", "theta", s)
    s = re.sub(r"\\omega", "omega", s)
    s = re.sub(r"\\pi", "pi", s)
    s = re.sub(r"\\phi", "phi", s)
    s = re.sub(r"\\mu", "mu", s)
    s = re.sub(r"\\lambda", "lambd", s) # use lambd to avoid Python keyword collision
    s = re.sub(r"\\rho", "rho", s)
    s = re.sub(r"\\epsilon", "epsilon", s)
    s = re.sub(r"\\eta", "eta", s)
    s = re.sub(r"\\tau", "tau", s)
    s = re.sub(r"\\nu", "nu", s)
    s = re.sub(r"\\sigma", "sigma", s)
    s = re.sub(r"\\alpha", "alpha", s)
    s = re.sub(r"\\beta", "beta", s)
    s = re.sub(r"\\gamma", "gamma", s)
    s = re.sub(r"\\Delta", "Delta", s)
    
    # Handle square root replacement
    s = re.sub(r"\\sqrt\s*\{([^}]+)\}", r"sqrt(\1)", s)
    
    # Clean subscripts in curly braces first: remove curly braces and commas/spaces
    s = re.sub(r"_\{([^}]+)\}", lambda m: "_" + m.group(1).replace(",", "").replace(" ", ""), s)
    
    # Handle superscripts
    s = s.replace("^", "**")
    
    s = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", s)
    
    # Translate multiplication dot/cross to *
    s = re.sub(r"\\cdot|\\times", "*", s)
    
    # Remove remaining formatting/helpers but KEEP \sqrt if it wasn't matched above (as fallback)
    commands = [
        r"\\left", r"r\\ight"
    ]
    for cmd in commands:
        s = re.sub(cmd, "", s)
        
    s = s.replace("{", "").replace("}", "")
    
    # Protect subscripts: replace all _subscripts with placeholders using non-letter symbol '#'
    subscripts = re.findall(r"_[a-zA-Z0-9]+", s)
    sub_placeholders = {}
    for idx, sub in enumerate(subscripts):
        ph = f"#{idx}#"
        sub_placeholders[ph] = sub
        s = s.replace(sub, ph)
        
    # Implicit multiplication for adjacent single letters
    # Hide known words first (including new Greek words)
    words = [
        'sin', 'cos', 'tan', 'theta', 'omega', 'pi', 'phi', 'mu', 'lambd', 'rho', 
        'epsilon', 'eta', 'tau', 'nu', 'sigma', 'alpha', 'beta', 'gamma', 'Delta', 'sqrt', 'speed', 'distance', 'time'
    ]
    # Use #word_{idx}# as placeholder for words to avoid any letter issues
    word_placeholders = {}
    for idx, w in enumerate(words):
        ph = f"#W{idx}#"
        word_placeholders[ph] = w
        s = s.replace(w, ph)
        
    # Insert * between adjacent letters
    while re.search(r"([a-zA-Z])([a-zA-Z])", s):
        s = re.sub(r"([a-zA-Z])([a-zA-Z])", r"\1*\2", s)
        
    # Restore words
    for ph, w in word_placeholders.items():
        s = s.replace(ph, w)
        
    # Restore subscripts
    for ph, sub in sub_placeholders.items():
        s = s.replace(ph, sub)
        
    return s


def is_value_substituted(formula: str) -> bool:
    """
    Checks if a formula has specific substituted values, units, or scientific notation
    which indicates it is not a standard general physics/math formula.
    """
    formula_lower = formula.lower()
    
    # 1. Check for decimal numbers that are not standard (we allow 0.5, .5, 0.25, .25)
    decimals = re.findall(r"\d+\.\d+", formula_lower)
    for dec in decimals:
        if dec not in ["0.5", ".5", "0.25", ".25"]:
            return True
            
    # 2. Check for scientific notation or large exponents on 10, e.g., 10^ or 10**
    if "10^" in formula_lower or "10**" in formula_lower or "10\\times" in formula_lower:
        return True
        
    # 3. Check for explicit unit words or text blocks containing units
    unit_words = [
        "year", "years", "month", "months", "day", "days", "hour", "hours", "minute", "minutes", "second", "seconds",
        "meter", "meters", "sec", "sec^", "kg", "kilogram", "kilograms", "gram", "grams", "volt", "volts", "ampere", "amperes",
        "ohm", "ohms", "joule", "joules", "watt", "watts", "newton", "newtons", "kelvin", "celsius", "fahrenheit",
        "au", "astronomical", "unit", "units", "mars", "earth", "sun", "moon", "kg/m", "m/s", "circ", "degree", "degrees"
    ]
    
    text_blocks = re.findall(r"\\text\s*\{([^}]+)\}", formula)
    for block in text_blocks:
        block_clean = block.strip().lower()
        if any(w in block_clean for w in unit_words) or block_clean.isdigit():
            return True
            
    # Check raw formula for standalone unit words
    words = re.findall(r"\b[a-zA-Z]+\b", formula_lower)
    for w in words:
        if w in unit_words:
            return True
            
    # 4. Strip out standard/allowed formula digits/numbers to see if any non-standard numbers remain
    # Remove exponents: e.g. ^2, ^3, ^4, ^-1, ^{2}, ^{-2}, etc.
    s = re.sub(r"\^\{?[-+]?\d+\}?", "", formula)
    s = re.sub(r"\*\*\{?[-+]?\d+\}?", "", s)
    
    # Remove subscripts: e.g. _1, _2, _0, _{1}, _{2}, _{0}, _{t}
    s = re.sub(r"_\{?\d+\}?", "", s)
    
    # Remove standard fractions: e.g. 1/2, 1/3, 1/4, 2/3, 4/3, 3/4, 1/8
    s = re.sub(r"\\frac\s*\{\s*1\s*\}\s*\{\s*[2348]\s*\}", "", s)
    s = re.sub(r"\\frac\s*\{\s*[234]\s*\}\s*\{\s*[34]\s*\}", "", s)
    s = re.sub(r"\b[1234]\s*/\s*[2348]\b", "", s)
    
    # Remove simple coefficient/scaling numbers: 0, 1, 2, 3, 4, 8
    s = re.sub(r"\b[012348]\b", "", s)
    
    # Check if there are any remaining digits (e.g. 90, 180, 360, 50, etc.)
    remaining_digits = re.findall(r"\d+", s)
    if remaining_digits:
        return True
            
    return False


class FormulaService:
    @staticmethod
    def _canonicalize_formula(formula_str: str):
        clean = strip_latex(formula_str)
        parts = clean.split("=")
        if len(parts) < 2:
            return None, 0, {}

        lhs = parts[0]
        rhs = parts[-1]

        try:
            transformations = (standard_transformations + (implicit_multiplication,))
            # Construct symbols dynamically including subscripts
            all_symbols = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", clean))
            # Remove known function names and constants
            for word in ['sin', 'cos', 'tan', 'sqrt', 'pi']:
                all_symbols.discard(word)
                
            local_dict = {sym: sympy.Symbol(sym) for sym in all_symbols}
            # Add pi as sympy's pi
            local_dict.update({
                'pi': sympy.pi
            })
            
            lhs_expr = parse_expr(lhs, transformations=transformations, local_dict=local_dict)
            rhs_expr = parse_expr(rhs, transformations=transformations, local_dict=local_dict)
            
            expr = sympy.simplify(lhs_expr - rhs_expr)
            
            symbols = sorted(list(expr.free_symbols), key=lambda s: s.name)
            symbol_count = len(symbols)
            if not symbols:
                return None, symbol_count, {}
                
            derived_expressions = {}
            for target in symbols:
                sols = sympy.solve(expr, target)
                if sols:
                    derived_expressions[target.name] = str(sols[0]).replace(" ", "").replace("**", "^")

            target = symbols[0]
            solutions = sympy.solve(expr, target)
            if not solutions:
                return str(expr).replace(" ", ""), symbol_count, {}
                
            canon_expr = sympy.Eq(target, solutions[0])
            return str(canon_expr).replace(" ", ""), symbol_count, derived_expressions
        except Exception:
            # Fallback symbol count using simple regex (unique letters/words)
            words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula_str))
            return None, len(words), {}

    @staticmethod
    async def extract_formulas(text: str, query: str = None) -> Dict[str, Any]:
        if not text and not query:
            return {"formulas": [], "calculation_steps": []}
            
        cache_key = get_cache_key(text, query)
        cache = load_persistent_cache()
        if cache_key in cache:
            logger.info("[FormulaService] Serving extract_formulas from persistent cache for query: %s", query)
            cached_res = cache[cache_key]
            for f in cached_res.get("formulas", []):
                primary = f.get("primary_formula") or f.get("formula")
                canon = f.get("canonical_form")
                derived = f.get("derived_forms", [])
                if primary:
                    FORMULA_GROUP_CACHE[primary] = {
                        "canonical_form": canon,
                        "primary_formula": primary,
                        "derived_forms": derived
                    }
            return cached_res
            
        candidates = set()
        titles_map = {} # maps candidate -> title
        
        # Let's construct a prompt to LLM to extract or generate clean formulas
        prompt = "You are a scientific formula extractor.\n"
        if query:
            prompt += "Given the search topic and some retrieved textbook text chunks, extract or provide all unique, relevant standard scientific and mathematical formulas/equations.\n"
            prompt += "If the textbook text does not contain clean mathematical formulas for the topic, use your general knowledge to provide the standard, canonical formulas for the topic.\n\n"
            prompt += f"Topic: {query}\n\n"
        else:
            prompt += "Extract all unique scientific and mathematical formulas/equations from the following text.\n\n"
            
        prompt += f"Textbook text:\n{text}\n\n"
        prompt += """Return a JSON object containing a list of extracted formulas under the key "formulas".
Each formula object in the list must have:
- formula: the clean formula using standard single-letter scientific variable notation (e.g. 'f = \\mu * N' or 'W = F * s' or 'E = m * c^2'). Use LaTeX or standard ASCII representation.
- title: a short name/title for the formula (e.g. 'Frictional Force', 'Work Done by a Constant Force', 'Newton's Second Law')

Do not include concrete numbers substituted (unless universal constants like 1/2 or g). Do not include sentences or text descriptions as the formula.
Return raw JSON only, no markdown formatting."""

        try:
            llm_text = await generate_llm_text_async(
                prompt,
                temperature=0.1,
                max_output_tokens=1000,
                system_prompt="You are a helpful physics and math assistant that outputs JSON only.",
                response_format={"type": "json_object"}
            )
            data = json.loads(llm_text)
            for item in data.get("formulas", []):
                formula_str = item.get("formula", "").strip()
                title = item.get("title", "").strip()
                if formula_str and title:
                    candidates.add(formula_str)
                    titles_map[formula_str] = title
        except Exception as e:
            logger.error("[FormulaService] Error during LLM extraction: %s", e)
            # Fallback to regex candidate extraction if LLM fails
            display_regex = r"\$\$(.*?)\$\$"
            inline_regex = r"\$([^$\n]+?)\$"
            for match in re.finditer(display_regex, text, re.DOTALL):
                val = match.group(1).strip()
                for line in val.split("\n"):
                    line_cleaned = line.strip()
                    if line_cleaned:
                        candidates.add(line_cleaned)
            for match in re.finditer(inline_regex, text):
                val = match.group(1).strip()
                candidates.add(val)
            if not candidates:
                for line in text.split("\n"):
                    cleaned = line.strip()
                    if cleaned and (re.search(r"[=∝→⇒⇌↔≈~]", cleaned) or re.search(r"[A-Z][a-z]?\d*\s*\+", cleaned)):
                        candidates.add(cleaned)
                    
        grouped = {} # maps canonical_form -> { "primary_formula": str, "derived_forms": set }
        
        for formula in candidates:
            # STRICT FILTER
            # Support both raw symbols and LaTeX equivalents like \propto, \approx, \to, \rightarrow, \le, \ge, =
            if not re.search(r"[=≈≤≥∝→]|propto|approx|\\to|\\rightarrow|\\le|\\ge", formula):
                continue
                
            canonical = formula.replace(" ", "").lower()
            if "propto" in canonical or "deltap" in canonical or "andinsiunitstheconstant" in canonical:
                if len(canonical) > 40 and not any(x in canonical for x in ["frac", "sqrt", "sin", "cos"]):
                    continue
                
            if canonical.isalpha():
                continue
                
            canon_sym, symbol_count, derived_expressions = FormulaService._canonicalize_formula(formula)
            group_key = canon_sym if canon_sym else canonical
            
            # Determine equation type and confidence
            confidence = 1.0
            eq_type = "Formula"
            
            clean_for_check = strip_latex(formula)
            parts = clean_for_check.split("=")
            is_final_answer = False
            if len(parts) == 2:
                def is_single_var(s):
                    return bool(re.match(r"^\s*[a-zA-Z_]\s*$", s))
                def is_number(s):
                    return bool(re.match(r"^\s*[\d\.\-]+\s*[a-zA-Z_]*\s*$", s))
                    
                if (is_single_var(parts[0]) and is_number(parts[1])) or (is_single_var(parts[1]) and is_number(parts[0])):
                    is_final_answer = True
            
            if symbol_count == 0:
                eq_type = "Worked Example"
                confidence = 1.0
            elif is_final_answer:
                eq_type = "Final Answer"
                confidence = 0.9
            elif symbol_count == 1:
                eq_type = "Substitution Step"
                confidence = 0.8
            else:
                eq_type = "Formula"
                confidence = 1.0
                
            # Semantic Deduplication for specific physics formulas
            if eq_type == "Formula":
                if "speed" in canonical and "distance" in canonical and "time" in canonical:
                    group_key = "Eq(s,t*v)"
                elif "v" in canonical and "s" in canonical and "t" in canonical:
                    group_key = "Eq(s,t*v)"
                elif "q" in canonical and "i" in canonical and "t" in canonical:
                    group_key = "Eq(I*t,Q)"
                elif canon_sym:
                    group_key = canon_sym

            # String similarity fallback grouping (if canon_sym failed)
            if not canon_sym:
                for existing_key in grouped.keys():
                    if difflib.SequenceMatcher(None, group_key, existing_key).ratio() > 0.8:
                        group_key = existing_key
                        break
                        
            if group_key not in grouped:
                grouped[group_key] = {
                    "canonical_form": group_key,
                    "primary_formula": formula,
                    "derived_forms": set(),
                    "equation_type": eq_type,
                    "confidence": confidence
                }
            else:
                if formula != grouped[group_key]["primary_formula"]:
                    grouped[group_key]["derived_forms"].add(formula)
                    
        formulas = []
        calculation_steps = []
        
        # Logging counters
        stats = {
            "total_candidates": len(candidates),
            "valid_formulas": 0,
            "substitution_steps": 0,
            "final_answers": 0,
            "worked_examples": 0,
            "duplicates_merged": 0
        }
        
        for idx, (canon, data) in enumerate(grouped.items()):
            primary = data["primary_formula"]
            derived = list(data["derived_forms"])
            stats["duplicates_merged"] += len(derived)
            
            eq_type = data.get("equation_type", "Formula")
            conf = data.get("confidence", 1.0)
            
            # Recalculate derived expressions for the primary formula to ensure it has them
            _, _, derived_expressions = FormulaService._canonicalize_formula(primary)
            
            title = titles_map.get(primary, "Formula")
            
            item = {
                "id": f"formula-{idx}",
                "formula": primary,
                "title": title,
                "raw": primary,
                "canonical_form": canon,
                "primary_formula": primary,
                "derived_forms": derived,
                "equation_type": eq_type,
                "confidence": conf,
                "derived_expressions": derived_expressions
            }
            
            if eq_type == "Formula" and not is_value_substituted(primary):
                stats["valid_formulas"] += 1
                # Cache the mappings so get_formula_details knows about derived forms
                FORMULA_GROUP_CACHE[primary] = {
                    "canonical_form": canon,
                    "primary_formula": primary,
                    "derived_forms": derived
                }
                formulas.append(item)
            else:
                # Completely discard/remove substituted formulas to save tokens and clean up views
                pass
                    
        logger.info("[FormulaService] Extraction complete. Stats: %s", json.dumps(stats))
            
        result = {"formulas": formulas, "calculation_steps": calculation_steps}
        try:
            cache = load_persistent_cache()
            cache[cache_key] = result
            save_persistent_cache(cache)
        except Exception as e:
            logger.error("[Cache] Failed to save result to cache: %s", e)
            
        return result

    @staticmethod
    async def get_formula_details(formula: str) -> FormulaLabResponse:
        clean_formula = strip_latex(formula)
        canonical = clean_formula.replace(" ", "").replace("**", "^").replace("·", "").upper()
        
        # Fetch cached derived forms if available
        cache_data = FORMULA_GROUP_CACHE.get(formula, {})
        canon_res = FormulaService._canonicalize_formula(formula)
        canon_form_str = canon_res[0] if isinstance(canon_res, tuple) and canon_res[0] is not None else formula
        canon_form = cache_data.get("canonical_form", canon_form_str)
        primary_form = cache_data.get("primary_formula", formula)
        derived_forms = cache_data.get("derived_forms", [])
        
        # Check cache
        cache_key_details = f"detail:{formula}"
        cache = load_persistent_cache()
        if cache_key_details in cache:
            logger.info("[FormulaService] Serving get_formula_details from persistent cache for formula: %s", formula)
            cached_res = cache[cache_key_details]
            controls = [FormulaControl(**c) for c in cached_res.get("controls", [])]
            anatomy = [FormulaVariable(**a) for a in cached_res.get("anatomy", [])]
            examples = [FormulaExample(**e) for e in cached_res.get("examples", [])]
            return FormulaLabResponse(
                id=cached_res.get("id"),
                title=cached_res.get("title"),
                formula=primary_form,
                canonical_form=canon_form,
                primary_formula=primary_form,
                derived_forms=derived_forms,
                description=cached_res.get("description"),
                purpose=cached_res.get("purpose", ""),
                applications=cached_res.get("applications", []),
                common_mistakes=cached_res.get("common_mistakes", []),
                variables=controls,
                controls=controls,
                anatomy=anatomy,
                examples=examples,
                resultSymbol=cached_res.get("resultSymbol", "y"),
                derived_expressions=cached_res.get("derived_expressions", {})
            )
        
        # Check registry
        for key, def_ in FORMULA_REGISTRY.items():
            key_norm = key.replace(" ", "").upper()
            if key_norm in canonical or canonical in key_norm:
                controls = []
                anatomy = []
                for v in def_["variables"]:
                    controls.append(FormulaControl(
                        symbol=v["symbol"], 
                        label=v["label"], 
                        unit=v["unit"]
                    ))
                    anatomy.append(FormulaVariable(
                        symbol=v["symbol"],
                        meaning=v["meaning"],
                        unit=v["unit"]
                    ))
                
                _, _, derived_expressions = FormulaService._canonicalize_formula(formula)
                res_obj = FormulaLabResponse(
                    id=key,
                    title=def_["title"],
                    formula=primary_form,
                    canonical_form=canon_form,
                    primary_formula=primary_form,
                    derived_forms=derived_forms,
                    description=def_["description"],
                    variables=controls,
                    controls=controls,
                    anatomy=anatomy,
                    examples=[FormulaExample(title="Example", content="Standard calculation.")],
                    resultSymbol=def_["resultSymbol"],
                    derived_expressions=derived_expressions
                )
                try:
                    cache = load_persistent_cache()
                    cache[cache_key_details] = {
                        "id": res_obj.id,
                        "title": res_obj.title,
                        "description": res_obj.description,
                        "purpose": res_obj.purpose or "",
                        "applications": res_obj.applications or [],
                        "common_mistakes": res_obj.common_mistakes or [],
                        "controls": [dict(c) for c in res_obj.controls],
                        "anatomy": [dict(a) for a in res_obj.anatomy],
                        "examples": [dict(e) for e in res_obj.examples],
                        "resultSymbol": res_obj.resultSymbol,
                        "derived_expressions": res_obj.derived_expressions
                    }
                    save_persistent_cache(cache)
                except Exception as e:
                    logger.error("[Cache] Failed to save registry details to cache: %s", e)
                return res_obj
                
        # LLM Fallback for unknown formula
        prompt = '''Analyze this scientific or mathematical formula: {clean_formula}
Return a JSON object with:
- title: string (e.g. "Newton's Second Law")
- description: string
- variables: array of objects with symbol, label, unit (if applicable), meaning, min (number), max (number), step (number), and defaultValue (number). Provide reasonable bounds for typical educational usage.
- resultSymbol: string (the symbol being calculated)
Do NOT include markdown block markers, output raw JSON.'''
        
        res_obj = None
        try:
            llm_text = await generate_llm_text_async(
                prompt,
                temperature=0.2,
                max_output_tokens=1000,
                system_prompt="You are a helpful physics and math assistant that outputs JSON only.",
                response_format={"type": "json_object"}
            )
            if llm_text:
                # clean up markdown backticks if any (json, python, or plain)
                llm_text = llm_text.strip()
                llm_text = re.sub(r"^```(?:json|text|markdown)?|```$", "", llm_text, flags=re.MULTILINE).strip()
                
                try:
                    data = json.loads(llm_text)
                except json.JSONDecodeError:
                    # Repair single backslashes in LaTeX commands that violate JSON escaping rules only if direct parsing fails
                    repaired_text = re.sub(r'\\(?!n|"|u[0-9a-fA-F]{4})', r'\\\\', llm_text)
                    data = json.loads(repaired_text)
                    
                controls = []
                anatomy = []
                for v in data.get("variables", []):
                    controls.append(FormulaControl(
                        symbol=v.get("symbol", ""),
                        label=v.get("label", v.get("symbol", "")),
                        unit=v.get("unit", ""),
                        min=v.get("min", 1.0),
                        max=v.get("max", 100.0),
                        step=v.get("step", 1.0),
                        defaultValue=v.get("defaultValue", 10.0)
                    ))
                    anatomy.append(FormulaVariable(
                        symbol=v.get("symbol", ""),
                        meaning=v.get("meaning", v.get("label", "")),
                        unit=v.get("unit", "")
                    ))
                _, _, derived_expressions = FormulaService._canonicalize_formula(formula)
                res_obj = FormulaLabResponse(
                    id="dynamic-formula",
                    title=data.get("title", "Unknown Formula"),
                    formula=primary_form,
                    canonical_form=canon_form,
                    primary_formula=primary_form,
                    derived_forms=derived_forms,
                    description=data.get("description", "A mathematical expression."),
                    purpose=data.get("purpose", ""),
                    applications=data.get("applications", []),
                    common_mistakes=data.get("common_mistakes", []),
                    variables=controls,
                    controls=controls,
                    anatomy=anatomy,
                    examples=[FormulaExample(title="Example", content="Dynamically generated.")],
                    resultSymbol=data.get("resultSymbol", "y"),
                    derived_expressions=derived_expressions
                )
        except Exception as e:
            logger.error("LLM formula extraction failed: %s", e)
            
        if not res_obj:
            # Absolute fallback
            _, _, derived_expressions = FormulaService._canonicalize_formula(formula)
            res_obj = FormulaLabResponse(
                id="fallback",
                title="Formula",
                formula=primary_form,
                canonical_form=canon_form,
                primary_formula=primary_form,
                derived_forms=derived_forms,
                description="A scientific or mathematical equation.",
                variables=[],
                controls=[],
                anatomy=[],
                examples=[],
                resultSymbol="y",
                derived_expressions=derived_expressions
            )
            
        try:
            cache = load_persistent_cache()
            cache[cache_key_details] = {
                "id": res_obj.id,
                "title": res_obj.title,
                "description": res_obj.description,
                "purpose": res_obj.purpose or "",
                "applications": res_obj.applications or [],
                "common_mistakes": res_obj.common_mistakes or [],
                "controls": [dict(c) for c in res_obj.controls],
                "anatomy": [dict(a) for a in res_obj.anatomy],
                "examples": [dict(e) for e in res_obj.examples],
                "resultSymbol": res_obj.resultSymbol,
                "derived_expressions": res_obj.derived_expressions
            }
            save_persistent_cache(cache)
        except Exception as e:
            logger.error("[Cache] Failed to save details result to cache: %s", e)
            
        return res_obj
