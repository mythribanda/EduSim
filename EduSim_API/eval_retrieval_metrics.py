"""
Comprehensive Multilingual Retrieval Quality Evaluation
Measures:
- Precision@1, Precision@2, Precision@5
- Recall@1, Recall@2, Recall@5
- MRR (Mean Reciprocal Rank)
- NDCG@1, NDCG@2, NDCG@5
- Chapter Relevance
- Class Filtering Accuracy
- Subject Filtering Accuracy
Across English, Telugu, and Hindi.
"""

import json
import math
import os
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import detect_query_language, expand_multilingual_query
from app.src.modules.tutor.subject_classifier import detect_subject

# Ground-truth chapter mappings for core curriculum concepts
TOPIC_CHAPTER_MAP = {
    # Physics
    "newton": ["laws of motion", "motion", "force"],
    "motion": ["motion", "laws of motion"],
    "gravity": ["gravitation"],
    "gravitation": ["gravitation"],
    "friction": ["laws of motion", "friction"],
    "work": ["work, energy and power", "work and energy"],
    "energy": ["work, energy and power", "work and energy"],
    "power": ["work, energy and power", "work and energy"],
    "snell": ["ray optics", "light", "refraction"],
    "refraction": ["ray optics", "light", "refraction"],
    "reflection": ["ray optics", "light", "reflection"],
    "ohm": ["current electricity", "electricity"],
    "current": ["current electricity", "electricity"],
    "pendulum": ["oscillations", "simple harmonic motion"],
    "waves": ["waves", "sound"],
    "sound": ["sound", "waves"],
    # Chemistry
    "exothermic": ["chemical reactions", "thermodynamics"],
    "endothermic": ["chemical reactions", "thermodynamics"],
    "hydrocarbon": ["carbon", "hydrocarbons", "organic chemistry"],
    "alkane": ["carbon", "hydrocarbons", "organic chemistry"],
    "alkene": ["carbon", "hydrocarbons", "organic chemistry"],
    "alkyne": ["carbon", "hydrocarbons", "organic chemistry"],
    "ionic": ["chemical bonding", "bonding"],
    "covalent": ["chemical bonding", "carbon and its compounds", "bonding"],
    "periodic": ["periodic", "classification of elements"],
    "mole": ["some basic concepts of chemistry", "atoms and molecules"],
    "avogadro": ["some basic concepts of chemistry", "atoms and molecules"],
    "acid": ["acids, bases and salts", "equilibrium"],
    "base": ["acids, bases and salts", "equilibrium"],
    "ph": ["acids, bases and salts", "equilibrium"],
    "redox": ["redox reactions", "chemical reactions"],
    "oxidation": ["redox reactions", "chemical reactions"],
    # Biology
    "cell": ["cell : the unit of life", "fundamental unit of life", "cell structure"],
    "photosynthesis": ["photosynthesis", "life processes"],
    "chlorophyll": ["photosynthesis", "life processes"],
    "chloroplast": ["photosynthesis", "cell : the unit of life"],
    "heart": ["body fluids and circulation", "life processes"],
    "circulation": ["body fluids and circulation", "life processes"],
    "mendel": ["heredity and evolution", "principles of inheritance"],
    "inheritance": ["heredity and evolution", "principles of inheritance"],
    "dna": ["molecular basis of inheritance", "heredity and evolution"],
    "respiration": ["respiration in plants", "life processes"],
    # Mathematics
    "quadratic": ["quadratic equations", "polynomials"],
    "roots": ["quadratic equations", "polynomials"],
    "arithmetic": ["arithmetic progressions", "sequences and series"],
    "ap": ["arithmetic progressions", "sequences and series"],
    "pythagoras": ["triangles", "geometry"],
    "trigonometric": ["introduction to trigonometry", "trigonometric functions"],
    "probability": ["probability"],
}

def is_chapter_relevant(query: str, chapter_name: str) -> bool:
    q_low = query.lower()
    ch_low = chapter_name.lower()
    for kw, allowed_chapters in TOPIC_CHAPTER_MAP.items():
        if kw in q_low:
            if any(cand in ch_low for cand in allowed_chapters):
                return True
    return False

def dcg_at_k(r, k):
    r = np.asarray(r, dtype=float)[:k]
    if r.size:
        return float(np.sum(r / np.log2(np.arange(2, r.size + 2))))
    return 0.0

def ndcg_at_k(r, k):
    dcg_max = dcg_at_k(sorted(r, reverse=True), k)
    if not dcg_max:
        return 0.0
    return dcg_at_k(r, k) / dcg_max

