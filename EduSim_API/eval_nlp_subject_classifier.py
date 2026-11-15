"""
Independent Balanced Subject Classification Benchmark (100 Questions)
Evaluates across:
1. English (25 questions)
2. Telugu (25 questions)
3. Hindi (25 questions)
4. Mixed-language / Transliterated / Ambiguous / Technical cross-cutting (25 questions)

Computes:
- Overall Accuracy
- Per-Language Accuracy
- Per-Subject Precision, Recall, F1-Score
- Confusion Matrix
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from sklearn.metrics import classification_report, confusion_matrix
import joblib

MODEL_PATH = api_dir / "app" / "src" / "modules" / "tutor" / "subject_classifier.joblib"

def get_100_balanced_questions():
    """
    100 carefully balanced questions across Physics, Chemistry, Biology, and Mathematics.
    Includes mixed-language, technical, ambiguous, and multi-subject queries.
    """
    q_list = []

    # ----------------------------------------------------
    # 1. ENGLISH (25 Questions: 6 Physics, 6 Chem, 6 Bio, 7 Math)
    # ----------------------------------------------------
    en = [
        # Physics
        ("State Newton's second law of motion and explain F=ma.", "physics"),
        ("What is universal gravitation constant G and orbital velocity?", "physics"),
        ("Explain Snell's law of refraction and critical angle in prisms.", "physics"),
        ("What is Ohm's law and relation between voltage, current and resistance?", "physics"),
        ("Explain simple harmonic motion and time period of a simple pendulum.", "physics"),
        ("Describe total internal reflection and optical fiber communication.", "physics"),
        # Chemistry
        ("Differentiate between exothermic and endothermic reactions with examples.", "chemistry"),
        ("What are hydrocarbons, alkanes, alkenes, and alkynes in organic chemistry?", "chemistry"),
        ("Explain ionic bonding versus covalent bonding and electronegativity.", "chemistry"),
        ("What is the periodic table trend for ionization energy and atomic radius?", "chemistry"),
        ("Explain mole concept, Avogadro constant and molarity calculation.", "chemistry"),
        ("Describe redox reactions, oxidation state and reducing agents.", "chemistry"),
        # Biology
        ("What is the cell theory and functions of cell membrane and nucleus?", "biology"),
        ("Explain the process of photosynthesis and function of chlorophyll in chloroplasts.", "biology"),
        ("Describe the structure of human heart and mechanism of double circulation.", "biology"),
        ("Explain Mendel's laws of inheritance and monohybrid genetic cross.", "biology"),
        ("What is the structure of DNA double helix model proposed by Watson and Crick?", "biology"),
        ("Explain aerobic respiration vs anaerobic glycolysis in mitochondria.", "biology"),
        # Mathematics
        ("What is the quadratic formula to find roots of ax^2 + bx + c = 0?", "mathematics"),
        ("Define an Arithmetic Progression (AP) and formula for the nth term.", "mathematics"),
        ("What is the formula for the sum of the first n terms of an AP?", "mathematics"),
        ("State and prove Pythagoras theorem for right-angled triangles.", "mathematics"),
        ("Explain trigonometric identities for sin, cos, and tan ratios.", "mathematics"),
        ("How to find the derivative of sin(x) and evaluate definite integrals?", "mathematics"),
        ("Calculate the probability and combinations of rolling two dice.", "mathematics"),
    ]
    for q, s in en:
        q_list.append({"lang": "en", "query": q, "expected": s, "type": "standard_english"})

    # ----------------------------------------------------
    # 2. TELUGU (25 Questions: 6 Physics, 6 Chem, 6 Bio, 7 Math)
    # ----------------------------------------------------
    te = [
        # Physics
        ("న్యూటన్ మొదటి గమన నియమం మరియు జడత్వం నిర్వచించండి.", "physics"),
        ("సార్వత్రిక గురుత్వాకర్షణ నియమం మరియు స్థిరాంకం G అంటే ఏమిటి?", "physics"),
        ("కాంతి వక్రీభవనం మరియు స్నెల్ నియమం వివరించండి.", "physics"),
        ("ఓమ్ నియమం మరియు విద్యుత్ ప్రవాహం, నిరోధం సంబంధం ఏమిటి?", "physics"),
        ("పని, గతిజ శక్తి మరియు స్థితిజ శక్తి సూత్రాలు ఏమిటి?", "physics"),
        ("ధ్వని తరంగాలు, పౌనఃపున్యం మరియు కంపన పరిమితి అంటే ఏమిటి?", "physics"),
        # Chemistry
        ("ఉష్ణమోచక మరియు ఉష్ణగ్రాహక రసాయన చర్యల మధ్య తేడాలు ఏమిటి?", "chemistry"),
        ("హైడ్రోకార్బన్లు, ఆల్కేన్లు మరియు కర్బన సమ్మేళనాలు అంటే ఏమిటి?", "chemistry"),
        ("అయానిక బంధం మరియు సమయోజనీయ బంధం మధ్య వ్యత్యాసం ఏమిటి?", "chemistry"),
        ("ఆవర్తన పట్టికలో మూలకాల వర్గీకరణ మరియు సమూహాలు ఏమిటి?", "chemistry"),
        ("మోల్ భావన మరియు అవగాడ్రో సంఖ్య లెక్కించడం ఎలా?", "chemistry"),
        ("ఆమ్లాలు, క్షారాలు మరియు pH స్కేల్ నిర్వచించండి.", "chemistry"),
        # Biology
        ("కణ సిద్ధాంతం అంటే ఏమిటి? దానిని ఎవరు ప్రతిపాదించారు?", "biology"),
        ("కిరణజన్య సంయోగక్రియ ప్రక్రియ మరియు హరితరేణువు విధులు ఏమిటి?", "biology"),
        ("మానవ గుండె నిర్మాణం మరియు రక్త ప్రసరణ వ్యవస్థ వివరించండి.", "biology"),
        ("మెండల్ అనువంశికత సూత్రాలు మరియు ఏక సంకర సంకరణం ఏమిటి?", "biology"),
        ("డీఎన్‌ఏ నిర్మాణం మరియు ద్వంద్వ కుండలి నమూనా వివరించండి.", "biology"),
        ("వాయు సహిత శ్వాసక్రియ మరియు మైటోకాండ్రియా పాత్ర ఏమిటి?", "biology"),
        # Mathematics
        ("వర్గ సమీకరణం మూలాలు కనుగొనే సూత్రం మరియు విచక్షణి ఏమిటి?", "mathematics"),
        ("అంకశ్రేఢి (AP) నిర్వచనం మరియు nవ పదం కనుగొనే సూత్రం ఏమిటి?", "mathematics"),
        ("అంకశ్రేఢిలో మొదటి n పదాల మొత్తం కనుగొనే సూత్రం ఏమిటి?", "mathematics"),
        ("పైథాగరస్ సిద్ధాంతం మరియు లంబకోణ త్రిభుజం ధర్మాలు ఏమిటి?", "mathematics"),
        ("త్రికోణమితి నిష్పత్తులు sin, cos, tan నిర్వచించండి.", "mathematics"),
        ("సమాకలనం మరియు అవకలనం ప్రాథమిక సిద్ధాంతాలు వివరించండి.", "mathematics"),
        ("సంభావ్యత నిర్వచనం మరియు ఒక ఘటన సంభావ్యత ఎలా లెక్కిస్తారు?", "mathematics"),
    ]
    for q, s in te:
        q_list.append({"lang": "te", "query": q, "expected": s, "type": "standard_telugu"})

    # ----------------------------------------------------
    # 3. HINDI (25 Questions: 6 Physics, 6 Chem, 6 Bio, 7 Math)
    # ----------------------------------------------------
    hi = [
        # Physics
        ("न्यूटन का गति का प्रथम नियम और जड़त्व की परिभाषा दीजिए।", "physics"),
        ("सार्वत्रिक गुरुत्वाकर्षण का नियम और स्थिरांक G समझाइए।", "physics"),
        ("प्रकाश का अपवर्तन और स्नेल का नियम समझाइए।", "physics"),
        ("ओम का नियम और विभवांतर तथा विद्युत धारा में संबंध बताइए।", "physics"),
        ("कार्य, गतिज ऊर्जा और स्थितिज ऊर्जा के सूत्र लिखिए।", "physics"),
        ("ध्वनि तरंगें, आवृत्ति और आयाम का क्या अर्थ है?", "physics"),
        # Chemistry
        ("ऊष्माक्षेपी और ऊष्माशोषी अभिक्रियाओं में क्या अंतर है?", "chemistry"),
        ("हाइड्रोकार्बन, एल्केन, एल्कीन और एल्काइन क्या होते हैं?", "chemistry"),
        ("आयनिक आबंध और सहसंयोजक आबंध में क्या अंतर है?", "chemistry"),
        ("आवर्त सारणी में तत्वों का वर्गीकरण और आवर्तिता समझाइए।", "chemistry"),
        ("मोल संकल्पना और आवोगाद्रो संख्या का महत्व समझाइए।", "chemistry"),
        ("अम्ल, क्षारक और pH पैमाने की व्याख्या कीजिए।", "chemistry"),
        # Biology
        ("कोशिका सिद्धांत क्या है और इसे किसने प्रतिपादित किया?", "biology"),
        ("प्रकाश संश्लेषण की प्रक्रिया और क्लोरोफिल की भूमिका समझाइए।", "biology"),
        ("मानव हृदय की संरचना और दोहरा परिसंचरण समझाइए।", "biology"),
        ("मेंडल के वंशागति के नियम और एकसंकर संकरण क्या है?", "biology"),
        ("डीएनए की संरचना और द्विकुंडलिनी मॉडल का वर्णन कीजिए।", "biology"),
        ("वायवीय और अवायवीय श्वसन में अंतर तथा माइटोकॉन्ड्रिया का कार्य।", "biology"),
        # Mathematics
        ("द्विघात समीकरण के मूल ज्ञात करने का द्विघाती सूत्र क्या है?", "mathematics"),
        ("समांतर श्रेणी (AP) की परिभाषा और nवें पद का सूत्र लिखिए।", "mathematics"),
        ("समांतर श्रेणी के प्रथम n पदों के योगफल का सूत्र क्या है?", "mathematics"),
        ("पाइथागोरस प्रमेय का कथन और समकोण त्रिभुज में सत्यापन लिखिए।", "mathematics"),
        ("त्रिकोणमितीय अनुपात sin, cos और tan की परिभाषा दीजिए।", "mathematics"),
        ("अवकलन और समाकलन के मूलभूत नियम क्या हैं?", "mathematics"),
        ("प्रायिकता की परिभाषा और किसी घटना की संभावना कैसे ज्ञात करें?", "mathematics"),
    ]
    for q, s in hi:
        q_list.append({"lang": "hi", "query": q, "expected": s, "type": "standard_hindi"})

    # ----------------------------------------------------
    # 4. MIXED-LANGUAGE, TRANSLITERATED, AMBIGUOUS & TECHNICAL (25 Questions)
    # ----------------------------------------------------
    mixed = [
        # Hinglish / Tenglish Physics
        ("Newton third law me action and reaction force equal and opposite hota hai?", "physics"),
        ("Projectile motion me maximum height aur range ka formula kya hai?", "physics"),
        ("Electric circuit lo resistance parallel ga connect cheste equivalent resistance entha?", "physics"),
        ("Current electricity me Kirchhoff junction law and voltage law explain karo.", "physics"),
        ("Simple harmonic motion lo kinetic energy and potential energy conversation ela untundi?", "physics"),
        ("Kinematics equation v = u + at derivation in physics.", "physics"),
        # Hinglish / Tenglish Chemistry
        ("Chemical reaction balance karne ke steps and law of conservation of mass.", "chemistry"),
        ("Organic chemistry me benzene ring aur aromaticity Hückel rule kya hai?", "chemistry"),
        ("pH scale lo strong acid and weak acid madhya difference enti?", "chemistry"),
        ("Covalent bond me electron sharing and octet rule explain cheyyandi.", "chemistry"),
        ("Thermodynamics me enthalpy change delta H negative hone par reaction exothermic hoti hai?", "chemistry"),
        ("Redox reaction lo oxidizing agent and reducing agent ela identify cheyali?", "chemistry"),
        # Hinglish / Tenglish Biology
        ("Human body me nephron and kidney excretion mechanism kaise work karta hai?", "biology"),
        ("Photosynthesis lo light reaction thylakoid membrane lo jarugutunda?", "biology"),
        ("Cell division me mitosis vs meiosis chromosomes number change explain karo.", "biology"),
        ("Genetics me dominant allele and recessive allele difference in Telugu.", "biology"),
        ("Endocrine glands pituitary gland master gland ani enduku antaru?", "biology"),
        ("Plant transpiration process and stomata opening closing mechanism.", "biology"),
        # Hinglish / Tenglish Mathematics
        ("Quadratic equation solve cheyadaniki discriminant formula b^2 - 4ac use cheyali.", "mathematics"),
        ("Integration of x^2 dx and definite integral limits evaluate kaise kare?", "mathematics"),
        ("Matrix multiplication me order of matrices kya hona chahiye?", "mathematics"),
        ("Trigonometry formulas sin square theta plus cos square theta equals 1 proof.", "mathematics"),
        ("Coordinate geometry distance between two points (x1, y1) and (x2, y2).", "mathematics"),
        ("Linear programming problem me feasible region and objective function.", "mathematics"),
        ("Binomial theorem expansion of (a + b)^n formula explain karo.", "mathematics"),
    ]
    for q, s in mixed:
        q_list.append({"lang": "mixed", "query": q, "expected": s, "type": "mixed_transliterated_technical"})

    return q_list

def evaluate_classifier():
    from app.src.modules.tutor.subject_classifier import detect_subject

    questions = get_100_balanced_questions()
    print(f"\n=======================================================")
    print(f"EVALUATING SUBJECT CLASSIFIER ON {len(questions)} BALANCED QUESTIONS")
    print(f"=======================================================")

    y_true = []
    y_pred = []
    by_lang = defaultdict(lambda: {"total": 0, "correct": 0})
    failures = []

    for idx, item in enumerate(questions, 1):
        q = item["query"]
        expected = item["expected"]
        lang = item["lang"]

        pred = detect_subject(q)
        norm_pred = "mathematics" if pred == "maths" else pred
        norm_exp = "mathematics" if expected == "maths" else expected

        y_true.append(norm_exp)
        y_pred.append(norm_pred)

        correct = (norm_pred == norm_exp)
        by_lang[lang]["total"] += 1
        if correct:
            by_lang[lang]["correct"] += 1
        else:
            failures.append({
                "id": idx,
                "lang": lang,
                "query": q,
                "expected": norm_exp,
                "predicted": norm_pred
            })

    # Metrics
    total = len(questions)
    total_correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    overall_acc = (total_correct / total) * 100.0

    print(f"\n--- OVERALL ACCURACY: {total_correct}/{total} ({overall_acc:.2f}%) ---")
    print("\n--- PER-LANGUAGE / CATEGORY BREAKDOWN ---")
    for lang, d in sorted(by_lang.items()):
        acc = (d["correct"] / d["total"]) * 100.0
        print(f"  {lang.upper():<8}: {d['correct']}/{d['total']} ({acc:.2f}%)")

    labels = ["physics", "chemistry", "biology", "mathematics"]
    print("\n--- CLASSIFICATION REPORT (PRECISION, RECALL, F1) ---")
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True)
    print(classification_report(y_true, y_pred, labels=labels, digits=4))

    print("\n--- CONFUSION MATRIX ---")
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    header = f"{'True/Pred':<15} | " + " | ".join(f"{l:<12}" for l in labels)
    print(header)
    print("-" * len(header))
    for i, l in enumerate(labels):
        row_str = " | ".join(f"{cm[i][j]:<12}" for j in range(len(labels)))
        print(f"{l:<15} | {row_str}")

    if failures:
        print(f"\n--- FAILURES ({len(failures)}) ---")
        for f in failures:
            print(f"  [{f['lang']}] {f['expected']} -> {f['predicted']}: {f['query']}")

    eval_data = {
        "overall_accuracy": round(overall_acc, 2),
        "total_evaluated": total,
        "total_correct": total_correct,
        "per_language": {
            l: {"correct": d["correct"], "total": d["total"], "accuracy": round(d["correct"]/d["total"]*100, 2)}
            for l, d in by_lang.items()
        },
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "labels": labels,
        "failures": failures
    }

    with open(api_dir / "subject_classification_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)

    return eval_data

if __name__ == "__main__":
    evaluate_classifier()
