#!/usr/bin/env python3
"""
EduSim Curriculum Pipeline — Textbook Scanner
==============================================
Recursively scans EduSim_API/textbooks (or --input path) for PDF files,
classifies each as NCERT chapter or state-board whole-book, writes:

  • output/inventory/textbooks_inventory.csv  — one row per PDF
  • output/inventory/ignored_non_pdf.log      — every non-PDF file ignored
  • output/reports/scan_report.json           — machine-readable summary

NEVER modifies, moves or deletes anything inside the source textbooks folder.
ALL output is written to EduSim_API/curriculum_pipeline/output/.

Usage
-----
  # Using default TEXTBOOKS_DIR (EduSim_API/textbooks):
  python -m curriculum_pipeline.scan_textbooks

  # Override via CLI:
  python -m curriculum_pipeline.scan_textbooks --input /path/to/books

  # Override via env var:
  TEXTBOOKS_DIR=/path/to/books python -m curriculum_pipeline.scan_textbooks

  # Dry-run (no files written):
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

# ── Allow running as a module from the repo root:
#    python -m curriculum_pipeline.scan_textbooks
_here = Path(__file__).resolve().parent
_api_root = _here.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from curriculum_pipeline.pipeline_config import (
    IGNORED_LOG,
    INVENTORY_CSV,
    INVENTORY_DIR,
    NCERT_CLASS_MAP,
    NCERT_LANG_MAP,
    NCERT_PATTERN,
    REPORTS_DIR,
    SCAN_REPORT,
    TEXTBOOKS_DIR,
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
    "source_type",     # ncert_chapter | state_board_book | unknown
    "board",           # ncert | ssc | unknown
    "class",           # numeric grade (int) or ''
    "subject",         # resolved subject string or ''
    "language",        # en | hi | ur | ''
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

# ---------------------------------------------------------------------------
# NCERT helpers
# ---------------------------------------------------------------------------

NCERT_WHITELIST: Dict[str, str] = {
    "sc": "science",
    "ph": "physics",
    "ch": "chemistry",
    "bo": "biology",
    "cu": "science",      # Curiosity series (classes 6-8)
    "mh": "mathematics",
    "gp": "mathematics",  # Ganita Prakash (classes 6-8)
}

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
    ok = cpp >= 60.0
    needs_ocr = cpp < 80.0
    return ok, cpp, needs_ocr


def _open_fitz(path: Path):
    """Open with fitz; return None if fitz not available or fails."""
    if not _FITZ_OK:
        return None
    try:
        return fitz.open(str(path))
    except Exception:
        return None


def _build_ncert_part_max_map(all_pdf_paths: List[Path]) -> Dict[Tuple[str, int], int]:
    """Pre-scan all valid NCERT files to find max chapter_no per (book_code, part)."""
    part_max: Dict[Tuple[str, int], int] = defaultdict(int)
    for p in all_pdf_paths:
        m = NCERT_PATTERN.match(p.name)
        if not m:
            continue
        c, lang, code, part_str, ch_str = m.groups()
        cls = NCERT_CLASS_MAP.get(c.lower(), 0)
        if 6 <= cls <= 12 and lang.lower() == "e" and code.lower() in NCERT_WHITELIST:
            if code.lower() in ("cu", "gp") and cls not in (6, 7, 8):
                continue
            book_key = f"{c.lower()}e{code.lower()}"
            part = int(part_str)
            ch_no = int(ch_str)
            if ch_no > part_max[(book_key, part)]:
                part_max[(book_key, part)] = ch_no
    return part_max


def _book_chapter_no(
    book_code: str, part: int, chapter_no: int,
    part_max_map: Dict[Tuple[str, int], int]
) -> int:
    offset = sum(part_max_map.get((book_code, p), 0) for p in range(1, part))
    return chapter_no + offset


# ---------------------------------------------------------------------------
# State-board helpers
# ---------------------------------------------------------------------------

_SSC_SUBJECT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bPhysical\s+Sciences?\b", re.I), "physical-science"),
    (re.compile(r"\bBiological\s+Sciences?\b", re.I), "biological-science"),
    (re.compile(r"\bGeneral\s+Science\b", re.I), "science"),
    (re.compile(r"\bBiology\b", re.I), "biology"),
    (re.compile(r"\b(?:Maths|Mathematics)\b", re.I), "mathematics"),
    (re.compile(r"\bPhysics\b", re.I), "physics"),
    (re.compile(r"\bScience\b", re.I), "science"),
]


def _resolve_ssc_subject_from_cover(doc) -> Tuple[str, str]:
    """
    Scan first 3 pages for subject keyword.
    Returns (cover_line, resolved_subject).
    """
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
    """
    Try Roman numeral first, then ordinal, then plain digit.
    Handles filenames like 'VIII Biology EM 2025-26.pdf',
    '9 Maths EM 2025-26.pdf', '1st class English.pdf'.
    """
    base = Path(filename).stem
    # Roman
    m = re.match(r"^(VIII|VII|VI|IV|IX|III|II|XI|XII|X|V|I)\b", base, re.I)
    if m:
        return ROMAN_CLASS_MAP.get(m.group(1).upper())
    # Ordinal  e.g. "1st", "2nd", "3rd", "4th"
    m = re.match(r"^(\d+)(?:st|nd|rd|th)\b", base, re.I)
    if m:
        return int(m.group(1))
    # Plain digit at start
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
    part_max_map: Dict[Tuple[str, int], int],
) -> Dict[str, Any]:
    row = _empty_row(path, textbooks_root)
    m = NCERT_PATTERN.match(path.name)
    if not m:
        row["scan_note"] = "NCERT pattern did not match (unexpected)"
        return row

    c_letter, lang_letter, code, part_str, ch_str = m.groups()
    cls = NCERT_CLASS_MAP.get(c_letter.lower(), 0)
    lang = NCERT_LANG_MAP.get(lang_letter.lower(), "other")
    code = code.lower()
    part = int(part_str)
    ch_no = int(ch_str)

    row["source_type"] = "ncert_chapter"
    row["board"] = "ncert"
    row["class"] = cls if cls else ""
    row["language"] = lang
    row["part"] = part
    row["chapter_no"] = ch_no

    # Notes for out-of-scope files (still catalogued)
    notes: List[str] = []
    if lang != "en":
        notes.append(f"language={lang!r} (not en)")
    if cls < 1 or cls > 12:
        notes.append(f"class={cls} out of range")
    if code not in NCERT_WHITELIST:
        notes.append(f"subject code {code!r} not whitelisted")
    elif code in ("cu", "gp") and cls not in (6, 7, 8):
        notes.append(f"code {code!r} valid only for classes 6-8, found class {cls}")
    else:
        row["subject"] = NCERT_WHITELIST[code]

    book_code = f"{c_letter.lower()}{lang_letter.lower()}{code}"
    row["book_chapter_no"] = _book_chapter_no(book_code, part, ch_no, part_max_map)

    doc = _open_fitz(path)
    if doc is not None:
        row["pages"] = len(doc)
    ok, cpp, needs_ocr = _extract_text_sample(path, doc)
    row["extraction_ok"] = ok
    row["chars_per_page"] = cpp
    row["needs_ocr"] = needs_ocr

    row["scan_note"] = "; ".join(notes) if notes else "ok"
    return row


def _classify_state_board(path: Path, textbooks_root: Path) -> Dict[str, Any]:
    row = _empty_row(path, textbooks_root)
    row["source_type"] = "state_board_book"
    row["board"] = "ssc"

    fn = path.name
    fn_lower = fn.lower()

    # Skip known noise
    notes: List[str] = []
    if fn == "5em.pdf":
        row["scan_note"] = "ambiguous filename '5em.pdf'"
        return row
    if "errata" in fn_lower:
        row["scan_note"] = "errata file"
        return row

    # Language: must be English-medium (EM)
    if re.search(r"\bEM\b", fn, re.I):
        row["language"] = "en"
    else:
        notes.append("medium not EM")

    # Class
    cls = _parse_class_from_filename(fn)
    if cls is not None:
        row["class"] = cls
        if cls < 1 or cls > 12:
            notes.append(f"class={cls} out of range")
    else:
        notes.append("could not parse class from filename")

    # Subject — filename first, then cover
    fn_subj = _resolve_ssc_subject_from_filename(fn)

    doc = _open_fitz(path)
    cover_line, cover_subj = _resolve_ssc_subject_from_cover(doc)
    row["cover_line"] = cover_line

    # Cover wins when available
    row["subject"] = cover_subj if cover_subj else (fn_subj or "")
    if not row["subject"]:
        notes.append("subject not resolved")

    if doc is not None:
        row["pages"] = len(doc)
        # TOC
        try:
            toc = doc.get_toc()
            row["toc_l1_count"] = sum(1 for e in toc if e[0] == 1)
        except Exception:
            pass

    ok, cpp, needs_ocr = _extract_text_sample(path, doc)
    row["extraction_ok"] = ok
    row["chars_per_page"] = cpp
    row["needs_ocr"] = needs_ocr

    row["scan_note"] = "; ".join(notes) if notes else "ok"
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
    Recursively walk textbooks_root, classify every .pdf, ignore everything
    else, then write the inventory CSV, the ignored log, and the JSON report.

    Returns the summary dict.
    """
    if not textbooks_root.exists():
        print(f"[ERROR] Textbooks folder not found: {textbooks_root}")
        print("  Stop — not searching elsewhere.")
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
        pass  # expected — path is outside, we're good

    print(f"\n{'='*70}")
    print(f"  EduSim Curriculum Pipeline — Textbook Scanner")
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
    ignored: List[Tuple[str, str]] = []  # (rel_path, reason)

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

    # ── Pre-build NCERT part-max map (needs all paths up front)
    part_max_map = _build_ncert_part_max_map(all_pdfs)

    # ── Classify each PDF
    rows: List[Dict[str, Any]] = []
    sha_seen: Dict[str, str] = {}        # sha256 → first filename

    for pdf_path in all_pdfs:
        if NCERT_PATTERN.match(pdf_path.name):
            row = _classify_ncert(pdf_path, textbooks_root, part_max_map)
        else:
            row = _classify_state_board(pdf_path, textbooks_root)

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
    ncert_count = sum(1 for r in rows if r["source_type"] == "ncert_chapter")
    sb_count = sum(1 for r in rows if r["source_type"] == "state_board_book")
    unk_count = sum(1 for r in rows if r["source_type"] == "unknown")
    dup_count = sum(1 for r in rows if r.get("duplicate_of"))
    ocr_count = sum(1 for r in rows if r.get("needs_ocr") is True)
    ok_count  = sum(1 for r in rows if r.get("scan_note") == "ok")

    # ── Write outputs
    if not dry_run:
        # Inventory CSV
        output_inventory.parent.mkdir(parents=True, exist_ok=True)
        with open(output_inventory, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"  ✓ Inventory written → {output_inventory}")

        # Ignored log
        output_ignored.parent.mkdir(parents=True, exist_ok=True)
        with open(output_ignored, "w", encoding="utf-8") as f:
            f.write(f"# Ignored non-PDF files — {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"# Source: {textbooks_root}\n\n")
            for rel, ext in sorted(ignored):
                f.write(f"{ext}\t{rel}\n")
        print(f"  ✓ Ignored log  written → {output_ignored}")

        # JSON report
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "textbooks_root": str(textbooks_root),
            "total_pdfs": len(all_pdfs),
            "ncert_chapter_files": ncert_count,
            "state_board_book_files": sb_count,
            "unknown_files": unk_count,
            "duplicate_files": dup_count,
            "needs_ocr": ocr_count,
            "clean_ok": ok_count,
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
        output_report.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"  ✓ Scan report  written → {output_report}\n")
    else:
        summary = {}

    # ── Terminal summary
    print(f"\n{'='*70}")
    print("  SCAN SUMMARY")
    print(f"{'='*70}")
    print(f"  Total PDFs scanned    : {len(all_pdfs)}")
    print(f"  NCERT chapter files   : {ncert_count}")
    print(f"  State-board books     : {sb_count}")
    print(f"  Unknown type          : {unk_count}")
    print(f"  Duplicates detected   : {dup_count}")
    print(f"  Files needing OCR     : {ocr_count}")
    print(f"  Non-PDF files ignored : {len(ignored)}")
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

    # Resolve paths
    src = args.input.resolve()
    out_dir = args.out_dir.resolve()

    scan(
        textbooks_root=src,
        output_inventory=out_dir / INVENTORY_CSV,
        output_ignored=out_dir / IGNORED_LOG,
        output_report=REPORTS_DIR / SCAN_REPORT,
        dry_run=args.dry_run,
    )
