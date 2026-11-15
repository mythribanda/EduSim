import asyncio
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import (
    detect_query_language,
    expand_multilingual_query,
    analyze_tutor_query
)
from app.src.modules.tutor.subject_classifier import detect_subject

def get_90_evaluation_questions():
    questions = []

    # ==========================
    # 30 ENGLISH QUESTIONS
    # ==========================
    en_physics = [
        "State Newton's first law of motion and explain inertia.",
        "What is Newton's second law of motion and write formula F=ma?",
        "Explain Newton's third law of motion with action and reaction pairs.",
        "What is universal law of gravitation and gravitational constant G?",
        "Define work, kinetic energy, and potential energy.",
        "What is Snell's law of refraction and refractive index?",
        "Explain Ohm's law and the relationship between voltage and current.",
        "What are transverse and longitudinal sound waves?"
    ]
    en_chemistry = [
        "What is a chemical reaction and how to balance chemical equations?",
        "Differentiate between exothermic and endothermic reactions.",
        "Explain acids, bases, and the pH scale with examples.",
        "What is the difference between ionic bond and covalent bond?",
        "Describe Mendeleev's periodic law and the modern periodic table.",
        "What is the mole concept and Avogadro's number?",
        "Explain oxidation and reduction reactions with examples.",
        "What are hydrocarbons, alkanes, alkenes, and alkynes?"
    ]
    en_biology = [
        "What is the cell theory and who proposed it?",
        "Describe the structure and function of plant cell wall and membrane.",
        "Explain the process of photosynthesis and role of chlorophyll.",
        "What is aerobic and anaerobic respiration in living organisms?",
        "Describe the structure of human heart and double circulation.",
        "What is the structure of DNA and double helix model?",
        "Explain Mendel's laws of inheritance and monohybrid cross."
    ]
    en_maths = [
        "What is the quadratic formula to find roots of ax^2 + bx + c = 0?",
        "Find the roots and discriminant of quadratic equation 2x^2 - 4x + 3 = 0.",
        "Define an Arithmetic Progression and formula for nth term.",
        "What is the formula for the sum of first n terms of an AP?",
        "Explain trigonometric ratios sin, cos, and tan in a right-angled triangle.",
        "State and prove Pythagoras theorem for right triangles.",
        "How to calculate the probability of an event?"
    ]

    for q in en_physics: questions.append({"lang": "en", "subject": "physics", "class": 11, "q": q})
    for q in en_chemistry: questions.append({"lang": "en", "subject": "chemistry", "class": 11, "q": q})
    for q in en_biology: questions.append({"lang": "en", "subject": "biology", "class": 11, "q": q})
    for q in en_maths: questions.append({"lang": "en", "subject": "maths", "class": 10, "q": q})

    # ==========================
    # 30 TELUGU QUESTIONS
    # ==========================
    te_physics = [
        "న్యూటన్ మొదటి గమన నియమం మరియు జడత్వం అంటే ఏమిటి?",
        "న్యూటన్ రెండవ గమన నియమం సూత్రం F=ma వివరించండి.",
        "న్యూటన్ మూడవ గమన నియమంలో చర్య మరియు ప్రతిచర్య అంటే ఏమిటి?",
        "సార్వత్రిక గురుత్వాకర్షణ నియమం మరియు స్థిరాంకం G అంటే ఏమిటి?",
        "పని, గతిజ శక్తి మరియు స్థితిజ శక్తి నిర్వచించండి.",
        "కాంతి వక్రీభవనం మరియు స్నెల్ నియమం వివరించండి.",
        "ఓమ్ నియమం మరియు విద్యుత్ ప్రవాహం, వోల్టేజ్ సంబంధం ఏమిటి?",
        "ధ్వని తరంగాలు మరియు కంపన పరిమితి అంటే ఏమిటి?"
    ]
    te_chemistry = [
        "రసాయన చర్య అంటే ఏమిటి? రసాయన సమీకరణాలను ఎలా తుల్యం చేయాలి?",
        "ఉష్ణమోచక మరియు ఉష్ణగ్రాహక చర్యల మధ్య తేడాలు ఏమిటి?",
        "ఆమ్లాలు, క్షారాలు మరియు pH స్కేల్ గురించి వివరించండి.",
        "అయానిక బంధం మరియు సమయోజనీయ బంధం మధ్య తేడా ఏమిటి?",
        "ఆవర్తన పట్టిక మరియు మూలకాల వర్గీకరణ వివరించండి.",
        "మోల్ భావన మరియు అవగాడ్రో సంఖ్య అంటే ఏమిటి?",
        "ఆక్సీకరణం మరియు క్షయకరణం చర్యలను వివరించండి.",
        "హైడ్రోకార్బన్లు మరియు కార్బన్ సమ్మేళనాలు అంటే ఏమిటి?"
    ]
    te_biology = [
        "కణ సిద్ధాంతం అంటే ఏమిటి? దానిని ఎవరు ప్రతిపాదించారు?",
        "వృక్ష కణం నిర్మాణం మరియు కణ కవచం విధులు వివరించండి.",
        "కిరణజన్య సంయోగక్రియ మరియు హరితరేణువు పాత్ర ఏమిటి?",
        "శ్వాసక్రియలో వాయు సహిత మరియు అవాయు శ్వాసక్రియ తేడాలు ఏమిటి?",
        "మానవ గుండె నిర్మాణం మరియు రక్త ప్రసరణ వ్యవస్థ వివరించండి.",
        "డీఎన్‌ఏ నిర్మాణం మరియు డబుల్ హెలిక్స్ నమూనా ఏమిటి?",
        "మెండల్ అనువంశికత సూత్రాలు వివరించండి."
    ]
    te_maths = [
        "వర్గ సమీకరణం మూలాలు కనుగొనే సూత్రం ఏమిటి?",
        "ద్విఘాత సమీకరణం విచక్షణి మరియు మూలాల స్వభావం ఏమిటి?",
        "అంకశ్రేఢి మరియు nవ పదం సూత్రం ఏమిటి?",
        "అంకశ్రేఢిలోని మొదటి n పదాల మొత్తం కనుగొనే సూత్రం ఏమిటి?",
        "త్రికోణమితి నిష్పత్తులు sin, cos, tan నిర్వచించండి.",
        "పైథాగరస్ సిద్ధాంతం మరియు లంబకోణ త్రిభుజం ధర్మాలు ఏమిటి?",
        "సంభావ్యత భావన మరియు దాని సూత్రం వివరించండి."
    ]

    for q in te_physics: questions.append({"lang": "te", "subject": "physics", "class": 11, "q": q})
    for q in te_chemistry: questions.append({"lang": "te", "subject": "chemistry", "class": 11, "q": q})
    for q in te_biology: questions.append({"lang": "te", "subject": "biology", "class": 11, "q": q})
    for q in te_maths: questions.append({"lang": "te", "subject": "maths", "class": 10, "q": q})

    # ==========================
    # 30 HINDI QUESTIONS
    # ==========================
    hi_physics = [
        "न्यूटन का गति का प्रथम नियम और जड़त्व की परिभाषा दीजिए।",
        "न्यूटन का गति का द्वितीय नियम और सूत्र F=ma समझाइए।",
        "न्यूटन के गति के तृतीय नियम में क्रिया और प्रतिक्रिया क्या है?",
        "गुरुत्वाकर्षण का सार्वत्रिक नियम और स्थिरांक G क्या है?",
        "कार्य, गतिज ऊर्जा और स्थितिज ऊर्जा को परिभाषित कीजिए।",
        "प्रकाश का अपवर्तन और स्नेल का नियम समझाइए।",
        "ओम का नियम और विभवांतर तथा विद्युत धारा में संबंध क्या है?",
        "ध्वनि तरंगें और आवृत्ति तथा तरंगदैर्ध्य क्या है?"
    ]
    hi_chemistry = [
        "रासायनिक अभिक्रिया क्या है और रासायनिक समीकरण संतुलित कैसे करते हैं?",
        "ऊष्माक्षेपी और ऊष्माशोषी अभिक्रियाओं में क्या अंतर है?",
        "अम्ल, क्षार और pH पैमाना उदाहरण सहित समझाइए।",
        "आयनिक आबंध और सहसंयोजक आबंध में क्या अंतर है?",
        "आधुनिक आवर्त सारणी और तत्वों का वर्गीकरण समझाइए।",
        "मोल संकल्पना और आवोगाद्रो संख्या क्या है?",
        "ऑक्सीकरण और अपचयन (रेडॉक्स) अभिक्रियाएं क्या हैं?",
        "हाइड्रोकार्बन और कार्बन के यौगिक क्या हैं?"
    ]
    hi_biology = [
        "कोशिका सिद्धांत क्या है और इसे किसने प्रतिपादित किया?",
        "पादप कोशिका की संरचना और कोशिका भित्ति के कार्य लिखिए।",
        "प्रकाश संश्लेषण की प्रक्रिया और क्लोरोफिल की भूमिका समझाइए।",
        "वायवीय और अवायवीय श्वसन में क्या अंतर है?",
        "मानव हृदय की संरचना और दोहरा परिसंचरण समझाइए।",
        "डीएनए की संरचना और द्विकुंडलिनी मॉडल क्या है?",
        "मेंडल के आनुवंशिकता के नियम क्या हैं?"
    ]
    hi_maths = [
        "द्विघात समीकरण के मूल ज्ञात करने का द्विघाती सूत्र क्या है?",
        "द्विघात समीकरण का विविक्तकर और मूलों की प्रकृति समझाइए।",
        "समांतर श्रेणी (AP) की परिभाषा और nवें पद का सूत्र क्या है?",
        "समांतर श्रेणी के प्रथम n पदों का योगफल ज्ञात करने का सूत्र क्या है?",
        "त्रिकोणमितीय अनुपात sin, cos, tan की परिभाषा दीजिए।",
        "पाइथागोरस प्रमेय का कथन और सत्यापन लिखिए।",
        "प्रायिकता की परिभाषा और सूत्र समझाइए।"
    ]

    for q in hi_physics: questions.append({"lang": "hi", "subject": "physics", "class": 11, "q": q})
    for q in hi_chemistry: questions.append({"lang": "hi", "subject": "chemistry", "class": 11, "q": q})
    for q in hi_biology: questions.append({"lang": "hi", "subject": "biology", "class": 11, "q": q})
    for q in hi_maths: questions.append({"lang": "hi", "subject": "maths", "class": 10, "q": q})

    return questions

