"""
EduSim — Model & Chunk Size Experiment Runner
============================================
Evaluates 4 variants on 60 test questions (50 in-scope + 10 out-of-scope):
  Variant A: all-MiniLM-L6-v2 + current chunks (baseline)
  Variant B: all-MiniLM-L6-v2 + chunks re-split <=200 tokens
  Variant C: BAAI/bge-small-en-v1.5 + current chunks (query instruction prefix on queries)
  Variant D: BAAI/bge-small-en-v1.5 + chunks re-split <=300 tokens

Excludes Telugu/Hindi language books. Builds variants in faiss_index_exp_*/.
Does NOT touch production faiss_index_v2.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np
import torch
import yaml
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

# Configure stdout for utf-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EduSim.experiments")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
API_DIR = ROOT_DIR
CHUNKS_DIR = API_DIR / "curriculum_pipeline" / "output" / "chunks"
EVAL_FILE = API_DIR / "tests" / "rag_eval" / "questions_eval_v2.yaml"

EXCLUDED_BOOKS = {"ssc_4th_tel_fl_2025_26"}
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# =========================================================================
# 1. Fast Tokenizer-Guided Resplitter
# =========================================================================
import re
boundary_regex = re.compile(r'(?<=[.!?])\s+|\n\n+')

def resplit_chunk_text(tokenizer, chunk: Dict[str, Any], max_tokens: int, overlap_tokens: int, hard_cap: int) -> List[Dict[str, Any]]:
    text = chunk.get("text", "").strip()
    if not text:
        return []

    all_ids = tokenizer.encode(text, add_special_tokens=False)
    if len(all_ids) <= max_tokens:
        c = dict(chunk)
        c["token_count"] = len(all_ids)
        return [c]

    segments = [s.strip() for s in boundary_regex.split(text) if s.strip()]
    if len(segments) <= 1:
        segments = [s.strip() for s in text.split('\n') if s.strip()]
    if len(segments) <= 1:
        segments = text.split()

    seg_token_data = []
    for seg in segments:
        seg_ids = tokenizer.encode(seg, add_special_tokens=False)
        if len(seg_ids) > hard_cap:
            step = max_tokens - overlap_tokens
            for i in range(0, len(seg_ids), step):
                slice_ids = seg_ids[i : i + max_tokens]
                slice_text = tokenizer.decode(slice_ids, skip_special_tokens=True).strip()
                if slice_text:
                    seg_token_data.append((slice_text, len(slice_ids)))
        else:
            seg_token_data.append((seg, len(seg_ids)))

    chunks_out = []
    cur_segs = []
    cur_tok_count = 0
    sub_idx = 1

    for seg_text, seg_len in seg_token_data:
        if cur_tok_count + seg_len > max_tokens and cur_segs:
            combined_text = " ".join(s[0] for s in cur_segs).strip()
            comb_ids = tokenizer.encode(combined_text, add_special_tokens=False)
            while len(comb_ids) > hard_cap and len(cur_segs) > 1:
                cur_segs.pop()
                combined_text = " ".join(s[0] for s in cur_segs).strip()
                comb_ids = tokenizer.encode(combined_text, add_special_tokens=False)

            new_c = dict(chunk)
            new_c["chunk_id"] = f"{chunk['chunk_id']}_s{sub_idx}"
            new_c["text"] = combined_text
            new_c["token_count"] = len(comb_ids)
            chunks_out.append(new_c)
            sub_idx += 1

            overlap_segs = []
            overlap_tok = 0
            for s in reversed(cur_segs):
                if overlap_tok + s[1] <= overlap_tokens:
                    overlap_segs.insert(0, s)
                    overlap_tok += s[1]
                else:
                    break
            cur_segs = overlap_segs
            cur_tok_count = overlap_tok

        cur_segs.append((seg_text, seg_len))
        cur_tok_count += seg_len

    if cur_segs:
        combined_text = " ".join(s[0] for s in cur_segs).strip()
        comb_ids = tokenizer.encode(combined_text, add_special_tokens=False)
        while len(comb_ids) > hard_cap and len(cur_segs) > 1:
            cur_segs.pop()
            combined_text = " ".join(s[0] for s in cur_segs).strip()
            comb_ids = tokenizer.encode(combined_text, add_special_tokens=False)

        new_c = dict(chunk)
        new_c["chunk_id"] = f"{chunk['chunk_id']}_s{sub_idx}" if sub_idx > 1 else chunk["chunk_id"]
        new_c["text"] = combined_text
        new_c["token_count"] = len(comb_ids)
        chunks_out.append(new_c)

    return chunks_out


# =========================================================================
# 2. Index Builder
# =========================================================================
def load_base_chunks() -> List[Dict[str, Any]]:
    chunks = []
    for cf in sorted(CHUNKS_DIR.glob("*.jsonl")):
        if cf.stem in EXCLUDED_BOOKS:
            continue
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
    return chunks


def build_faiss_index(
    chunks: List[Dict[str, Any]],
    model_name: str,
    output_dir: Path,
    batch_size: int = 128,
) -> Tuple[float, int]:
    """Encodes chunks and builds a FAISS IndexFlatIP index. Returns (build_time_sec, total_vectors)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    index_file = output_dir / "index.faiss"
    meta_file = output_dir / "metadata.json"

    # If already built and valid, load and return cached time
    if index_file.exists() and meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            idx = faiss.read_index(str(index_file))
            if idx.ntotal == len(chunks) and len(meta) == len(chunks):
                logger.info(f"Index at {output_dir} already built ({idx.ntotal} vectors). Skipping re-build.")
                return 0.0, idx.ntotal
        except Exception:
            pass

    logger.info(f"Building {output_dir.name} with {len(chunks)} chunks using {model_name}...")
    t_start = time.time()

    model = SentenceTransformer(model_name, device="cpu")
    texts = [c["text"] for c in chunks]

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Save metadata with row_id
    metadata = []
    for i, c in enumerate(chunks):
        row = dict(c)
        row["row_id"] = i
        metadata.append(row)

    faiss.write_index(index, str(index_file))
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    build_time = time.time() - t_start
    logger.info(f"Built {output_dir.name} in {build_time:.2f}s ({index.ntotal} vectors).")
    return build_time, index.ntotal


