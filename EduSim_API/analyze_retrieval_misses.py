import json
import sys
from pathlib import Path
from collections import defaultdict

api_dir = Path(".").resolve()
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import detect_query_language, expand_multilingual_query
from app.src.modules.tutor.subject_classifier import detect_subject
from eval_multilingual_90_questions import get_90_evaluation_questions
from eval_retrieval_metrics import is_chapter_relevant

vector_store.load_all()
questions = get_90_evaluation_questions()

print(f"Total questions to analyze: {len(questions)}")
misses = []

for idx, item in enumerate(questions):
    q = item["q"]
    lang = item["lang"]
    expected_subj = item["subject"]
    cls = item["class"]
    
    det_lang = detect_query_language(q)
    expanded_q = expand_multilingual_query(q, det_lang)
    det_subj = detect_subject(expanded_q)
    norm_det_subj = "mathematics" if det_subj in ("maths", "mathematics") else det_subj
    norm_exp_subj = "mathematics" if expected_subj in ("maths", "mathematics") else expected_subj
    
    chunks = vector_store.retrieve(
        query=expanded_q,
        subject=norm_det_subj,
        class_num=cls,
        k=5,
        min_score=0.0
    )
    
    top_chunk = chunks[0] if chunks else {}
    top_score = top_chunk.get("score", 0.0)
    top_ch = top_chunk.get("chapter", "")
    top_subj = top_chunk.get("subject", "").lower()
    norm_top_subj = "mathematics" if top_subj in ("maths", "mathematics") else top_subj
    
    is_rel = (norm_top_subj == norm_exp_subj) and (top_score >= 0.35 or is_chapter_relevant(expanded_q, top_ch))
    
    if not is_rel:
        misses.append({
            "idx": idx,
            "q": q,
            "lang": lang,
            "expected_subj": expected_subj,
            "detected_subj": det_subj,
            "expanded_q": expanded_q,
            "class": cls,
            "top_score": top_score,
            "top_ch": top_ch,
            "top_subj": top_subj,
            "top_text": top_chunk.get("text", "")[:120] if top_chunk else "NO CHUNKS"
        })

print(f"\nTotal P@1 misses: {len(misses)} / {len(questions)}")
by_lang = defaultdict(list)
for m in misses:
    by_lang[m["lang"]].append(m)

for l, m_list in by_lang.items():
    print(f"\n================ {l.upper()} MISSES ({len(m_list)}) ================")
    for m in m_list:
        print(f"[{m['idx']}] Q: {m['q']}")
        print(f"  Exp Subj: {m['expected_subj']} | Det Subj: {m['detected_subj']} | Class: {m['class']}")
        print(f"  Expanded: {m['expanded_q']}")
        print(f"  Top Score: {m['top_score']:.4f} | Top Ch: {m['top_ch']} | Top Subj: {m['top_subj']}")
        print(f"  Top Text: {m['top_text']}")
        print("-" * 60)
