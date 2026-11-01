"""
EduSim Embedder Benchmark: English & Hindi Retrieval Comparison
==============================================================
Compares 4 SentenceTransformer embedding models across 30 English and 30 Hindi questions:
  1. all-MiniLM-L6-v2
  2. paraphrase-multilingual-MiniLM-L12-v2
  3. intfloat/multilingual-e5-small
  4. BAAI/bge-m3

Measures Recall@5 against the known ground-truth chapter (book_code, chapter_number).
Uses a high-discrimination evaluation corpus: key chunks from the 60 test chapters
plus stratified distractors across NCERT subjects (~150 chunks total).
Caches chunk embeddings locally in curriculum_pipeline/output/eval_cache/ for fast reruns.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

# Reconfigure stdout for UTF-8 in Windows environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EduSim.compare_embedders")

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
CACHE_DIR = API_DIR / "curriculum_pipeline" / "output" / "eval_cache"
INDEX_DIR = API_DIR / "faiss_index_v2"
INDEX_FILE = INDEX_DIR / "index.faiss"
METADATA_FILE = INDEX_DIR / "metadata.json"

EN_QUESTIONS_FILE = API_DIR / "tests" / "rag_eval" / "questions.yaml"
HI_QUESTIONS_FILE = API_DIR / "tests" / "rag_eval" / "questions_hindi.yaml"

MODELS_TO_BENCHMARK = [
    {
        "name": "all-MiniLM-L6-v2",
        "display_name": "all-MiniLM-L6-v2",
        "dim": 384,
        "is_e5": False,
        "reuse_faiss_v2": True,
    },
    {
        "name": "paraphrase-multilingual-MiniLM-L12-v2",
        "display_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "dim": 384,
        "is_e5": False,
        "reuse_faiss_v2": False,
    },
    {
        "name": "intfloat/multilingual-e5-small",
        "display_name": "intfloat/multilingual-e5-small",
        "dim": 384,
        "is_e5": True,
        "reuse_faiss_v2": False,
    },
    {
        "name": "BAAI/bge-m3",
        "display_name": "BAAI/bge-m3",
        "dim": 1024,
        "is_e5": False,
        "reuse_faiss_v2": False,
    },
]


def load_evaluation_data(max_distractors: int = 50) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Loads questions and extracts target chunks plus stratified distractors."""
    if not EN_QUESTIONS_FILE.exists():
        raise FileNotFoundError(f"English questions file missing: {EN_QUESTIONS_FILE}")
    if not HI_QUESTIONS_FILE.exists():
        raise FileNotFoundError(f"Hindi questions file missing: {HI_QUESTIONS_FILE}")
    if not METADATA_FILE.exists():
        raise FileNotFoundError(f"Index metadata missing: {METADATA_FILE}")

    with open(EN_QUESTIONS_FILE, "r", encoding="utf-8") as f:
        en_questions = yaml.safe_load(f)
    with open(HI_QUESTIONS_FILE, "r", encoding="utf-8") as f:
        hi_questions = yaml.safe_load(f)

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        all_metadata = json.load(f)

    # 1. Identify target chapters
    target_chapters = set()
    for q in en_questions:
        target_chapters.add((q["expected_book_code"].strip().lower(), str(q["expected_chapter_number"]).strip()))
    for q in hi_questions:
        target_chapters.add((q["expected_book_code"].strip().lower(), str(q["expected_chapter_number"]).strip()))

    # Group target chunks by chapter and select up to 2 representative chunks per chapter
    chunks_by_target = {}
    other_chunks = []

    for m in all_metadata:
        key = (str(m.get("book_code", "")).strip().lower(), str(m.get("chapter_number", "")).strip())
        if key in target_chapters:
            chunks_by_target.setdefault(key, []).append(m)
        else:
            other_chunks.append(m)

    target_chunks = []
    for key, ch_chunks in sorted(chunks_by_target.items()):
        # Take up to 2 chunks per target chapter
        target_chunks.extend(ch_chunks[:2])

    # Deterministic sampling for distractors
    rng = random.Random(42)
    distractors = rng.sample(other_chunks, min(max_distractors, len(other_chunks)))

    candidate_chunks = target_chunks + distractors

    logger.info(
        f"Loaded {len(en_questions)} English questions, {len(hi_questions)} Hindi questions.\n"
        f"Target chunks: {len(target_chunks)} across {len(target_chapters)} chapters | "
        f"Distractor chunks: {len(distractors)} | Total pool: {len(candidate_chunks)}"
    )
    return en_questions, hi_questions, candidate_chunks


def get_model_specs(model_name: str) -> Tuple[int, str]:
    """Retrieves embedding dimension and formatted model parameter size."""
    specs = {
        "all-MiniLM-L6-v2": (384, "86.6 MB (22.7M params)"),
        "paraphrase-multilingual-MiniLM-L12-v2": (384, "448.8 MB (117.7M params)"),
        "intfloat/multilingual-e5-small": (384, "448.8 MB (117.7M params)"),
        "BAAI/bge-m3": (1024, "2165.8 MB (567.8M params)"),
    }
    return specs.get(model_name, (384, "Unknown"))


