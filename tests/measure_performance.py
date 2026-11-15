"""
tests/measure_performance.py
============================
Benchmarks empirical performance of the EduSim RAG & AI Tutor components:
  1. Embedding generation throughput and latency (SentenceTransformers all-MiniLM-L6-v2)
  2. Dense vector FAISS retrieval latency (filtered vs unfiltered)
  3. Retrieval Precision@K and Recall@K over grounded curriculum benchmarks
  4. End-to-end timing metrics
"""

import time
import sys
from pathlib import Path
import yaml
import numpy as np

# Add API to path
REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
sys.path.insert(0, str(API_DIR))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.legacy_rag.embedder import get_embeddings


def benchmark_all():
    print("=" * 70)
    print("EDUSIM RAG & AI TUTOR PERFORMANCE BENCHMARK")
    print("=" * 70)

    # 1. Embedder Benchmark
    print("\n--- 1. Embedding Model Performance ---")
    embedder = get_embeddings()
    sample_texts = [
        "Newton's second law of motion states that force equals mass times acceleration.",
        "A simple pendulum consists of a mass attached to a string of length L.",
        "The electric current in a conductor is directly proportional to voltage.",
        "Photosynthesis is the process by which green plants make food using sunlight.",
    ]
    t0 = time.perf_counter()
    _ = embedder.encode(sample_texts, convert_to_numpy=True)
    t_batch = time.perf_counter() - t0
    per_item_ms = (t_batch / len(sample_texts)) * 1000
    print(f"Model: {getattr(embedder, 'model_name', 'all-MiniLM-L6-v2')}")
    print(f"Dimension: {getattr(embedder, 'dimension', 384)}")
    print(f"Batch encoding ({len(sample_texts)} texts): {t_batch * 1000:.2f} ms ({per_item_ms:.2f} ms/item)")

    # 2. FAISS Preload & Metadata Metrics
    print("\n--- 2. FAISS Vector Store Metrics ---")
    t0 = time.perf_counter()
    vector_store.load_all()
    t_load = time.perf_counter() - t0
    v_count = vector_store.vector_count
    subj_count = vector_store.subject_count
    print(f"FAISS index vectors loaded: {v_count}")
    print(f"Subjects covered: {subj_count}")
    print(f"Index load time (if not cached): {t_load * 1000:.2f} ms")

    # 3. Retrieval Latency Benchmark
    print("\n--- 3. Semantic Retrieval Latency (k=5) ---")
    queries = [
        ("What is Newton's second law?", "physics", 9),
        ("How does a simple pendulum swing?", "physics", 11),
        ("Explain the chemical reaction of photosynthesis", "biology", 10),
        ("What is the formula for area of a triangle?", "mathematics", 9),
        ("What causes gravitational pull?", "physics", 9),
        ("Explain electric current and resistance", "physics", 10),
    ]

    latencies_unfiltered = []
    for q, _, _ in queries:
        t_start = time.perf_counter()
        _ = vector_store.retrieve(query=q, k=5, min_score=0.0)
        latencies_unfiltered.append((time.perf_counter() - t_start) * 1000)

    latencies_filtered = []
    for q, subj, cls_n in queries:
        t_start = time.perf_counter()
        _ = vector_store.retrieve(query=q, k=5, subject=subj, class_num=cls_n, min_score=0.0)
        latencies_filtered.append((time.perf_counter() - t_start) * 1000)

    avg_unfilt = np.mean(latencies_unfiltered)
    p95_unfilt = np.percentile(latencies_unfiltered, 95)
    avg_filt = np.mean(latencies_filtered)
    p95_filt = np.percentile(latencies_filtered, 95)
    print(f"Unfiltered Retrieval: Mean = {avg_unfilt:.2f} ms | P95 = {p95_unfilt:.2f} ms")
    print(f"Filtered (Class+Subject): Mean = {avg_filt:.2f} ms | P95 = {p95_filt:.2f} ms")

    # 4. Precision@K and Recall@K on questions_eval_v3.yaml
    print("\n--- 4. Quality Evaluation: Precision@K & Recall@K (questions_eval_v3.yaml) ---")
    q_file = Path("tests/rag_eval/questions_eval_v3.yaml")
    if q_file.exists():
        with open(q_file, "r", encoding="utf-8") as f:
            q_data = yaml.safe_load(f)
        in_scope = [q for q in q_data if q.get("in_scope", True)]

        hits_at_1 = 0
        hits_at_5 = 0
        precisions_at_5 = []

        for q in in_scope:
            q_text = q["question"]
            exp_book = q.get("expected_book_code", "").strip().lower()
            exp_ch = str(q.get("expected_chapter_number", "")).strip()
            exp_cls = q.get("expected_class")
            exp_subj = q.get("expected_subject")

            chunks = vector_store.retrieve(
                query=q_text,
                k=5,
                subject=exp_subj,
                class_num=exp_cls,
                min_score=0.0,
            )

            target_hits = sum(
                1 for c in chunks
                if str(c.get("book_code", "")).strip().lower() == exp_book
                and str(c.get("chapter_number", "")).strip() == exp_ch
            )

            if chunks and str(chunks[0].get("book_code", "")).strip().lower() == exp_book and str(chunks[0].get("chapter_number", "")).strip() == exp_ch:
                hits_at_1 += 1
            if target_hits > 0:
                hits_at_5 += 1
            precisions_at_5.append(target_hits / 5.0)

        n = len(in_scope)
        recall_at_1 = hits_at_1 / n
        recall_at_5 = hits_at_5 / n
        mean_p5 = np.mean(precisions_at_5)
        print(f"Total Evaluated Questions: {n}")
        print(f"Recall@1 (Hit@1): {recall_at_1 * 100:.1f}% ({hits_at_1}/{n})")
        print(f"Recall@5 (Hit@5): {recall_at_5 * 100:.1f}% ({hits_at_5}/{n})")
        print(f"Mean Precision@5: {mean_p5 * 100:.1f}%")

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    benchmark_all()