def run_multilingual_evaluation_90():
    print("=== PHASE 3: MULTILINGUAL EVALUATION (90 QUESTIONS) ===")
    vector_store.load_all()
    questions = get_90_evaluation_questions()
    print(f"Total questions loaded: {len(questions)}")

    stats = defaultdict(lambda: {"total": 0, "lang_correct": 0, "subj_correct": 0, "retrieval_success": 0, "scores": []})
    detailed_results = []

    for idx, item in enumerate(questions, 1):
        q = item["q"]
        lang = item["lang"]
        subj = item["subject"]
        cls = item["class"]

        detected_lang = detect_query_language(q)
        lang_ok = (detected_lang == lang)

        detected_subj = detect_subject(q)
        # Normalize maths to mathematics
        norm_det_subj = "mathematics" if detected_subj == "maths" else detected_subj
        norm_exp_subj = "mathematics" if subj == "maths" else subj
        subj_ok = (norm_det_subj == norm_exp_subj or norm_det_subj in (norm_exp_subj, "science"))

        expanded_q = expand_multilingual_query(q, detected_lang)

        # Retrieve
        search_subj = norm_exp_subj
        chunks = vector_store.retrieve(
            query=expanded_q,
            subject=search_subj,
            class_num=cls,
            k=2,
            min_score=0.0
        )
        has_chunks = len(chunks) > 0
        top_score = chunks[0]["score"] if has_chunks else 0.0

        stats[lang]["total"] += 1
        if lang_ok: stats[lang]["lang_correct"] += 1
        if subj_ok: stats[lang]["subj_correct"] += 1
        if has_chunks and top_score > 0.20: stats[lang]["retrieval_success"] += 1
        stats[lang]["scores"].append(top_score)

        detailed_results.append({
            "id": idx,
            "lang": lang,
            "detected_lang": detected_lang,
            "lang_ok": lang_ok,
            "expected_subject": norm_exp_subj,
            "detected_subject": norm_det_subj,
            "subj_ok": subj_ok,
            "retrieval_success": has_chunks,
            "top_score": round(top_score, 4),
            "top_book": chunks[0].get("book_title") if has_chunks else None,
            "top_chapter": chunks[0].get("chapter_title") if has_chunks else None,
            "query": q
        })

    print("\n" + "=" * 75)
    print("MULTILINGUAL 90-QUESTION EVALUATION METRICS:")
    print("=" * 75)
    print(f"{'Language':<10} | {'Count':<6} | {'Lang Acc':<10} | {'Subj Acc':<10} | {'Retr Success':<12} | {'Avg Score'}")
    print("-" * 75)
    for l in ["en", "te", "hi"]:
        st = stats[l]
        cnt = st["total"]
        l_acc = st["lang_correct"] / cnt * 100
        s_acc = st["subj_correct"] / cnt * 100
        r_acc = st["retrieval_success"] / cnt * 100
        avg_sc = sum(st["scores"]) / len(st["scores"]) if st["scores"] else 0.0
        print(f"{l.upper():<10} | {cnt:<6} | {l_acc:<9.1f}% | {s_acc:<9.1f}% | {r_acc:<11.1f}% | {avg_sc:.4f}")

    total_cnt = len(questions)
    overall_l_acc = sum(st["lang_correct"] for st in stats.values()) / total_cnt * 100
    overall_s_acc = sum(st["subj_correct"] for st in stats.values()) / total_cnt * 100
    overall_r_acc = sum(st["retrieval_success"] for st in stats.values()) / total_cnt * 100
    all_scores = [sc for st in stats.values() for sc in st["scores"]]
    overall_avg_sc = sum(all_scores) / len(all_scores) if all_scores else 0.0

    print("-" * 75)
    print(f"{'OVERALL':<10} | {total_cnt:<6} | {overall_l_acc:<9.1f}% | {overall_s_acc:<9.1f}% | {overall_r_acc:<11.1f}% | {overall_avg_sc:.4f}")
    print("=" * 75)

    with open(api_dir / "multilingual_90_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total_cnt,
                "language_accuracy": round(overall_l_acc, 2),
                "subject_accuracy": round(overall_s_acc, 2),
                "retrieval_accuracy": round(overall_r_acc, 2),
                "average_score": round(overall_avg_sc, 4),
            },
            "per_language": {
                l: {
                    "count": stats[l]["total"],
                    "language_accuracy": round(stats[l]["lang_correct"] / stats[l]["total"] * 100, 2),
                    "subject_accuracy": round(stats[l]["subj_correct"] / stats[l]["total"] * 100, 2),
                    "retrieval_accuracy": round(stats[l]["retrieval_success"] / stats[l]["total"] * 100, 2),
                    "average_score": round(sum(stats[l]["scores"]) / len(stats[l]["scores"]), 4)
                } for l in ["en", "te", "hi"]
            },
            "details": detailed_results
        }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_multilingual_evaluation_90()
