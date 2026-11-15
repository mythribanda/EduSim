#!/usr/bin/env python3
"""
EduSim Curriculum Pipeline — Textbook Scanner
==============================================
Recursively scans EduSim_API/textbooks (or --input path) for PDF files,
classifies each as NCERT book, NCERT language book, or state-board book:

  • output/inventory/textbooks_inventory.csv  — one row per PDF
  • output/inventory/ignored_non_pdf.log      — every non-PDF file ignored
  • output/reports/scan_report.json           — machine-readable summary

NEVER modifies, moves or deletes anything inside the source textbooks folder.
ALL output is written to EduSim_API/curriculum_pipeline/output/.

Usage
-----
  python -m curriculum_pipeline.scan_textbooks
  python -m curriculum_pipeline.scan_textbooks --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ── Allow running as a module from the repo root:
_here = Path(__file__).resolve().parent
_api_root = _here.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from curriculum_pipeline.pipeline_config import (
    IGNORED_LOG,
    INVENTORY_CSV,
    INVENTORY_DIR,
    MAPPING_YAML_PATH,
    NCERT_CLASS_MAP,
    NCERT_LANG_MAP,
    NCERT_PATTERN,
    REPORTS_DIR,
    SCAN_REPORT,
    TEXTBOOKS_DIR,
    is_ncert_filename,
    parse_ncert_filename,
)

# ── Optional PDF library (PyMuPDF)
try:
    import fitz  # PyMuPDF
    _FITZ_OK = True
except ImportError:
    fitz = None
    _FITZ_OK = False

# ── Reconfigure stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# CSV schema
# ---------------------------------------------------------------------------
CSV_COLUMNS: List[str] = [
    "file",            # basename
    "rel_path",        # path relative to textbooks root
    "source_type",     # ncert_book | ncert_language_book | state_board_book | unknown
    "board",           # ncert | ssc | unknown
    "class",           # numeric grade (int) or ''
    "subject",         # resolved subject string or ''
    "language",        # en | hi | ur | te | ''
    "part",            # NCERT part number or ''
    "chapter_no",      # NCERT chapter number within part or ''
    "book_chapter_no", # continuous chapter number across parts or ''
    "pages",           # page count (requires fitz) or ''
    "size_bytes",      # file size
    "sha256",          # hex digest
    "duplicate_of",    # basename of first-seen duplicate, or ''
    "extraction_ok",   # true/false — whether text extraction worked
    "chars_per_page",  # rough chars/page from first 5 pages
    "needs_ocr",       # true/false
    "cover_line",      # first meaningful line on cover (state-board)
    "toc_l1_count",    # count of level-1 TOC entries
    "scan_note",       # free-text classification note
]


def _load_mapping_data() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads ncert subjects and ssc books mappings from mapping.yaml."""
    if not MAPPING_YAML_PATH.exists():
        return {}, {}
    try:
        with open(MAPPING_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            ncert_subs = data.get("ncert", {}).get("subjects", {})
            ssc_books = data.get("ssc", {}).get("books", {})
            return ncert_subs, ssc_books
    except Exception:
        return {}, {}


NCERT_SUBJECTS_MAP, SSC_BOOKS_MAP = _load_mapping_data()

WORD_NUMBER_MAP: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

ROMAN_CLASS_MAP: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12,
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_text_sample(path: Path, doc) -> Tuple[bool, float, bool]:
    """
    Returns (extraction_ok, chars_per_page, needs_ocr).
    Samples up to the first 5 pages.
    """
    if doc is None:
        return False, 0.0, True
    n = len(doc)
    if n == 0:
        return False, 0.0, True
    sample_pages = list(range(min(5, n)))
    texts = [doc[i].get_text() for i in sample_pages]
    total_chars = sum(len(t) for t in texts)
    cpp = round(total_chars / len(sample_pages), 1) if sample_pages else 0.0
    ok = cpp >= 40.0
    needs_ocr = cpp < 80.0
    return ok, cpp, needs_ocr


def _open_fitz(path: Path):
    """Open with fitz; return None if fitz not available or fails."""
    if not _FITZ_OK:
        return None
    try:
        if path.stat().st_size == 0:
            return None
        return fitz.open(str(path))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# State-board helpers
# ---------------------------------------------------------------------------

_SSC_SUBJECT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bPhysical\s+Sciences?\b", re.I), "physical-science"),
    (re.compile(r"\bBiological\s+Sciences?\b", re.I), "biology"),
    (re.compile(r"\bGeneral\s+Science\b", re.I), "science"),
    (re.compile(r"\bBiology\b", re.I), "biology"),
    (re.compile(r"\bPhysics\b", re.I), "physical-science"),
    (re.compile(r"\b(?:Maths|Mathematics)\b", re.I), "mathematics"),
    (re.compile(r"\bSocial\s+(?:Studies|Science)?\b", re.I), "social-science"),
    (re.compile(r"\bEVS\b|\bEnvironmental\s+Studies\b", re.I), "evs"),
    (re.compile(r"\bEnglish\b", re.I), "english"),
    (re.compile(r"\bHindi\b", re.I), "hindi"),
    (re.compile(r"\bTelugu\b|\bTel\b", re.I), "telugu"),
    (re.compile(r"\bScience\b", re.I), "science"),
]


