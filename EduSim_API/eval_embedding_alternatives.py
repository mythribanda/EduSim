"""
Staging Comparison of Multilingual Embedding Models vs Production Model.
Evaluates:
1. sentence-transformers/all-MiniLM-L6-v2 (Current Production, 384-dim)
2. sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (Multilingual MiniLM, 384-dim)
3. intfloat/multilingual-e5-small (Multilingual E5, 384-dim)
"""

import time
import numpy as np
from sentence_transformers import SentenceTransformer

# 6 Representative curriculum concepts with their NCERT textbook passages
TEST_CHUNKS = [
    {
        "id": "gravitation",
        "subject": "physics",
        "text": "Every particle in the universe attracts every other particle with a force directly proportional to the product of their masses and inversely proportional to the square of the distance between them. F = G (m1 m2) / r^2 where G is universal gravitational constant.",
        "queries": {
            "en": "What is the universal law of gravitation and gravitational constant?",
            "te": "సార్వత్రిక గురుత్వాకర్షణ నియమం మరియు స్థిరాంకం G అంటే ఏమిటి?",
            "hi": "गुरुत्वाकर्षण का सार्वत्रिक नियम और स्थिरांक G क्या है?"
        }
    },
    {
        "id": "photosynthesis",
        "subject": "biology",
        "text": "Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize nutrients from carbon dioxide and water. Photosynthesis in plants generally involves the green pigment chlorophyll and generates oxygen as a byproduct. 6CO2 + 6H2O -> C6H12O6 + 6O2",
        "queries": {
            "en": "Explain the process of photosynthesis and role of chlorophyll.",
            "te": "కిరణజన్య సంయోగక్రియ మరియు హరితరేణువు పాత్ర ఏమిటి?",
            "hi": "प्रकाश संश्लेषण की प्रक्रिया और क्लोरोफिल की भूमिका समझाइए।"
        }
    },
    {
        "id": "exothermic",
        "subject": "chemistry",
        "text": "Reactions in which heat is released along with the formation of products are called exothermic chemical reactions. Burning of natural gas is an exothermic reaction. Reactions in which energy is absorbed are known as endothermic reactions.",
        "queries": {
            "en": "Differentiate between exothermic and endothermic reactions.",
            "te": "ఉష్ణమోచక మరియు ఉష్ణగ్రాహక చర్యల మధ్య తేడాలు ఏమిటి?",
            "hi": "ऊष्माक्षेपी और ऊष्माशोषी अभिक्रियाओं में क्या अंतर है?"
        }
    },
    {
        "id": "quadratic",
        "subject": "mathematics",
        "text": "A quadratic equation in the variable x is of the form ax^2 + bx + c = 0, where a, b, c are real numbers and a != 0. The roots are given by x = (-b +- sqrt(b^2 - 4ac)) / (2a). The term b^2 - 4ac is called the discriminant.",
        "queries": {
            "en": "What is the quadratic formula to find roots of ax^2 + bx + c = 0?",
            "te": "వర్గ సమీకరణం మూలాలు కనుగొనే సూత్రం ఏమిటి?",
            "hi": "द्विघात समीकरण ax^2 + bx + c = 0 के मूल ज्ञात करने का सूत्र क्या है?"
        }
    },
    {
        "id": "refraction",
        "subject": "physics",
        "text": "Snell's law of refraction states that the ratio of the sine of the angle of incidence to the sine of the angle of refraction is constant, for the light of a given colour and for the given pair of media. sin(i) / sin(r) = n21, where n21 is refractive index.",
        "queries": {
            "en": "What is Snell's law of refraction and refractive index?",
            "te": "కాంతి వక్రీభవనం మరియు స్నెల్ నియమం వివరించండి.",
            "hi": "प्रकाश का अपवर्तन और स्नेल का नियम समझाइए।"
        }
    },
    {
        "id": "cell_theory",
        "subject": "biology",
        "text": "Schleiden and Schwann together formulated the cell theory. This theory however did not explain as to how new cells were formed. Rudolf Virchow first explained that cells divided and new cells are formed from pre-existing cells: Omnis cellula-e cellula.",
        "queries": {
            "en": "What is the cell theory and who proposed it?",
            "te": "కణ సిద్ధాంతం అంటే ఏమిటి? దానిని ఎవరు ప్రతిపాదించారు?",
            "hi": "कोशिका सिद्धांत क्या है और इसे किसने प्रतिपादित किया?"
        }
    }
]

