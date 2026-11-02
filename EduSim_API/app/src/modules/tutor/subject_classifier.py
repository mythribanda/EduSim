

import re


def _count_keyword_matches(keywords: list[str], text: str) -> int:
    count = 0
    for k in keywords:
        pattern = r"\b" + re.escape(k) + r"\b"
        if re.search(pattern, text):
            count += 1
    return count


def detect_subject(query: str) -> str:
    """
    Lightweight keyword-based subject routing
    for educational textbook retrieval.
    """

    q = query.lower()

    # =====================================================
    # PHYSICS KEYWORDS
    # =====================================================
    physics_keywords = [

        # Mechanics
        "force",
        "motion",
        "gravity",
        "velocity",
        "acceleration",
        "speed",
        "distance",
        "displacement",
        "momentum",
        "friction",
        "inertia",
        "newton",
        "work",
        "energy",
        "power",

        # Waves & Sound
        "wave",
        "sound",
        "frequency",
        "amplitude",
        "wavelength",
        "echo",
        "ultrasound",

        # Light & Optics
        "light",
        "reflection",
        "refraction",
        "mirror",
        "lens",
        "optics",
        "prism",

        # Electricity & Magnetism
        "electricity",
        "electric current",
        "voltage",
        "resistance",
        "circuit",
        "battery",
        "magnet",
        "magnetic field",

        # Heat
        "temperature",
        "heat",
        "thermal",
        "conduction",
        "convection",
        "radiation",

        # Modern Physics
        "atom",
        "nuclear",
        "radioactivity",
        "electron",
        "proton",
        "neutron"
    ]

    # =====================================================
    # CHEMISTRY KEYWORDS
    # =====================================================
    chemistry_keywords = [

        # Basic Chemistry
        "molecule",
        "compound",
        "element",
        "mixture",
        "solution",

        # Atomic Structure
        "atom",
        "electron",
        "proton",
        "neutron",
        "nucleus",

        # Reactions
        "reaction",
        "chemical reaction",
        "oxidation",
        "reduction",
        "combustion",

        # Acids & Bases
        "acid",
        "base",
        "ph",
        "neutralization",

        # Bonding
        "bond",
        "ionic bond",
        "covalent bond",

        # Periodic Table
        "periodic table",
        "metal",
        "nonmetal",
        "metalloid",

        # States of Matter
        "solid",
        "liquid",
        "gas",
        "evaporation",
        "condensation",

        # Organic Chemistry
        "hydrocarbon",
        "carbon",
        "organic compound",

        # Quantities
        "mole",
        "molarity",
        "molality"
    ]

    # =====================================================
    # MATHEMATICS KEYWORDS
    # =====================================================
    maths_keywords = [

        # Algebra
        "algebra",
        "equation",
        "linear equation",
        "quadratic equation",
        "polynomial",
        "factorization",

        # Geometry
        "geometry",
        "triangle",
        "circle",
        "rectangle",
        "square",
        "perimeter",
        "area",
        "volume",
        "surface area",

        # Trigonometry
        "trigonometry",
        "sin",
        "cos",
        "tan",
        "angle",

        # Calculus
        "calculus",
        "derivative",
        "integration",
        "integral",
        "differentiation",
        "limit",

        # Coordinate Geometry
        "coordinate geometry",
        "graph",
        "slope",
        "distance formula",

        # Statistics & Probability
        "statistics",
        "probability",
        "mean",
        "median",
        "mode",

        # Linear Algebra
        "matrix",
        "vector",

        # Arithmetic
        "percentage",
        "ratio",
        "proportion",
        "profit",
        "loss",
        "simple interest",
        "compound interest",

        # Number System
        "number system",
        "prime number",
        "rational number",
        "irrational number"
    ]

    # =====================================================
    # BIOLOGY KEYWORDS
    # =====================================================
    biology_keywords = [

        # Cell Biology
        "cell",
        "cell membrane",
        "nucleus",
        "mitochondria",

        # Genetics
        "dna",
        "gene",
        "genetics",
        "chromosome",
        "heredity",

        # Human Body
        "human body",
        "heart",
        "brain",
        "lungs",
        "kidney",
        "digestive system",
        "respiratory system",
        "circulatory system",

        # Plants
        "plant",
        "photosynthesis",
        "transpiration",

        # Animals
        "animal",
        "vertebrate",
        "invertebrate",

        # Ecology
        "ecosystem",
        "food chain",
        "environment",
        "biodiversity",

        # Life Processes
        "respiration",
        "nutrition",
        "reproduction",

        # Microbiology
        "bacteria",
        "virus",
        "fungi",

        # Evolution
        "evolution",
        "adaptation",

        # Health
        "disease",
        "immunity",
        "vaccine"
    ]

    # =====================================================
    # SCORING
    # =====================================================
    scores = {
        "physics": _count_keyword_matches(physics_keywords, q),
        "chemistry": _count_keyword_matches(chemistry_keywords, q),
        "maths": _count_keyword_matches(maths_keywords, q),
        "biology": _count_keyword_matches(biology_keywords, q),
    }

    # =====================================================
    # BEST MATCH
    # =====================================================
    best_match = max(scores, key=scores.get)

    # =====================================================
    # DEFAULT FALLBACK
    # =====================================================
    if scores[best_match] == 0:
        return "physics"

    return best_match