def _resolve_ssc_subject_from_cover(doc) -> Tuple[str, str]:
    if doc is None:
        return "", ""
    for pno in range(min(3, len(doc))):
        lines = [ln.strip() for ln in doc[pno].get_text().splitlines() if ln.strip()]
        for pat, subj in _SSC_SUBJECT_PATTERNS:
            for ln in lines:
                if pat.search(ln):
                    return ln, subj
    return "", ""


def _parse_class_from_filename(filename: str) -> Optional[int]:
    base = Path(filename).stem
    # Prefix Roman numeral e.g. "VIII Biology"
    m = re.match(r"^(VIII|VII|VI|IV|IX|III|II|XI|XII|X|V|I)\b", base, re.I)
    if m:
        return ROMAN_CLASS_MAP.get(m.group(1).upper())
    # Ordinal e.g. "1st", "2nd", "3rd", "4th"
    m = re.match(r"^(\d+)(?:st|nd|rd|th)\b", base, re.I)
    if m:
        return int(m.group(1))
    # Mid-string Class Roman or Digit: e.g. "English - Class V", "Class - X", "Class 4"
    m_mid = re.search(r"\bClass\s*[-–—]?\s*(VIII|VII|VI|IV|IX|III|II|XI|XII|X|V|I|\d+)\b", base, re.I)
    if m_mid:
        val = m_mid.group(1)
        if val.upper() in ROMAN_CLASS_MAP:
            return ROMAN_CLASS_MAP[val.upper()]
        elif val.isdigit():
            return int(val)
    # Plain digit at start e.g. "5 Maths", "5em"
    m = re.match(r"^(\d+)\b", base)
    if m:
        return int(m.group(1))
    return None


def _resolve_ssc_subject_from_filename(filename: str) -> Optional[str]:
    for pat, subj in _SSC_SUBJECT_PATTERNS:
        if pat.search(filename):
            return subj
    return None


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _empty_row(file: Path, textbooks_root: Path) -> Dict[str, Any]:
    rel = file.relative_to(textbooks_root)
    return {
        "file": file.name,
        "rel_path": str(rel),
        "source_type": "unknown",
        "board": "unknown",
        "class": "",
        "subject": "",
        "language": "",
        "part": "",
        "chapter_no": "",
        "book_chapter_no": "",
        "pages": "",
        "size_bytes": file.stat().st_size if file.exists() else 0,
        "sha256": "",
        "duplicate_of": "",
        "extraction_ok": "",
        "chars_per_page": "",
        "needs_ocr": "",
        "cover_line": "",
        "toc_l1_count": "",
        "scan_note": "",
    }