# =========================================================================
# 3. Evaluation & Metrics
# =========================================================================
def evaluate_variant(
    index_dir: Path,
    model_name: str,
    query_prefix: str,
    questions: List[Dict[str, Any]],
    k: int = 5,
) -> Dict[str, Any]:
    """Evaluates an index variant across unfiltered and filtered queries."""
    index = faiss.read_index(str(index_dir / "index.faiss"))
    with open(index_dir / "metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)

    model = SentenceTransformer(model_name, device="cpu")

    # Pre-build filter indices
    by_class_subject = {}
    for row in metadata:
        cls_val = row.get("class")
        subj = (row.get("subject") or "").lower()
        key = (cls_val, subj)
        if key not in by_class_subject:
            by_class_subject[key] = []
        by_class_subject[key].append(row["row_id"])

    # Measure CPU query latency and retrieve top-k
    latencies = []
    unfiltered_results = []
    filtered_results = []

    for q in questions:
        q_text = q["question"]
        if query_prefix:
            q_text = f"{query_prefix}{q_text}"

        t0 = time.perf_counter()
        q_emb = model.encode([q_text], normalize_embeddings=True, convert_to_numpy=True)
        q_emb = np.ascontiguousarray(q_emb, dtype=np.float32)
        faiss.normalize_L2(q_emb)

        # 1. Unfiltered search (k=5)
        scores, indices = index.search(q_emb, k)
        t_elapsed = (time.perf_counter() - t0) * 1000.0  # ms
        latencies.append(t_elapsed)

        retrieved_unf = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(metadata):
                retrieved_unf.append((float(score), metadata[idx]))
        unfiltered_results.append((q, retrieved_unf))

        # 2. Filtered search
        if q.get("in_scope", True):
            exp_class = q.get("expected_class")
            exp_subj = (q.get("expected_subject") or "").lower()
            allowed_rows = by_class_subject.get((exp_class, exp_subj), [])
        else:
            allowed_rows = []

        if allowed_rows:
            # IDSelector search
            selector = faiss.IDSelectorBatch(np.array(allowed_rows, dtype=np.int64))
            params = faiss.SearchParameters(sel=selector)
            f_scores, f_indices = index.search(q_emb, min(k, len(allowed_rows)), params=params)
            retrieved_f = []
            for score, idx in zip(f_scores[0], f_indices[0]):
                if idx != -1 and idx < len(metadata):
                    retrieved_f.append((float(score), metadata[idx]))
            filtered_results.append((q, retrieved_f))
        else:
            # Fallback to unfiltered if no filter or out of scope
            filtered_results.append((q, retrieved_unf))

    avg_latency = float(np.mean(latencies))

    def compute_eval_metrics(results: List[Tuple[Dict[str, Any], List[Tuple[float, Dict[str, Any]]]]]):
        in_scope_results = [r for r in results if r[0].get("in_scope", True)]
        total = len(in_scope_results)
        if total == 0:
            return {}

        hit1 = 0
        hit3 = 0
        hit5 = 0
        rr_sum = 0.0
        passage_hit1 = 0
        passage_hit5 = 0

        for q, hits in in_scope_results:
            exp_book = q.get("expected_book_code")
            exp_ch = str(q.get("expected_chapter_number"))
            keywords = [kw.lower() for kw in q.get("answer_keywords", [])]

            found_rank = None
            for rank, (score, m) in enumerate(hits, 1):
                b = m.get("book_code")
                c = str(m.get("chapter_number"))
                if b == exp_book and c == exp_ch:
                    if found_rank is None:
                        found_rank = rank

            if found_rank == 1:
                hit1 += 1
            if found_rank is not None and found_rank <= 3:
                hit3 += 1
            if found_rank is not None and found_rank <= 5:
                hit5 += 1
            if found_rank is not None:
                rr_sum += 1.0 / found_rank

            # Passage-level hit check
            if hits:
                top1_text = hits[0][1].get("text", "").lower()
                if any(kw in top1_text for kw in keywords):
                    passage_hit1 += 1

            any_top5_kw = False
            for score, m in hits[:5]:
                txt = m.get("text", "").lower()
                if any(kw in txt for kw in keywords):
                    any_top5_kw = True
                    break
            if any_top5_kw:
                passage_hit5 += 1

        return {
            "hit1": (hit1 / total) * 100.0,
            "hit3": (hit3 / total) * 100.0,
            "hit5": (hit5 / total) * 100.0,
            "mrr": rr_sum / total,
            "passage_hit1": (passage_hit1 / total) * 100.0,
            "passage_hit5": (passage_hit5 / total) * 100.0,
        }

    # Threshold tuning on in-scope vs out-of-scope queries
    # Collect max similarity scores for all 60 queries
    in_scope_scores = []
    oos_scores = []

    for q, hits in unfiltered_results:
        top_score = hits[0][0] if hits else 0.0
        if q.get("in_scope", True):
            in_scope_scores.append(top_score)
        else:
            oos_scores.append(top_score)

    # Sweep thresholds to find the threshold with 100% (or max) OOS refusal with minimum false refusals
    best_thresh = 0.35
    best_score_diff = -999.0
    best_refusal_rate = 0.0
    best_false_refusal_rate = 100.0

    for t in np.arange(0.20, 0.85, 0.01):
        thresh = round(float(t), 2)
        oos_refused = sum(1 for s in oos_scores if s < thresh)
        in_refused = sum(1 for s in in_scope_scores if s < thresh)

        refusal_rate = (oos_refused / len(oos_scores)) * 100.0
        false_refusal_rate = (in_refused / len(in_scope_scores)) * 100.0

        # Objective: high refusal of OOS, low false refusal of in-scope
        objective = refusal_rate - (1.5 * false_refusal_rate)
        if objective > best_score_diff:
            best_score_diff = objective
            best_thresh = thresh
            best_refusal_rate = refusal_rate
            best_false_refusal_rate = false_refusal_rate

    unf_metrics = compute_eval_metrics(unfiltered_results)
    filt_metrics = compute_eval_metrics(filtered_results)

    return {
        "latency_ms": avg_latency,
        "unfiltered": unf_metrics,
        "filtered": filt_metrics,
        "tuned_threshold": best_thresh,
        "refusal_rate": best_refusal_rate,
        "false_refusal_rate": best_false_refusal_rate,
    }


# =========================================================================
# 4. Main Experiment Flow
# =========================================================================
def run_all_experiments():
    logger.info("Starting Model & Chunk Size Experiment Suite...")
    torch.set_num_threads(12)

    # 1. Load Eval Questions
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = yaml.safe_load(f)
    logger.info(f"Loaded {len(questions)} evaluation questions from {EVAL_FILE.name}.")

    # 2. Prepare Chunks
    logger.info("Loading base chunks (excluding Telugu)...")
    base_chunks = load_base_chunks()
    logger.info(f"Loaded {len(base_chunks)} base chunks.")

    minilm_tok = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    bge_tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")

    # Variant A chunks: base_chunks (hard capped at 256 by MiniLM model)
    chunks_a = base_chunks

    # Variant B chunks: re-split <=200 tokens (hard cap 256)
    logger.info("Re-splitting chunks for Variant B (<=200 tokens)...")
    chunks_b = []
    for c in base_chunks:
        chunks_b.extend(resplit_chunk_text(minilm_tok, c, max_tokens=200, overlap_tokens=20, hard_cap=256))
    logger.info(f"Variant B prepared: {len(chunks_b)} chunks.")

    # Variant C chunks: base chunks with hard cap 512
    logger.info("Re-splitting chunks for Variant C (hard cap 512 tokens)...")
    chunks_c = []
    for c in base_chunks:
        chunks_c.extend(resplit_chunk_text(bge_tok, c, max_tokens=512, overlap_tokens=30, hard_cap=512))
    logger.info(f"Variant C prepared: {len(chunks_c)} chunks.")

    # Variant D chunks: re-split <=300 tokens (hard cap 512)
    logger.info("Re-splitting chunks for Variant D (<=300 tokens)...")
    chunks_d = []
    for c in base_chunks:
        chunks_d.extend(resplit_chunk_text(bge_tok, c, max_tokens=300, overlap_tokens=30, hard_cap=512))
    logger.info(f"Variant D prepared: {len(chunks_d)} chunks.")

    variants = [
        {
            "id": "A",
            "name": "MiniLM + current chunks",
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "query_prefix": "",
            "chunks": chunks_a,
            "dir": API_DIR / "faiss_index_exp_a",
        },
        {
            "id": "B",
            "name": "MiniLM + <=200 tok chunks",
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "query_prefix": "",
            "chunks": chunks_b,
            "dir": API_DIR / "faiss_index_exp_b",
        },
        {
            "id": "C",
            "name": "BGE-small + current chunks",
            "model_name": "BAAI/bge-small-en-v1.5",
            "query_prefix": BGE_QUERY_PREFIX,
            "chunks": chunks_c,
            "dir": API_DIR / "faiss_index_exp_c",
        },
        {
            "id": "D",
            "name": "BGE-small + <=300 tok chunks",
            "model_name": "BAAI/bge-small-en-v1.5",
            "query_prefix": BGE_QUERY_PREFIX,
            "chunks": chunks_d,
            "dir": API_DIR / "faiss_index_exp_d",
        },
    ]

    results = []

    for var in variants:
        logger.info(f"\n=======================================================")
        logger.info(f"RUNNING VARIANT {var['id']}: {var['name']}")
        logger.info(f"=======================================================")

        # Build Index
        build_time, vec_count = build_faiss_index(
            chunks=var["chunks"],
            model_name=var["model_name"],
            output_dir=var["dir"],
            batch_size=128,
        )

        # Run Eval
        logger.info(f"Evaluating Variant {var['id']} on 60 questions...")
        metrics = evaluate_variant(
            index_dir=var["dir"],
            model_name=var["model_name"],
            query_prefix=var["query_prefix"],
            questions=questions,
            k=5,
        )

        record = {
            "variant": var["id"],
            "description": var["name"],
            "model": var["model_name"].split("/")[-1],
            "vectors": vec_count,
            "build_time_s": build_time,
            "latency_ms": metrics["latency_ms"],
            "tuned_threshold": metrics["tuned_threshold"],
            "refusal_rate": metrics["refusal_rate"],
            "false_refusal_rate": metrics["false_refusal_rate"],
            "unf_hit1": metrics["unfiltered"]["hit1"],
            "unf_hit3": metrics["unfiltered"]["hit3"],
            "unf_hit5": metrics["unfiltered"]["hit5"],
            "unf_mrr": metrics["unfiltered"]["mrr"],
            "unf_psg5": metrics["unfiltered"]["passage_hit5"],
            "filt_hit1": metrics["filtered"]["hit1"],
            "filt_hit3": metrics["filtered"]["hit3"],
            "filt_hit5": metrics["filtered"]["hit5"],
            "filt_mrr": metrics["filtered"]["mrr"],
            "filt_psg5": metrics["filtered"]["passage_hit5"],
        }
        results.append(record)

    # Print Consolidated Results Table
    print("\n" + "=" * 135)
    print("CONSOLIDATED MODEL & CHUNK SIZE EXPERIMENT RESULTS TABLE")
    print("=" * 135)
    header = (
        f"{'Variant':<8} | {'Model':<14} | {'Vectors':<7} | {'Build(s)':<8} | {'Lat(ms)':<7} | "
        f"{'Thresh':<6} | {'Refuse':<6} | {'F-Ref':<6} | "
        f"{'Unf H@1':<7} | {'Unf H@5':<7} | {'Unf MRR':<7} | {'Unf Psg':<7} | "
        f"{'Fil H@1':<7} | {'Fil H@5':<7} | {'Fil MRR':<7} | {'Fil Psg':<7}"
    )
    print(header)
    print("-" * 135)
    for r in results:
        line = (
            f"Var {r['variant']:<4} | {r['model']:<14} | {r['vectors']:<7} | {r['build_time_s']:<8.1f} | {r['latency_ms']:<7.1f} | "
            f"{r['tuned_threshold']:<6.2f} | {r['refusal_rate']:<5.1f}% | {r['false_refusal_rate']:<5.1f}% | "
            f"{r['unf_hit1']:<6.1f}% | {r['unf_hit5']:<6.1f}% | {r['unf_mrr']:<7.4f} | {r['unf_psg5']:<6.1f}% | "
            f"{r['filt_hit1']:<6.1f}% | {r['filt_hit5']:<6.1f}% | {r['filt_mrr']:<7.4f} | {r['filt_psg5']:<6.1f}%"
        )
        print(line)
    print("=" * 135)

    # Save summary json
    summary_path = API_DIR / "tests" / "rag_eval" / "experiments_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved full experiment results to {summary_path}")


if __name__ == "__main__":
    run_all_experiments()
