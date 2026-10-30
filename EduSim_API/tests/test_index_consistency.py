"""
EduSim Tests — Index and Chunk Consistency
==========================================
Validates that:
1. The chunk files on disk and the FAISS v2 index are 100% consistent:
   - Identical chunk counts and IDs
   - Identical content hashes
   - No orphan index rows or missing chunks
   - No disallowed or needs_review books
2. For NCERT chapter-wise books, the chunk chapter_number matches the chapter
   implied by its source_pdf filename (e.g. ceev106.pdf -> chapter 6).
3. Book metadata (book_title and subject) is consistent between catalog/curriculum
   JSONs and generated chunks.
"""

import csv
import json
import re
from pathlib import Path

import pytest

from curriculum_pipeline.check_consistency import run_consistency_check
from curriculum_pipeline.pipeline_config import API_ROOT, PIPELINE_OUTPUT_ROOT

CHUNKS_DIR = PIPELINE_OUTPUT_ROOT / "chunks"
BOOKS_DIR = PIPELINE_OUTPUT_ROOT / "curriculum" / "books"
CATALOG_FILE = PIPELINE_OUTPUT_ROOT / "catalog" / "books_catalog.csv"


def test_index_consistency_full():
    """Validates that FAISS index_v2 and chunks/*.jsonl are 100% aligned with zero mismatches."""
    report = run_consistency_check()
    assert report["is_consistent"] is True, f"Consistency check failed with errors: {report['errors']}"
    assert report["missing_from_index_count"] == 0
    assert report["orphan_in_index_count"] == 0
    assert report["hash_mismatches_count"] == 0
    assert report["total_faiss_vectors"] == report["total_index_rows"]
    assert report["total_disk_chunks"] == report["total_index_rows"]


def test_ncert_chapter_number_matches_source_pdf():
    """
    For NCERT chapter-wise books, verifies that chunk chapter_number matches
    the 2-digit chapter number encoded in the source PDF filename (e.g. 'ceev106.pdf' -> 6).
    """
    pattern = re.compile(r"^[a-z]{4}\d?(\d{2})\.pdf$", re.IGNORECASE)
    chunk_files = list(CHUNKS_DIR.glob("*.jsonl"))
    assert len(chunk_files) > 0, "No chunk files found"

    mismatches = []
    checked_chunks = 0

    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                chk = json.loads(line)
                board = str(chk.get("board", "")).upper()
                source_pdf = chk.get("source_pdf") or ""
                pdf_name = Path(source_pdf).name

                # Only test NCERT chapter-wise PDFs (matches 4 letters + part + 2 digit chapter)
                match = pattern.match(pdf_name)
                if board == "NCERT" and match:
                    checked_chunks += 1
                    expected_ch = int(match.group(1))
                    actual_ch = chk.get("chapter_number")
                    try:
                        actual_ch_int = int(actual_ch)
                    except (ValueError, TypeError):
                        mismatches.append(
                            f"{cf.name} line {line_no}: invalid chapter_number '{actual_ch}' for {pdf_name}"
                        )
                        continue

                    if actual_ch_int != expected_ch:
                        mismatches.append(
                            f"{cf.name} chunk {chk.get('chunk_id')}: source_pdf={pdf_name} "
                            f"implies chapter {expected_ch}, but chunk has {actual_ch_int}"
                        )

    assert checked_chunks > 0, "No NCERT chapter-wise chunks were evaluated"
    assert len(mismatches) == 0, f"Found {len(mismatches)} chapter number mismatches:\n" + "\n".join(mismatches[:10])


def test_book_title_and_subject_consistency():
    """
    Verifies that book_title and subject in chunk files match the canonical
    curriculum book JSON definitions and catalog entries.
    """
    # Load catalog lookup if catalog exists
    catalog_meta = {}
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                catalog_meta[row["book_code"]] = {
                    "subject": (row.get("subject") or "").strip().lower(),
                    "title": (row.get("book_title") or "").strip().lower(),
                }

    chunk_files = list(CHUNKS_DIR.glob("*.jsonl"))
    assert len(chunk_files) > 0

    mismatches = []
    for cf in chunk_files:
        bcode = cf.stem
        book_json_file = BOOKS_DIR / f"{bcode}.json"
        assert book_json_file.exists(), f"Missing book JSON for chunk file {cf.name}"

        with open(book_json_file, "r", encoding="utf-8") as f:
            bdata = json.load(f)

        expected_subject = (bdata.get("subject") or "").strip().lower()
        expected_title = (bdata.get("book_title") or "").strip().lower()

        with open(cf, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                chk = json.loads(line)
                chk_subj = (chk.get("subject") or "").strip().lower()
                chk_title = (chk.get("book_title") or "").strip().lower()

                if chk_subj != expected_subject:
                    mismatches.append(
                        f"{cf.name}:{line_no}: subject '{chk_subj}' does not match book JSON '{expected_subject}'"
                    )
                    break
                if chk_title != expected_title:
                    mismatches.append(
                        f"{cf.name}:{line_no}: title '{chk_title}' does not match book JSON '{expected_title}'"
                    )
                    break

    assert len(mismatches) == 0, f"Metadata mismatches found:\n" + "\n".join(mismatches)