def _classify_ncert(
    path: Path,
    textbooks_root: Path,
    is_language_folder: bool = False,
) -> Dict[str, Any]:
    row = _empty_row(path, textbooks_root)
    parsed = parse_ncert_filename(path.name)
    notes: List[str] = []

    if not parsed:
        row["scan_note"] = "NCERT pattern did not match (unexpected format)"
        return row

    c_letter = parsed["class_letter"]
    lang_letter = parsed["lang_letter"]
    code = parsed["subject_code"]
    cls_num = parsed["class_num"]
    lang_code = parsed["lang_code"]
    part = parsed["part"]
    ch_no = parsed["chapter_no"]

    # Classification type
    if is_language_folder or lang_code in ("hi", "ur") or code in ("at", "ga", "ks", "ml", "sr", "ve", "sa", "mr", "pr", "kl", "we", "ww"):
        row["source_type"] = "ncert_language_book" if is_language_folder else "ncert_book"
    else:
        row["source_type"] = "ncert_book"

    row["board"] = "ncert"
    row["class"] = cls_num if cls_num else ""
    row["language"] = lang_code
    row["part"] = part if part is not None else ""
    row["chapter_no"] = ch_no if ch_no is not None else ""

    # Subject lookup from mapping.yaml
    subj_info = NCERT_SUBJECTS_MAP.get(code, {})
    if subj_info:
        row["subject"] = subj_info.get("subject", code)
    else:
        row["subject"] = code
        notes.append(f"unmapped subject code '{code}'")

    if cls_num < 1 or cls_num > 12:
        notes.append(f"class={cls_num} out of range")

    # Document extraction check
    doc = _open_fitz(path)
    if doc is None:
        row["extraction_ok"] = False
        row["pages"] = 0
        notes.append("corrupted or unreadable PDF")
    else:
        row["pages"] = len(doc)
        ok, cpp, needs_ocr = _extract_text_sample(path, doc)
        row["extraction_ok"] = ok
        row["chars_per_page"] = cpp
        row["needs_ocr"] = needs_ocr
        try:
            toc = doc.get_toc()
            row["toc_l1_count"] = sum(1 for e in toc if e[0] == 1)
        except Exception:
            pass

    row["scan_note"] = "; ".join(notes) if notes else "ok"
    return row


def _classify_state_board(path: Path, textbooks_root: Path) -> Dict[str, Any]:
    row = _empty_row(path, textbooks_root)
    row["source_type"] = "state_board_book"
    row["board"] = "ssc"

    fn = path.name
    fn_lower = fn.lower()
    notes: List[str] = []

    # Check mapping.yaml for exact file metadata
    meta = SSC_BOOKS_MAP.get(fn, {})

    # Check for known noise / errata / 0-byte corrupted files
    if meta.get("flagged"):
        notes.append(meta.get("flag_reason", "flagged document"))
    elif "errata" in fn_lower:
        notes.append("errata file")

    # File size check
    if path.stat().st_size == 0:
        row["extraction_ok"] = False
        row["pages"] = 0
        notes.append("corrupted or 0-byte file")
        row["scan_note"] = "; ".join(notes)
        return row

    # Class resolution: mapping first, then filename
    cls = meta.get("class") or _parse_class_from_filename(fn)
    if cls is not None:
        row["class"] = cls
        if cls < 1 or cls > 12:
            notes.append(f"class={cls} out of range")
    else:
        notes.append("could not parse class from filename")

    # Medium / language resolution
    if meta.get("medium"):
        row["language"] = meta["medium"]
    elif re.search(r"\bEM\b", fn, re.I):
        row["language"] = "en"
    elif re.search(r"\bTM\b|\bTel\b|\bTelugu\b", fn, re.I):
        row["language"] = "te"
    elif re.search(r"\bHindi\b|\bFL Hindi\b", fn, re.I):
        row["language"] = "hi"
    else:
        row["language"] = "en"

    # Subject resolution: mapping first, then cover/filename
    if meta.get("subject"):
        row["subject"] = meta["subject"]
    else:
        fn_subj = _resolve_ssc_subject_from_filename(fn)
        row["subject"] = fn_subj or ""

    doc = _open_fitz(path)
    if doc is None:
        row["extraction_ok"] = False
        row["pages"] = 0
        notes.append("unreadable PDF")
    else:
        row["pages"] = len(doc)
        cover_line, cover_subj = _resolve_ssc_subject_from_cover(doc)
        row["cover_line"] = cover_line
        if not row["subject"] and cover_subj:
            row["subject"] = cover_subj

        ok, cpp, needs_ocr = _extract_text_sample(path, doc)
        row["extraction_ok"] = ok
        row["chars_per_page"] = cpp
        row["needs_ocr"] = needs_ocr

        try:
            toc = doc.get_toc()
            row["toc_l1_count"] = sum(1 for e in toc if e[0] == 1)
        except Exception:
            pass

    if not row["subject"]:
        notes.append("subject not resolved")

    row["scan_note"] = "; ".join(notes) if notes else "ok"
    return row


