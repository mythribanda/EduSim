"""
EduSim RAG Retrieval Evaluation & Threshold Sweeper
==================================================
Evaluates retrieval quality across curriculum-grounded questions and sweeps
similarity thresholds (0.15 to 0.55) to optimize false-refusal vs out-of-scope refusal.

Computes:
  - Hit@1, Hit@3, Hit@5, and MRR (Mean Reciprocal Rank)
  - Threshold sweep:
      - Answerable questions retrieved (recall@5)
      - Out-of-syllabus questions correctly refused
      - False-refusal rate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure EduSim_API is in sys.path
CURR_DIR = Path(__file__).resolve().parent
for p in [CURR_DIR, *CURR_DIR.parents]:
    if (p / "app").is_dir():
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
        API_DIR = p
        break
else:
    API_DIR = CURR_DIR

from app.src.modules.legacy_rag.vector_loader import vector_store

DEFAULT_QUESTIONS_YAML = Path(__file__).resolve().parent / "questions_eval_v3.yaml"


def load_questions(yaml_path: Path) -> List[Dict[str, Any]]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_mode(
    questions: List[Dict[str, Any]],
    use_filter: bool = False,
    k: int = 5,
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """
    Evaluates retrieval for in-scope questions either with or without class/subject filters.
    Returns (metrics_dict, failures_list).
    """
    in_scope_questions = [q for q in questions if q.get("in_scope", True)]
    if not in_scope_questions:
        return {}, []

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    failures = []

    for q in in_scope_questions:
        q["id"]
        q_text = q["question"]
        exp_book = q.get("expected_book_code", "").strip().lower()
        exp_ch = str(q.get("expected_chapter_number", "")).strip()
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

    n = len(in_scope_questions)
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


def run_threshold_sweep(
    questions: List[Dict[str, Any]],
    min_thresh: float = 0.15,
    max_thresh: float = 0.55,
    step: float = 0.05,
    k: int = 5,
) -> Dict[str, Any]:
    """
    Sweeps thresholds from min_thresh to max_thresh (step) and reports:
      - Answerable questions retrieved (recall@5)
      - Out-of-syllabus questions correctly refused
      - False-refusal rate
    Identifies the optimal threshold keeping false-refusal < 5% and OOS refused >= 90%.
    """
    in_scope = [q for q in questions if q.get("in_scope", True)]
    out_of_scope = [q for q in questions if not q.get("in_scope", True)]

    # Pre-retrieve all question top-k chunks with min_score=0.0
    cached_runs = []
    for q in questions:
        chunks = vector_store.retrieve(
            query=q["question"],
            k=k,
            min_score=0.0,
        )
        scores = [float(c.get("score", 0.0)) for c in chunks]
        top_score = scores[0] if scores else 0.0
        tail_score = scores[-1] if len(scores) >= k else (scores[-1] if scores else 0.0)
        margin = top_score - tail_score

        exp_book = q.get("expected_book_code", "").strip().lower()
        exp_ch = str(q.get("expected_chapter_number", "")).strip()

        target_hit_score = None
        for c in chunks:
            if (
                str(c.get("book_code", "")).strip().lower() == exp_book
                and str(c.get("chapter_number", "")).strip() == exp_ch
            ):
                target_hit_score = float(c.get("score", 0.0))
                break

        cached_runs.append({
            "question": q,
            "is_in_scope": q.get("in_scope", True),
            "top_score": top_score,
            "margin": margin,
            "target_hit_score": target_hit_score,
        })

    thresholds = []
    curr = min_thresh
    while curr <= max_thresh + 1e-6:
        thresholds.append(round(curr, 2))
        curr += step

    sweep_rows = []
    chosen_threshold = None

    for t in thresholds:
        # 1. Answerable retrieved (in-scope question where target chapter hit AND chunk score >= t)
        retrieved_hits = sum(
            1 for r in cached_runs
            if r["is_in_scope"] and r["target_hit_score"] is not None and r["target_hit_score"] >= t
        )
        recall_at_5 = retrieved_hits / len(in_scope) if in_scope else 0.0

        # 2. False refusal rate (in-scope question where top chunk score < t)
        false_refusals = sum(
            1 for r in cached_runs
            if r["is_in_scope"] and r["top_score"] < t
        )
        false_refusal_rate = false_refusals / len(in_scope) if in_scope else 0.0

        # 3. Out-of-syllabus correctly refused (out-of-scope question where top chunk score < t)
        oos_refused = sum(
            1 for r in cached_runs
            if not r["is_in_scope"] and r["top_score"] < t
        )
        oos_refusal_rate = oos_refused / len(out_of_scope) if out_of_scope else 1.0

        # Optimal candidate: false_refusal_rate < 0.05 and oos_refusal_rate >= 0.90
        is_candidate = (false_refusal_rate < 0.05) and (oos_refusal_rate >= 0.90)
        if is_candidate and chosen_threshold is None:
            chosen_threshold = t

        sweep_rows.append({
            "threshold": t,
            "recall@5": recall_at_5,
            "retrieved_hits": retrieved_hits,
            "in_scope_total": len(in_scope),
            "false_refusal_rate": false_refusal_rate,
            "false_refusals": false_refusals,
            "oos_refusal_rate": oos_refusal_rate,
            "oos_refused": oos_refused,
            "oos_total": len(out_of_scope),
            "is_candidate": is_candidate,
        })

    # Print Sweep Table
    print("\n" + "=" * 110)
    print(f"RAG SIMILARITY THRESHOLD SWEEP (0.15 to 0.55) — {len(in_scope)} Answerable, {len(out_of_scope)} Out-of-Syllabus")
    print("=" * 110)
    print(f"{'Threshold':<11} | {'Answerable Retrieved (Recall@5)':<34} | {'False Refusal Rate':<22} | {'OOS Refused Rate':<20} | {'Status'}")
    print("-" * 110)
    for row in sweep_rows:
        t_str = f"{row['threshold']:.2f}"
        rec_str = f"{row['recall@5'] * 100:>5.1f}% ({row['retrieved_hits']}/{row['in_scope_total']})"
        fr_str = f"{row['false_refusal_rate'] * 100:>5.1f}% ({row['false_refusals']}/{row['in_scope_total']})"
        oos_str = f"{row['oos_refusal_rate'] * 100:>5.1f}% ({row['oos_refused']}/{row['oos_total']})"
        status = "<-- SELECTED (False Refusal < 5% & OOS Refused >= 90%)" if row["threshold"] == chosen_threshold else ""
        print(f"{t_str:<11} | {rec_str:<34} | {fr_str:<22} | {oos_str:<20} | {status}")
    print("=" * 110)

    if chosen_threshold is not None:
        print(f"\n[RECOMMENDED THRESHOLD]: {chosen_threshold:.2f}")
        print(f"  - False Refusal Rate: {next(r['false_refusal_rate'] for r in sweep_rows if r['threshold'] == chosen_threshold) * 100:.1f}% (< 5%)")
        print(f"  - OOS Refusal Rate:   {next(r['oos_refusal_rate'] for r in sweep_rows if r['threshold'] == chosen_threshold) * 100:.1f}% (>= 90%)")
        print(f"  - Answerable Recall:  {next(r['recall@5'] for r in sweep_rows if r['threshold'] == chosen_threshold) * 100:.1f}%")
    else:
        print("\n[NOTE]: No single threshold achieved both <5% false refusal and >=90% OOS refusal.")
        print("Relative margin scoring (top1 - top5 margin) is recommended.")

    return {
        "sweep_rows": sweep_rows,
        "chosen_threshold": chosen_threshold,
        "in_scope_count": len(in_scope),
        "oos_count": len(out_of_scope),
    }


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
        print(f"    EXPECTED: Book={q.get('expected_book_code')} | Ch={q.get('expected_chapter_number')} ({q.get('chapter_title')}) | Class={q.get('expected_class')} | Subject={q.get('expected_subject')}")
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
            print(f'         "{snippet}..."')


def main():
    parser = argparse.ArgumentParser(description="EduSim RAG Retrieval Evaluation & Threshold Sweeper")
    parser.add_argument("--yaml", type=Path, default=None, help="Path to evaluation questions YAML")
    parser.add_argument("--sweep", action="store_true", help="Force running threshold sweep (0.15 to 0.55)")
    parser.add_argument("--min-thresh", type=float, default=0.15, help="Min sweep threshold (default: 0.15)")
    parser.add_argument("--max-thresh", type=float, default=0.55, help="Max sweep threshold (default: 0.55)")
    parser.add_argument("--step", type=float, default=0.05, help="Sweep step size (default: 0.05)")
    args = parser.parse_args()

    # Determine yaml path
    yaml_file = args.yaml
    if yaml_file is None:
        if DEFAULT_QUESTIONS_YAML.exists():
            yaml_file = DEFAULT_QUESTIONS_YAML
        else:
            candidates = [
                API_DIR / "tests" / "rag_eval" / "questions_eval_v3.yaml",
                API_DIR / "tests" / "rag_eval" / "questions_eval_v2.yaml",
                API_DIR / "tests" / "rag_eval" / "questions.yaml",
            ]
            for c in candidates:
                if c.exists():
                    yaml_file = c
                    break

    if not yaml_file or not yaml_file.exists():
        print("Error: questions file not found.")
        sys.exit(1)

    print("\nPreloading FAISS Vector Index V2...")
    vector_store.load_all()
    questions = load_questions(yaml_file)
    print(f"Loaded {len(questions)} evaluation questions from {yaml_file.name}.\n")

    in_scope_count = sum(1 for q in questions if q.get("in_scope", True))
    oos_count = sum(1 for q in questions if not q.get("in_scope", True))

    # 1. Standard In-Scope Evaluation (Hit@1, Hit@3, Hit@5, MRR)
    if in_scope_count > 0:
        metrics_unfilt, failures_unfilt = evaluate_mode(questions, use_filter=False)
        metrics_filt, failures_filt = evaluate_mode(questions, use_filter=True)

        print("=" * 65)
        print(f"RETRIEVAL EVALUATION RESULTS ({in_scope_count} IN-SCOPE QUESTIONS)")
        print("=" * 65)
        header = f"{'Metric':<18} | {'Unfiltered':<18} | {'Filtered (Class+Subject)':<22}"
        print(header)
        print("-" * 65)
        print(f"{'Hit@1':<18} | {metrics_unfilt['hit@1'] * 100:>5.1f}% ({metrics_unfilt['hits_at_1_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@1'] * 100:>5.1f}% ({metrics_filt['hits_at_1_count']}/{metrics_filt['total']})")
        print(f"{'Hit@3':<18} | {metrics_unfilt['hit@3'] * 100:>5.1f}% ({metrics_unfilt['hits_at_3_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@3'] * 100:>5.1f}% ({metrics_filt['hits_at_3_count']}/{metrics_filt['total']})")
        print(f"{'Hit@5':<18} | {metrics_unfilt['hit@5'] * 100:>5.1f}% ({metrics_unfilt['hits_at_5_count']}/{metrics_unfilt['total']})     | {metrics_filt['hit@5'] * 100:>5.1f}% ({metrics_filt['hits_at_5_count']}/{metrics_filt['total']})")
        print(f"{'MRR':<18} | {metrics_unfilt['mrr']:>7.4f}             | {metrics_filt['mrr']:>7.4f}")
        print("=" * 65)

    # 2. Run Threshold Sweep (if out-of-scope questions exist or --sweep is explicitly requested)
    if oos_count > 0 or args.sweep:
        run_threshold_sweep(
            questions=questions,
            min_thresh=args.min_thresh,
            max_thresh=args.max_thresh,
            step=args.step,
        )


if __name__ == "__main__":
    main()