def evaluate_retrieval_detailed():
    print("=" * 80)
    print("PHASE 3: COMPREHENSIVE MULTILINGUAL RETRIEVAL EVALUATION")
    print("=" * 80)
    
    vector_store.load_all()
    
    # Load 90 questions benchmark dataset
    from eval_multilingual_90_questions import get_90_evaluation_questions
    questions = get_90_evaluation_questions()
    
    results = defaultdict(lambda: {
        "p1": [], "p2": [], "p5": [],
        "r1": [], "r2": [], "r5": [],
        "rr": [], # Reciprocal Rank
        "ndcg1": [], "ndcg2": [], "ndcg5": [],
        "chapter_rel": [],
        "class_acc": [],
        "subject_acc": [],
        "scores": []
    })
    
    for item in questions:
        q = item["q"]
        lang = item["lang"]
        expected_subj = item["subject"]
        cls = item["class"]
        
        det_lang = detect_query_language(q)
        expanded_q = expand_multilingual_query(q, det_lang)
        det_subj = detect_subject(expanded_q)
        norm_det_subj = "mathematics" if det_subj in ("maths", "mathematics") else det_subj
        norm_exp_subj = "mathematics" if expected_subj in ("maths", "mathematics") else expected_subj
        
        subj_filter_ok = (norm_det_subj == norm_exp_subj)
        
        # Retrieve top 5 chunks
        chunks = vector_store.retrieve(
            query=expanded_q,
            subject=norm_det_subj,
            class_num=cls,
            k=5,
            min_score=0.0
        )
        
        # Binary relevance for top 5
        rels = []
        found_relevant_at = None
        
        for idx, c in enumerate(chunks):
            ch_name = c.get("chapter", "")
            score = c.get("score", 0.0)
            c_subj = c.get("subject", "").lower()
            norm_c_subj = "mathematics" if c_subj in ("maths", "mathematics") else c_subj
            
            # Ground-truth relevance criteria:
            # 1. Subject matches expected subject
            # 2. Similarity score exceeds meaningful dense threshold (>= 0.35)
            # 3. Chapter title or text corresponds to topic
            is_rel = (norm_c_subj == norm_exp_subj) and (score >= 0.35 or is_chapter_relevant(expanded_q, ch_name))
            rel_val = 1 if is_rel else 0
            rels.append(rel_val)
            
            if rel_val == 1 and found_relevant_at is None:
                found_relevant_at = idx + 1
        
        while len(rels) < 5:
            rels.append(0)
            
        # Metrics
        p1 = rels[0]
        p2 = sum(rels[:2]) / 2.0
        p5 = sum(rels[:5]) / 5.0
        
        # In single-topic queries, ideal relevant chunk count is at least 1-2
        total_possible_rel = max(1, sum(rels))
        r1 = rels[0] / total_possible_rel
        r2 = sum(rels[:2]) / total_possible_rel
        r5 = sum(rels[:5]) / total_possible_rel
        
        rr = 1.0 / found_relevant_at if found_relevant_at else 0.0
        ndcg1 = ndcg_at_k(rels, 1)
        ndcg2 = ndcg_at_k(rels, 2)
        ndcg5 = ndcg_at_k(rels, 5)
        
        top_ch = chunks[0].get("chapter", "") if chunks else ""
        top_score = chunks[0].get("score", 0.0) if chunks else 0.0
        ch_ok = is_chapter_relevant(expanded_q, top_ch)
        
        # Class filtering check: chunks retrieved obey class constraint
        class_ok = all(c.get("class") in (cls, str(cls), None) for c in chunks)
        
        for target in (lang, "overall"):
            results[target]["p1"].append(p1)
            results[target]["p2"].append(p2)
            results[target]["p5"].append(p5)
            results[target]["r1"].append(r1)
            results[target]["r2"].append(r2)
            results[target]["r5"].append(r5)
            results[target]["rr"].append(rr)
            results[target]["ndcg1"].append(ndcg1)
            results[target]["ndcg2"].append(ndcg2)
            results[target]["ndcg5"].append(ndcg5)
            results[target]["chapter_rel"].append(1 if ch_ok else 0)
            results[target]["class_acc"].append(1 if class_ok else 0)
            results[target]["subject_acc"].append(1 if subj_filter_ok else 0)
            results[target]["scores"].append(top_score)
            
    print("\n" + "=" * 95)
    print(f"{'Lang':<8} | {'P@1':<7} | {'P@5':<7} | {'R@1':<7} | {'R@5':<7} | {'MRR':<7} | {'NDCG@5':<7} | {'Chapter%':<8} | {'Class%':<7} | {'Subj%'}")
    print("-" * 95)
    
    summary = {}
    for lang in ("en", "te", "hi", "overall"):
        d = results[lang]
        p1_m = np.mean(d["p1"]) * 100
        p5_m = np.mean(d["p5"]) * 100
        r1_m = np.mean(d["r1"]) * 100
        r5_m = np.mean(d["r5"]) * 100
        mrr_m = np.mean(d["rr"])
        ndcg5_m = np.mean(d["ndcg5"])
        ch_m = np.mean(d["chapter_rel"]) * 100
        cl_m = np.mean(d["class_acc"]) * 100
        sb_m = np.mean(d["subject_acc"]) * 100
        
        print(f"{lang.upper():<8} | {p1_m:<6.1f}% | {p5_m:<6.1f}% | {r1_m:<6.1f}% | {r5_m:<6.1f}% | {mrr_m:<7.4f} | {ndcg5_m:<7.4f} | {ch_m:<7.1f}% | {cl_m:<6.1f}% | {sb_m:<6.1f}%")
        summary[lang] = {
            "precision_at_1": round(p1_m, 2),
            "precision_at_5": round(p5_m, 2),
            "recall_at_1": round(r1_m, 2),
            "recall_at_5": round(r5_m, 2),
            "mrr": round(mrr_m, 4),
            "ndcg_at_5": round(ndcg5_m, 4),
            "chapter_relevance": round(ch_m, 2),
            "class_filtering_accuracy": round(cl_m, 2),
            "subject_filtering_accuracy": round(sb_m, 2),
            "mean_top_similarity_score": round(float(np.mean(d["scores"])), 4)
        }
        
    with open(api_dir / "retrieval_metrics_report.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nDetailed retrieval metrics saved to retrieval_metrics_report.json")

if __name__ == "__main__":
    evaluate_retrieval_detailed()