def _classify_unknown(path: Path, textbooks_root: Path) -> Dict[str, Any]:
    row = _empty_row(path, textbooks_root)
    row["source_type"] = "unknown"
    row["board"] = "unknown"
    row["scan_note"] = "unrecognized textbook folder and filename format"
    doc = _open_fitz(path)
    if doc is not None:
        row["pages"] = len(doc)
        ok, cpp, needs_ocr = _extract_text_sample(path, doc)
        row["extraction_ok"] = ok
        row["chars_per_page"] = cpp
        row["needs_ocr"] = needs_ocr
    return row


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan(
    textbooks_root: Path,
    output_inventory: Path,
    output_ignored: Path,
    output_report: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Recursively walks textbooks_root, classifies every .pdf using directory signals
    and filename conventions, detects duplicates and corruption, and writes outputs.
    """
    if not textbooks_root.exists():
        print(f"[ERROR] Textbooks folder not found: {textbooks_root}")
        sys.exit(1)

    if not textbooks_root.is_dir():
        print(f"[ERROR] Path is not a directory: {textbooks_root}")
        sys.exit(1)

    # ── Safety guard: output must NOT land inside textbooks_root
    try:
        output_inventory.relative_to(textbooks_root)
        raise RuntimeError(
            f"Output path {output_inventory} is inside the read-only textbooks "
            f"folder {textbooks_root}. Refusing to write."
        )
    except ValueError:
        pass

    print(f"\n{'='*70}")
    print("  EduSim Curriculum Pipeline — Textbook Scanner")
    print(f"{'='*70}")
    print(f"  Source (read-only): {textbooks_root}")
    print(f"  Inventory CSV     : {output_inventory}")
    print(f"  Ignored log       : {output_ignored}")
    print(f"  Scan report       : {output_report}")
    if dry_run:
        print("  *** DRY-RUN mode — no files will be written ***")
    print()

    # ── Walk and partition
    all_pdfs: List[Path] = []
    ignored: List[Tuple[str, str]] = []

    for dirpath, _dirs, filenames in os.walk(textbooks_root):
        dp = Path(dirpath)
        for fname in sorted(filenames):
            fp = dp / fname
            rel = fp.relative_to(textbooks_root)
            if fp.suffix.lower() == ".pdf":
                all_pdfs.append(fp)
            else:
                ignored.append((str(rel), fp.suffix or "(no ext)"))

    print(f"  Found {len(all_pdfs)} PDF file(s), {len(ignored)} non-PDF ignored.\n")

    if not all_pdfs:
        print("[STOP] No PDF files found. Nothing to do.")
        sys.exit(0)

    # ── Classify each PDF
    rows: List[Dict[str, Any]] = []
    sha_seen: Dict[str, str] = {}

    for pdf_path in all_pdfs:
        rel = pdf_path.relative_to(textbooks_root)
        rel_str = str(rel).replace("\\", "/").lower()

        # Classification signal precedence:
        # 1. Folder location: 'ncert books/language/' -> NCERT language books
        if "ncert books/language" in rel_str or "/language/" in rel_str:
            row = _classify_ncert(pdf_path, textbooks_root, is_language_folder=True)
        # 2. Folder location: 'ncert books/' -> NCERT main books
        elif "ncert books" in rel_str or rel_str.startswith("ncert"):
            row = _classify_ncert(pdf_path, textbooks_root, is_language_folder=False)
        # 3. Folder location: 'Text Books/' -> Telangana State Board
        elif "text books" in rel_str or "state_board" in rel_str or rel_str.startswith("text"):
            row = _classify_state_board(pdf_path, textbooks_root)
        # 4. Fallback: Filename pattern matching
        elif is_ncert_filename(pdf_path.name):
            row = _classify_ncert(pdf_path, textbooks_root, is_language_folder=False)
        elif pdf_path.name in SSC_BOOKS_MAP or _resolve_ssc_subject_from_filename(pdf_path.name):
            row = _classify_state_board(pdf_path, textbooks_root)
        else:
            row = _classify_unknown(pdf_path, textbooks_root)

        # SHA256 + duplicate detection
        try:
            digest = _sha256(pdf_path)
            row["sha256"] = digest
            if digest in sha_seen:
                row["duplicate_of"] = sha_seen[digest]
            else:
                sha_seen[digest] = pdf_path.name
        except OSError as e:
            row["sha256"] = f"ERROR: {e}"

        rows.append(row)

    # ── Counters for report
    ncert_main_count = sum(1 for r in rows if r["source_type"] == "ncert_book")
    ncert_lang_count = sum(1 for r in rows if r["source_type"] == "ncert_language_book")
    ncert_total = ncert_main_count + ncert_lang_count
    sb_count = sum(1 for r in rows if r["source_type"] == "state_board_book")
    unk_count = sum(1 for r in rows if r["source_type"] == "unknown")
    dup_count = sum(1 for r in rows if r.get("duplicate_of"))
    ocr_count = sum(1 for r in rows if r.get("needs_ocr") is True)
    corrupted_count = sum(1 for r in rows if "corrupted" in r.get("scan_note", "").lower() or r.get("extraction_ok") is False)
    errata_count = sum(1 for r in rows if "errata" in r.get("scan_note", "").lower())
    clean_ok_count = sum(1 for r in rows if r.get("scan_note") == "ok")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "textbooks_root": str(textbooks_root),
        "total_pdfs": len(all_pdfs),
        "ncert_total_books": ncert_total,
        "ncert_main_books": ncert_main_count,
        "ncert_language_books": ncert_lang_count,
        "state_board_books": sb_count,
        "unknown_files": unk_count,
        "duplicate_files": dup_count,
        "corrupted_or_unreadable_files": corrupted_count,
        "errata_files": errata_count,
        "needs_ocr": ocr_count,
        "clean_ok": clean_ok_count,
        "ignored_non_pdf": len(ignored),
        "board_breakdown": dict(Counter(r["board"] for r in rows)),
        "subject_breakdown": dict(Counter(r["subject"] for r in rows if r.get("subject"))),
        "class_breakdown": dict(
            sorted(
                Counter(r["class"] for r in rows if r.get("class") != "").items(),
                key=lambda kv: (int(kv[0]) if str(kv[0]).isdigit() else 99)
            )
        ),
    }

    # ── Write outputs
    if not dry_run:
        output_inventory.parent.mkdir(parents=True, exist_ok=True)
        with open(output_inventory, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"  ✓ Inventory written → {output_inventory}")

        output_ignored.parent.mkdir(parents=True, exist_ok=True)
        with open(output_ignored, "w", encoding="utf-8") as f:
            f.write(f"# Ignored non-PDF files — {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"# Source: {textbooks_root}\n\n")
            for rel, ext in sorted(ignored):
                f.write(f"{ext}\t{rel}\n")
        print(f"  ✓ Ignored log  written → {output_ignored}")

        output_report.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"  ✓ Scan report  written → {output_report}\n")

    # ── Terminal summary
    print(f"\n{'='*70}")
    print("  SCAN SUMMARY")
    print(f"{'='*70}")
    print(f"  Total PDFs scanned          : {len(all_pdfs)}")
    print(f"  NCERT main books            : {ncert_main_count}")
    print(f"  NCERT language books        : {ncert_lang_count}")
    print(f"  State-board (SSC) books     : {sb_count}")
    print(f"  Unknown type                : {unk_count}")
    print(f"  Corrupted / 0-byte files    : {corrupted_count}")
    print(f"  Errata files (flagged)      : {errata_count}")
    print(f"  Duplicates detected         : {dup_count}")
    print(f"  Files needing OCR           : {ocr_count}")
    print(f"  Non-PDF files ignored       : {len(ignored)}")
    print()

    if ignored:
        print("  Ignored non-PDF files:")
        for rel, ext in sorted(ignored):
            print(f"    [{ext}]  {rel}")
        print()

    print(f"{'='*70}\n")
    return summary


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan EduSim textbooks folder and produce an inventory CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        metavar="DIR",
        type=Path,
        default=TEXTBOOKS_DIR,
        help=(
            "Path to the textbooks folder to scan. "
            f"Defaults to TEXTBOOKS_DIR env var or {TEXTBOOKS_DIR}"
        ),
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        type=Path,
        default=INVENTORY_DIR,
        help=f"Directory for output files. Default: {INVENTORY_DIR}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify files and print summary but do not write any output files.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    src = args.input.resolve()
    out_dir = args.out_dir.resolve()

    scan(
        textbooks_root=src,
        output_inventory=out_dir / INVENTORY_CSV,
        output_ignored=out_dir / IGNORED_LOG,
        output_report=REPORTS_DIR / SCAN_REPORT,
        dry_run=args.dry_run,
    )
