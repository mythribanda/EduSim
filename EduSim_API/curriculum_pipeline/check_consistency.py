"""
EduSim Curriculum Pipeline — Consistency Checker
===============================================
Compares output/chunks/*.jsonl with faiss_index_v2/metadata.json and FAISS vector count.

Checks per book:
  - chunks on disk vs rows in index
  - chunk_ids missing from index
  - index ids with no chunk file on disk
  - duplicate chunk_ids (within disk files or index)
  - content_hash / text-hash mismatches between chunk files and index
  - FAISS index.ntotal == len(metadata.json)
  - Policy enforcement: no disallowed or needs_review books in chunks or index

Exits non-zero on any mismatch.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import faiss

from curriculum_pipeline.pipeline_config import API_ROOT, PIPELINE_OUTPUT_ROOT
from curriculum_pipeline.chunker import compute_content_hash

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("EduSim.consistency_checker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CHUNKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "chunks"
BOOKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "curriculum" / "books"
INDEX_V2_DIR: Path = API_ROOT / "faiss_index_v2"
INDEX_FILE: Path = INDEX_V2_DIR / "index.faiss"
METADATA_FILE: Path = INDEX_V2_DIR / "metadata.json"


def get_disallowed_book_codes(books_dir: Path = BOOKS_DIR) -> Set[str]:
    """Finds books marked needs_review or non-ok that must not be in chunks or index."""
    disallowed = set()
    for bf in books_dir.glob("*.json"):
        try:
            with open(bf, "r", encoding="utf-8") as f:
                bdata = json.load(f)
            bcode = bdata.get("book_code") or bf.stem
            st = bdata.get("extraction_status")
            tq = bdata.get("text_quality")
            if st == "needs_review" or (tq is not None and tq != "ok") or (st and st.startswith("skipped_")):
                disallowed.add(bcode)
        except Exception:
            pass
    return disallowed


def run_consistency_check(
    chunks_dir: Path = CHUNKS_DIR,
    books_dir: Path = BOOKS_DIR,
    index_file: Path = INDEX_FILE,
    metadata_file: Path = METADATA_FILE,
) -> Dict[str, Any]:
    """
    Executes full consistency audit.
    Returns audit dictionary with summary metrics, per-book details, and error lists.
    """
    errors: List[str] = []
    warnings: List[str] = []
    disallowed_books = get_disallowed_book_codes(books_dir)

    # 1. Load FAISS index
    if not index_file.exists():
        errors.append(f"FAISS index file not found: {index_file}")
        vector_count = 0
    else:
        try:
            faiss_idx = faiss.read_index(str(index_file))
            vector_count = faiss_idx.ntotal
        except Exception as e:
            errors.append(f"Failed to read FAISS index {index_file}: {e}")
            vector_count = 0

    # 2. Load Metadata
    metadata_rows: List[Dict[str, Any]] = []
    meta_by_chunk_id: Dict[str, Dict[str, Any]] = {}
    meta_book_counts: Counter = Counter()
    duplicate_index_ids: List[str] = []

    if not metadata_file.exists():
        errors.append(f"Metadata file not found: {metadata_file}")
    else:
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata_rows = json.load(f)

            for i, row in enumerate(metadata_rows):
                cid = row.get("chunk_id")
                if not cid:
                    errors.append(f"Index metadata row {i} has no chunk_id!")
                    continue
                if cid in meta_by_chunk_id:
                    duplicate_index_ids.append(cid)
                meta_by_chunk_id[cid] = row
                bcode = row.get("book_code") or "unknown"
                meta_book_counts[bcode] += 1

                # Check policy
                if bcode in disallowed_books:
                    errors.append(f"Disallowed book '{bcode}' found in index metadata (row {i}, chunk_id={cid})!")
        except Exception as e:
            errors.append(f"Failed to load metadata {metadata_file}: {e}")

    # Verify vector count == metadata rows count
    if vector_count != len(metadata_rows):
        errors.append(f"Vector count mismatch: FAISS has {vector_count} vectors but metadata.json has {len(metadata_rows)} rows!")

    if duplicate_index_ids:
        errors.append(f"Found {len(duplicate_index_ids)} duplicate chunk_ids in metadata.json: {duplicate_index_ids[:5]}")

    # 3. Load chunks on disk
    disk_chunks_by_id: Dict[str, Dict[str, Any]] = {}
    disk_book_counts: Counter = Counter()
    duplicate_disk_ids: List[str] = []
    chunk_files = sorted(list(chunks_dir.glob("*.jsonl")))

    for cf in chunk_files:
        bcode = cf.stem
        # Policy check
        if bcode in disallowed_books:
            errors.append(f"Disallowed book '{bcode}' has chunk file on disk: {cf.name}!")

        file_chunk_count = 0
        with open(cf, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line_s = line.strip()
                if not line_s:
                    continue
                try:
                    chk = json.loads(line_s)
                    cid = chk.get("chunk_id")
                    if not cid:
                        errors.append(f"{cf.name} line {line_no}: missing chunk_id!")
                        continue
                    if cid in disk_chunks_by_id:
                        duplicate_disk_ids.append(cid)
                    disk_chunks_by_id[cid] = chk
                    file_chunk_count += 1
                except Exception as e:
                    errors.append(f"{cf.name} line {line_no}: invalid JSON: {e}")

        disk_book_counts[bcode] = file_chunk_count

    if duplicate_disk_ids:
        errors.append(f"Found {len(duplicate_disk_ids)} duplicate chunk_ids on disk: {duplicate_disk_ids[:5]}")

    # 4. Cross-checks
    all_books = sorted(list(set(disk_book_counts.keys()) | set(meta_book_counts.keys())))
    book_reports: List[Dict[str, Any]] = []

    missing_from_index: List[str] = []
    orphan_index_ids: List[str] = []
    hash_mismatches: List[Dict[str, Any]] = []

    for bcode in all_books:
        disk_count = disk_book_counts.get(bcode, 0)
        idx_count = meta_book_counts.get(bcode, 0)
        book_cids_disk = {cid for cid, c in disk_chunks_by_id.items() if c.get("book_code") == bcode}
        book_cids_idx = {cid for cid, m in meta_by_chunk_id.items() if m.get("book_code") == bcode}

        b_missing = sorted(list(book_cids_disk - book_cids_idx))
        b_orphan = sorted(list(book_cids_idx - book_cids_disk))
        missing_from_index.extend(b_missing)
        orphan_index_ids.extend(b_orphan)

        # Check content_hash for matching chunk_ids
        b_hash_mismatch = 0
        common_ids = book_cids_disk & book_cids_idx
        for cid in common_ids:
            disk_chunk = disk_chunks_by_id[cid]
            idx_chunk = meta_by_chunk_id[cid]

            d_hash = disk_chunk.get("content_hash")
            i_hash = idx_chunk.get("content_hash")

            if not d_hash:
                d_hash = compute_content_hash(
                    text=disk_chunk.get("text", ""),
                    board=disk_chunk.get("board", ""),
                    class_num=disk_chunk.get("class"),
                    subject=disk_chunk.get("subject", ""),
                    book_code=disk_chunk.get("book_code", ""),
                    chapter_number=str(disk_chunk.get("chapter_number", "")),
                    page_start=disk_chunk.get("page_start", 1),
                    page_end=disk_chunk.get("page_end", 1),
                )
            if not i_hash:
                i_hash = compute_content_hash(
                    text=idx_chunk.get("text", ""),
                    board=idx_chunk.get("board", ""),
                    class_num=idx_chunk.get("class"),
                    subject=idx_chunk.get("subject", ""),
                    book_code=idx_chunk.get("book_code", ""),
                    chapter_number=str(idx_chunk.get("chapter_number", "")),
                    page_start=idx_chunk.get("page_start", 1),
                    page_end=idx_chunk.get("page_end", 1),
                )

            if d_hash != i_hash:
                b_hash_mismatch += 1
                hash_mismatches.append({
                    "chunk_id": cid,
                    "disk_hash": d_hash,
                    "index_hash": i_hash,
                    "book_code": bcode,
                })

        is_match = (disk_count == idx_count) and len(b_missing) == 0 and len(b_orphan) == 0 and b_hash_mismatch == 0
        if not is_match:
            errors.append(
                f"Book '{bcode}' mismatch: disk={disk_count}, index={idx_count}, "
                f"missing_from_idx={len(b_missing)}, orphans_in_idx={len(b_orphan)}, hash_diffs={b_hash_mismatch}"
            )

        book_reports.append({
            "book_code": bcode,
            "disk_chunks": disk_count,
            "index_rows": idx_count,
            "missing_from_index": len(b_missing),
            "orphan_in_index": len(b_orphan),
            "hash_mismatches": b_hash_mismatch,
            "status": "PASS" if is_match else "FAIL",
        })

    is_consistent = (len(errors) == 0)

    return {
        "is_consistent": is_consistent,
        "total_disk_chunks": len(disk_chunks_by_id),
        "total_index_rows": len(metadata_rows),
        "total_faiss_vectors": vector_count,
        "total_books_checked": len(all_books),
        "missing_from_index_count": len(missing_from_index),
        "orphan_in_index_count": len(orphan_index_ids),
        "hash_mismatches_count": len(hash_mismatches),
        "duplicate_disk_ids_count": len(duplicate_disk_ids),
        "duplicate_index_ids_count": len(duplicate_index_ids),
        "book_reports": book_reports,
        "errors": errors,
        "warnings": warnings,
    }


def print_consistency_table(audit: Dict[str, Any]):
    """Pretty prints the consistency report."""
    headers = ["Book Code", "Disk Chunks", "Index Rows", "Missing", "Orphans", "Hash Mismatch", "Status"]
    col_widths = [42, 12, 11, 8, 8, 14, 8]

    fmt_row = " | ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "-+-".join("-" * w for w in col_widths)

    print("\n" + "=" * len(separator))
    print("PIPELINE CONSISTENCY AUDIT REPORT")
    print("=" * len(separator))
    print(fmt_row.format(*headers))
    print(separator)

    for r in audit["book_reports"]:
        row_vals = [
            r["book_code"][:col_widths[0]],
            str(r["disk_chunks"]),
            str(r["index_rows"]),
            str(r["missing_from_index"]),
            str(r["orphan_in_index"]),
            str(r["hash_mismatches"]),
            r["status"],
        ]
        print(fmt_row.format(*row_vals))

    print(separator)
    print(f"Total Disk Chunks  : {audit['total_disk_chunks']}")
    print(f"Total Index Rows   : {audit['total_index_rows']}")
    print(f"Total FAISS Vectors: {audit['total_faiss_vectors']}")
    print(f"Overall Status     : {'ALL CONSISTENT [PASS]' if audit['is_consistent'] else 'MISMATCHES FOUND [FAIL]'}")
    print("=" * len(separator) + "\n")

    if audit["errors"]:
        print("ERRORS ENCOUNTERED:")
        for err in audit["errors"]:
            print(f"  [X] {err}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Audit consistency between chunks and FAISS index")
    args = parser.parse_args()

    audit = run_consistency_check()
    print_consistency_table(audit)

    if not audit["is_consistent"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