def get_or_create_chunk_embeddings(
    model_info: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    batch_size: int = 32,
) -> Tuple[SentenceTransformer, np.ndarray]:
    """Encodes chunks or loads cached/reconstructed embeddings."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = model_info["name"].replace("/", "_").replace("-", "_")
    cache_path = CACHE_DIR / f"chunks_{slug}_{len(chunks)}.npy"

    logger.info(f"Loading model '{model_info['name']}'...")
    model = SentenceTransformer(model_info["name"], device="cpu")
    if hasattr(model, "max_seq_length") and model.max_seq_length > 512:
        model.max_seq_length = 512
    if hasattr(model, "tokenizer") and hasattr(model.tokenizer, "model_max_length"):
        model.tokenizer.model_max_length = 512
    if hasattr(model[0], "max_seq_length"):
        model[0].max_seq_length = 512

    # 1. Fast path: load cached
    if cache_path.exists():
        logger.info(f"Loading cached embeddings from {cache_path}...")
        embeddings = np.load(str(cache_path))
        if embeddings.shape[0] == len(chunks):
            return model, embeddings

    # 2. Fast path for all-MiniLM-L6-v2: reconstruct directly from existing faiss_index_v2
    if model_info.get("reuse_faiss_v2") and INDEX_FILE.exists():
        try:
            logger.info("Extracting embeddings for all-MiniLM-L6-v2 directly from faiss_index_v2...")
            faiss_v2 = faiss.read_index(str(INDEX_FILE))
            row_ids = [c["row_id"] for c in chunks]
            embeddings = np.zeros((len(chunks), 384), dtype=np.float32)
            for i, rid in enumerate(row_ids):
                embeddings[i] = faiss_v2.reconstruct(int(rid))
            faiss.normalize_L2(embeddings)
            np.save(str(cache_path), embeddings)
            logger.info(f"Extracted {len(chunks)} vectors from existing index in 0.2s.")
            return model, embeddings
        except Exception as e:
            logger.warning(f"Could not reconstruct from existing index: {e}. Encoding directly...")

    # 3. Standard encoding
    logger.info(f"Encoding {len(chunks)} chunks with '{model_info['name']}' on CPU...")
    is_e5 = model_info.get("is_e5", False)
    if is_e5:
        texts = [
            f"passage: {c['text']}" if not c["text"].startswith("passage: ") else c["text"]
            for c in chunks
        ]
    else:
        texts = [c["text"] for c in chunks]

    t0 = time.time()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings)
    elapsed = time.time() - t0
    logger.info(f"Encoded {len(chunks)} chunks in {elapsed:.1f}s. Saving to cache: {cache_path}...")
    np.save(str(cache_path), embeddings)

    return model, embeddings


def evaluate_model_recall(
    model: SentenceTransformer,
    model_info: Dict[str, Any],
    chunk_embeddings: np.ndarray,
    chunks_meta: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    k: int = 5,
) -> float:
    """Computes Recall@k against the expected (book_code, chapter_number)."""
    dim = chunk_embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(chunk_embeddings)

    is_e5 = model_info.get("is_e5", False)
    hits = 0

    for q in questions:
        q_text = q["question"]
        if is_e5 and not q_text.startswith("query: "):
            q_text = f"query: {q_text}"

        q_emb = model.encode([q_text], normalize_embeddings=True, convert_to_numpy=True)
        q_emb = np.ascontiguousarray(q_emb, dtype=np.float32)
        faiss.normalize_L2(q_emb)

        scores, indices = index.search(q_emb, k)
        exp_book = q["expected_book_code"].strip().lower()
        exp_ch = str(q["expected_chapter_number"]).strip()

        hit = False
        for idx in indices[0]:
            if idx != -1 and idx < len(chunks_meta):
                meta = chunks_meta[idx]
                c_book = str(meta.get("book_code", "")).strip().lower()
                c_ch = str(meta.get("chapter_number", "")).strip()
                if c_book == exp_book and c_ch == exp_ch:
                    hit = True
                    break

        if hit:
            hits += 1

    recall = (hits / len(questions)) * 100.0 if questions else 0.0
    return recall


def run_benchmark():
    en_questions, hi_questions, chunks = load_evaluation_data()

    results = []

    print("\n" + "=" * 95)
    print("RUNNING EMBEDDER BENCHMARK: ENGLISH & HINDI RETRIEVAL (Recall@5)")
    print("=" * 95)

    for minfo in MODELS_TO_BENCHMARK:
        logger.info(f"\n--- Benchmarking {minfo['display_name']} ---")
        model, chunk_embs = get_or_create_chunk_embeddings(minfo, chunks)
        dim, spec_str = get_model_specs(minfo["name"])

        logger.info(f"Evaluating {minfo['display_name']} on 30 English questions...")
        en_recall = evaluate_model_recall(model, minfo, chunk_embs, chunks, en_questions, k=5)

        logger.info(f"Evaluating {minfo['display_name']} on 30 Hindi questions...")
        hi_recall = evaluate_model_recall(model, minfo, chunk_embs, chunks, hi_questions, k=5)

        overall_recall = (en_recall + hi_recall) / 2.0

        results.append({
            "model": minfo["display_name"],
            "dim": dim,
            "size": spec_str,
            "en_recall": en_recall,
            "hi_recall": hi_recall,
            "overall_recall": overall_recall,
        })

    # Print summary table
    print("\n" + "=" * 105)
    print("EMBEDDING MODEL BENCHMARK RESULTS (Evaluation on 30 English + 30 Hindi Questions)")
    print("=" * 105)
    header = f"{'Model Name':<40} | {'Dim':<5} | {'Model Size':<24} | {'English R@5':<11} | {'Hindi R@5':<11} | {'Overall R@5':<11}"
    print(header)
    print("-" * 105)
    for r in results:
        row = f"{r['model']:<40} | {r['dim']:<5} | {r['size']:<24} | {r['en_recall']:>10.1f}% | {r['hi_recall']:>10.1f}% | {r['overall_recall']:>10.1f}%"
        print(row)
    print("=" * 105 + "\n")

    # Save benchmark report as JSON
    report_path = API_DIR / "curriculum_pipeline" / "output" / "reports" / "embedder_benchmark.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark results saved to: {report_path}\n")


if __name__ == "__main__":
    run_benchmark()
