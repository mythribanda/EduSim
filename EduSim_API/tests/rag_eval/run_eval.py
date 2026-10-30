"""
EduSim RAG Retrieval Evaluation
===============================
Evaluates retrieval quality across 30 curriculum-grounded questions.
Computes hit@1, hit@3, hit@5, and MRR (Mean Reciprocal Rank) based on exact
(book_code, chapter_number) ground truth matching.

Runs both:
  1. Unfiltered (pure semantic vector search across all 6,748 chunks)
  2. Filtered (scoped by expected class and subject)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure EduSim_API is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "EduSim_API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.src.modules.legacy_rag.vector_loader import vector_store

DEFAULT_QUESTIONS_YAML = Path(__file__).resolve().parent / "questions.yaml"


def load_questions(yaml_path: Path) -> List[Dict[str, Any]]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_mode(
    questions: List[Dict[str, Any]],
    use_filter: bool = False,
    k: int = 5,
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """
    Evaluates retrieval for the questions list either with or without class/subject filters.
    Returns (metrics_dict, failures_list).
    """
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    failures = []

    for q in questions:
        qid = q["id"]
        q_text = q["question"]
        exp_book = q["expected_book_code"].strip().lower()
        exp_ch = str(q["expected_chapter_number"]).strip()
        exp_cls = q.get("expected_class")
        exp_subj = q.get("expected_subject")

        filters = {}
        if use_filter:
            if exp_cls is not None:
                filters["class_num"] = exp_cls
            if exp_subj is not None:
                filters["subject"] = exp_subj

        # Retrieve top-k chunks with min_score=0.0 to inspect full candidate ranks
        retrieved_chunks = vector_store.retrieve(
            query=q_text,
            k=k,
            min_score=0.0,
            **filters,
        )

        first_hit_rank = None
        for rank_idx, chunk in enumerate(retrieved_chunks, 1):
            chunk_book = str(chunk.get("book_code", "")).strip().lower()
            chunk_ch = str(chunk.get("chapter_number", "")).strip()

            if chunk_book == exp_book and chunk_ch == exp_ch:
                first_hit_rank = rank_idx
                break

        if first_hit_rank == 1:
            hits_at_1 += 1
            hits_at_3 += 1
            hits_at_5 += 1
            reciprocal_ranks.append(1.0)
        elif first_hit_rank in (2, 3):
            hits_at_3 += 1
            hits_at_5 += 1
            reciprocal_ranks.append(1.0 / first_hit_rank)
        elif first_hit_rank in (4, 5):
            hits_at_5 += 1
            reciprocal_ranks.append(1.0 / first_hit_rank)
        else:
            reciprocal_ranks.append(0.0)
            failures.append({
                "question": q,
                "first_hit_rank": first_hit_rank,
                "retrieved": retrieved_chunks,
            })

    n = len(questions)
    metrics = {
        "hit@1": round(hits_at_1 / n, 4),
        "hit@3": round(hits_at_3 / n, 4),
        "hit@5": round(hits_at_5 / n, 4),
        "mrr": round(sum(reciprocal_ranks) / n, 4),
        "total": n,
        "hits_at_1_count": hits_at_1,
        "hits_at_3_count": hits_at_3,
        "hits_at_5_count": hits_at_5,
    }

    return metrics, failures


def print_failures_report(failures: List[Dict[str, Any]], title: str):
    print("\n" + "=" * 80)
    print(f"FAILURE ANALYSIS: {title} ({len(failures)} questions missed in top-5)")
    print("=" * 80)

    if not failures:
        print("  None! All questions successfully retrieved target book+chapter in top-5.")
        return

    for idx, f in enumerate(failures, 1):
        q = f["question"]
        print(f"\n[{idx}] {q['id']}: \"{q['question']}\"")
        print(f"    EXPECTED: Book={q['expected_book_code']} | Ch={q['expected_chapter_number']} ({q.get('chapter_title')}) | Class={q.get('expected_class')} | Subject={q.get('expected_subject')}")
        print("    TOP-3 RETRIEVED CHUNKS:")
        for r_idx, c in enumerate(f["retrieved"][:3], 1):
            score = c.get("score", 0.0)
            b = c.get("book_code")
            ch = c.get("chapter_number")
            ch_t = c.get("chapter_title")
            cls_v = c.get("class")
            sub_v = c.get("subject")
            snippet = c.get("text", "").replace("\n", " ")[:140]
            print(f"      {r_idx}. [Score: {score:.4f}] Book={b} Ch={ch} ({ch_t}) | Class={cls_v} Subj={sub_v}")
            print(f"         \"{snippet}...\"")


def main():
    parser = argparse.ArgumentParser(description="EduSim RAG Retrieval Evaluation")
    parser.add_argument("--yaml", type=Path, default=DEFAULT_QUESTIONS_YAML, help="Path to questions.yaml")
    args = parser.parse_args()

    yaml_file = args.yaml
    if not yaml_file.exists():
        # Fallback check
        alt_yaml = API_DIR / "tests" / "rag_eval" / "questions.yaml"
        if alt_yaml.exists():
            yaml_file = alt_yaml
        else:
            print(f"Error: {yaml_file} not found.")
            sys.exit(1)

    print("\nPreloading FAISS Vector Index V2...")
    vector_store.load_all()
    questions = load_questions(yaml_file)
    print(f"Loaded {len(questions)} evaluation questions from {yaml_file.name}.\n")

    # 1. Run Unfiltered Evaluation
    metrics_unfilt, failures_unfilt = evaluate_mode(questions, use_filter=False)

    # 2. Run Filtered Evaluation (Class + Subject)
    metrics_filt, failures_filt = evaluate_mode(questions, use_filter=True)

    # Print Metrics Summary Table
    print("=" * 65)
    print("RETRIEVAL EVALUATION RESULTS (30 QUESTIONS)")
    print("=" * 65)
    header = f"{'Metric':<18} | {'Unfiltered':<18} | {'Filtered (Class+Subject)':<22}"
    print(header)
    print("-" * 65)
    print(f"{'Hit@1':<18} | {metrics_unfilt['hit@1'] * 100:>5.1f}% ({metrics_unfilt['hits_at_1_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@1'] * 100:>5.1f}% ({metrics_filt['hits_at_1_count']}/{metrics_filt['total']})")
    print(f"{'Hit@3':<18} | {metrics_unfilt['hit@3'] * 100:>5.1f}% ({metrics_unfilt['hits_at_3_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@3'] * 100:>5.1f}% ({metrics_filt['hits_at_3_count']}/{metrics_filt['total']})")
    print(f"{'Hit@5':<18} | {metrics_unfilt['hit@5'] * 100:>5.1f}% ({metrics_unfilt['hits_at_5_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@5'] * 100:>5.1f}% ({metrics_filt['hits_at_5_count']}/{metrics_filt['total']})")
    print(f"{'MRR':<18} | {metrics_unfilt['mrr']:>7.4f}             | {metrics_filt['mrr']:>7.4f}")
    print("=" * 65)

    # Print Failures
    print_failures_report(failures_unfilt, "UNFILTERED EVALUATION")
    print_failures_report(failures_filt, "FILTERED EVALUATION")


if __name__ == "__main__":
    main()
