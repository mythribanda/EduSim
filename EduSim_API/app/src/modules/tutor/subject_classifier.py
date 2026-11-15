

import logging
import re
from pathlib import Path

logger = logging.getLogger("EduSim.tutor.subject_classifier")

_NLP_MODEL = None
_MODEL_PATH = Path(__file__).resolve().parent / "subject_classifier.joblib"

def _get_nlp_model():
    global _NLP_MODEL
    if _NLP_MODEL is None and _MODEL_PATH.exists():
        try:
            import joblib
            _NLP_MODEL = joblib.load(_MODEL_PATH)
        except Exception as e:
            logger.warning(f"Could not load subject_classifier.joblib: {e}")
    return _NLP_MODEL


def _count_keyword_matches(keywords: list[str], text: str) -> int:
    count = 0
    for k in keywords:
        if any(ord(c) > 127 for c in k):
            if k in text:
                count += 1
        else:
            pattern = r"\b" + re.escape(k) + r"\b"
            if re.search(pattern, text):
                count += 1
    return count


def detect_subject(query: str) -> str:
    """
    Offline NLP Subject Classifier with hybrid word+character TF-IDF Logistic Regression
    and graceful fallback to keyword rules.
    """
    # 1. First attempt calibrated offline NLP model
    model = _get_nlp_model()
    if model is not None:
        try:
            probs = model.predict_proba([query])[0]
            classes = model.classes_
            top_idx = probs.argmax()
            top_prob = probs[top_idx]
            top_class = classes[top_idx]
            if top_prob >= 0.38:
                return "maths" if top_class == "mathematics" else top_class
        except Exception as e:
            logger.debug(f"NLP model prediction failed: {e}")

    # 2. Rule-based / Keyword fallback
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
                # Multilingual (Telugu & Hindi)
        "గురుత్వాకర్షణ", "చలనం", "గతి", "వేగం", "త్వరణం", "బలం", "శక్తి", "పని", "కాంతి", "ధ్వని", "విద్యుత్", "విద్యుత్తు", "అయస్కాంతం", "పీడనం", "ఘర్షణ", "ద్రవ్యరాశి", "సాంద్రత", "ఉష్ణోగ్రత", "వేడి", "తరంగం",
        "गुरुत्वाकर्षण", "गति", "वेग", "चाल", "त्वरण", "बल", "ऊर्जा", "कार्य", "प्रकाश", "ध्वनि", "विद्युत", "बिजली", "चुंबक", "दाब", "घर्षण", "द्रव्यमान", "घनत्व", "तापमान", "ऊष्मा", "तरंग",
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
        "bonding",
        "chemical bond",
        "chemical bonding",
        "ionic bond",
        "covalent bond",
        "covalent",
        "ionic",
        "valence",
        "valency",
        "catalyst",
        "equilibrium",

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
        "molality",

        # Multilingual (Telugu & Hindi)
        "రసాయన", "పరమాణువు", "అణువు", "మూలకం", "సమ్మేళనం", "మిశ్రమం", "ద్రావణం", "ఆమ్లం", "క్షారం", "లోహం", "అలోహం", "ఆక్సీకరణం", "బంధం", "బంధాలు", "సమయోజనీయ", "అయానిక", "సంయోజనీయత", "రసాయన చర్య", "ద్రావణాలు", "ఉత్ప్రేరకం",
        "रसायन", "परमाणु", "अणु", "तत्व", "यौगिक", "मिश्रण", "विलयन", "अम्ल", "क्षार", "लवण", "धातु", "अधातु", "ऑक्सीकरण", "आबंधन", "आबंध", "सहसंयोजक", "सहसंयोजकता", "आयनिक", "संयोजकता", "रासायनिक अभिक्रिया", "उत्प्रेरक", "संतुलन",
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
        "quadratic",
        "quadratic formula",
        "roots",
        "roots of",
        "zeros of",
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
                # Multilingual (Telugu & Hindi)
        "గణితం", "త్రికోణమితి", "బీజగణితం", "జ్యామితి", "సంఖ్య", "సమీకరణం", "వైశాల్యం", "పరిధి", "వ్యాసార్థం", "త్రికోణం", "చతుర్భుజం", "సంభావ్యత", "భిన్నం", "వర్గ", "ద్విఘాత", "మూలాలు", "శూన్యాలు", "గుణకాలు", "శ్రేఢులు", "అంకశ్రేఢి",
        "गणित", "त्रिकोणमिति", "बीजगणित", "ज्यामिति", "संख्या", "समीकरण", "क्षेत्रफल", "परिधि", "त्रिज्या", "त्रिभुज", "चतुर्भुज", "प्रायिकता", "भिन्न", "द्विघात", "मूल", "शून्यक", "गुणांक", "श्रेणी", "समांतर श्रेणी",
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
                # Multilingual (Telugu & Hindi)
        "కణం", "కణజాలం", "కిరణజన్య", "శ్వాసక్రియ", "జీర్ణక్రియ", "రక్త ప్రసరణ", "ప్రత్యుత్పత్తి", "వృక్ష", "జంతు", "డీఎన్‌ఏ", "జన్యువు", "హరితరేణువు", "హరితరేణువులు", "క్లోరోప్లాస్ట్", "మైటోకాండ్రియా", "జీవక్రియ", "జీర్ణవ్యవస్థ", "ఉద్గార",
        "कोशिका", "ऊतक", "प्रकाश संश्लेषण", "श्वसन", "पाचन", "रक्त", "जनन", "पादप", "जंतु", "डीएनए", "जीन", "हरितलवक", "क्लोरोप्लास्ट", "माइटोकॉन्ड्रिया", "जैव प्रक्रम", "पाचन तंत्र", "उत्सर्जन", "कायिक",
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