MODELS = [
    ("all-MiniLM-L6-v2 (Production)", "sentence-transformers/all-MiniLM-L6-v2", False),
    ("paraphrase-multilingual-MiniLM-L12-v2", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", False),
    ("multilingual-e5-small", "intfloat/multilingual-e5-small", True),
]

def cosine_sim(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def run_evaluation():
    print("=" * 80)
    print("STAGING BENCHMARK: MULTILINGUAL EMBEDDING MODELS")
    print("=" * 80)
    
    results = {}
    
    for label, model_name, is_e5 in MODELS:
        print(f"\nEvaluating: {label} ({model_name})...")
        t0 = time.perf_counter()
        try:
            model = SentenceTransformer(model_name)
        except Exception as e:
            print(f"Failed to load {model_name}: {e}")
            continue
        load_time = time.perf_counter() - t0
        
        # Encode textbook chunks
        chunk_texts = [c["text"] if not is_e5 else f"passage: {c['text']}" for c in TEST_CHUNKS]
        chunk_embeddings = model.encode(chunk_texts, normalize_embeddings=True)
        
        lang_scores = {"en": [], "te": [], "hi": []}
        rank_1_hits = {"en": 0, "te": 0, "hi": 0}
        
        for lang in ("en", "te", "hi"):
            for i, chunk in enumerate(TEST_CHUNKS):
                q = chunk["queries"][lang]
                q_text = q if not is_e5 else f"query: {q}"
                q_emb = model.encode(q_text, normalize_embeddings=True)
                
                # Compute cosine similarities with all chunks
                sims = [cosine_sim(q_emb, c_emb) for c_emb in chunk_embeddings]
                target_sim = sims[i]
                lang_scores[lang].append(target_sim)
                
                # Check if correct chunk is rank 1
                best_idx = int(np.argmax(sims))
                if best_idx == i:
                    rank_1_hits[lang] += 1
                    
        total_queries = len(TEST_CHUNKS)
        results[label] = {
            "load_time_s": round(load_time, 2),
            "dim": chunk_embeddings.shape[1],
            "en_p1": f"{rank_1_hits['en']}/{total_queries} ({rank_1_hits['en']/total_queries*100:.1f}%)",
            "te_p1": f"{rank_1_hits['te']}/{total_queries} ({rank_1_hits['te']/total_queries*100:.1f}%)",
            "hi_p1": f"{rank_1_hits['hi']}/{total_queries} ({rank_1_hits['hi']/total_queries*100:.1f}%)",
            "en_mean_sim": round(float(np.mean(lang_scores["en"])), 4),
            "te_mean_sim": round(float(np.mean(lang_scores["te"])), 4),
            "hi_mean_sim": round(float(np.mean(lang_scores["hi"])), 4),
        }
        
    print("\n" + "=" * 80)
    print("STAGING BENCHMARK RESULTS SUMMARY")
    print("=" * 80)
    for model, m in results.items():
        print(f"Model: {model} [Dim: {m['dim']}, Load: {m['load_time_s']}s]")
        print(f"  English P@1: {m['en_p1']} | Mean Sim: {m['en_mean_sim']}")
        print(f"  Telugu P@1:  {m['te_p1']} | Mean Sim: {m['te_mean_sim']}")
        print(f"  Hindi P@1:   {m['hi_p1']} | Mean Sim: {m['hi_mean_sim']}")
        print("-" * 60)

    import json
    with open("staging_embedding_comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_evaluation()
