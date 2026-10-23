"""
EduSim Curriculum Pipeline — Text Quality Preflight
===================================================
Analyzes Unicode quality across all textbook PDFs before ingestion.
Samples up to 5 text pages per PDF to compute:
  - Share of characters in expected Unicode block for language (Telugu, Devanagari, Arabic/Urdu, Latin)
  - Private Use Area (PUA) ratio
  - Replacement character ratio
  - Latin-1 symbol ratio in non-Latin books

Classifies each PDF into:
  - ok: Clean standard Unicode text
  - legacy_encoding: 8-bit custom font encoding (PUA or ASCII/Latin-1 mapped glyphs)
  - scanned_image_only: Scanned pages with minimal or no extractable text layer
  - mixed: Garbled or corrupted Unicode mix
"""

from __future__ import annotations

import csv
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from curriculum_pipeline.pipeline_config import (
    PIPELINE_OUTPUT_ROOT,
    REPORTS_DIR,
    TEXTBOOKS_DIR,
)

logger = logging.getLogger("EduSim.preflight")
PREFLIGHT_CSV_PATH = REPORTS_DIR / "preflight.csv"


def detect_expected_language(file_name: str, rel_path: str, lang_hint: str) -> str:
    """Infers expected language: 'en', 'hi', 'te', 'ur', 'sa'."""
    lh = (lang_hint or "").lower().strip()
    if lh in ["hi", "hindi"]:
        return "hi"
    if lh in ["te", "telugu"]:
        return "te"
    if lh in ["ur", "urdu"]:
        return "ur"
    if lh in ["sa", "sanskrit"]:
        return "sa"

    lower_fn = file_name.lower()
    if "tel" in lower_fn:
        return "te"
    if "hindi" in lower_fn or re.match(r"^[a-l]h", lower_fn):
        return "hi"
    if "urdu" in lower_fn or re.match(r"^[a-l]u", lower_fn):
        return "ur"
    if "sanskrit" in lower_fn:
        return "sa"

    return "en"


def analyze_pdf_text_quality(pdf_path: Path, expected_lang: str) -> Dict[str, Any]:
    """Inspects up to 5 non-cover pages of a PDF and returns Unicode quality metrics."""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return {
            "total_pages": 0,
            "sampled_pages": 0,
            "total_chars": 0,
            "expected_script_ratio": 0.0,
            "pua_ratio": 0.0,
            "replacement_ratio": 0.0,
            "latin1_symbol_ratio": 0.0,
            "classification": "unreadable",
            "notes": "Missing or zero-byte PDF file (needs re-supply)",
        }

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {
            "total_pages": 0,
            "sampled_pages": 0,
            "total_chars": 0,
            "expected_script_ratio": 0.0,
            "pua_ratio": 0.0,
            "replacement_ratio": 0.0,
            "latin1_symbol_ratio": 0.0,
            "classification": "unreadable",
            "notes": f"MuPDF open error: {str(e)[:50]} (needs re-supply)",
        }

    total_pages = len(doc)
    if total_pages == 0:
        return {
            "total_pages": 0,
            "sampled_pages": 0,
            "total_chars": 0,
            "expected_script_ratio": 0.0,
            "pua_ratio": 0.0,
            "replacement_ratio": 0.0,
            "latin1_symbol_ratio": 0.0,
            "classification": "unreadable",
            "notes": "Zero pages in document (needs re-supply)",
        }

    # Sample up to 5 pages (e.g. pages 2, 4, 6, 8, 10 or evenly spaced)
    candidate_indices = [1, 2, 4, 7, 10] if total_pages >= 11 else list(range(min(5, total_pages)))
    sample_pages = [idx for idx in candidate_indices if idx < total_pages]
    if not sample_pages:
        sample_pages = [0]

    all_sampled_text = ""
    for pno in sample_pages:
        try:
            txt = doc[pno].get_text()
            all_sampled_text += txt
        except Exception:
            pass

    chars = [c for c in all_sampled_text if not c.isspace()]
    total_chars = len(chars)

    if total_chars < 50:
        return {
            "total_pages": total_pages,
            "sampled_pages": len(sample_pages),
            "total_chars": total_chars,
            "expected_script_ratio": 0.0,
            "pua_ratio": 0.0,
            "replacement_ratio": 0.0,
            "latin1_symbol_ratio": 0.0,
            "classification": "scanned_image_only",
            "notes": "Fewer than 50 text characters extracted across sampled pages",
        }

    # Count character categories
    devanagari_cnt = sum(1 for c in chars if 0x0900 <= ord(c) <= 0x097F)
    telugu_cnt = sum(1 for c in chars if 0x0C00 <= ord(c) <= 0x0C7F)
    arabic_urdu_cnt = sum(1 for c in chars if (0x0600 <= ord(c) <= 0x06FF or 0xFB50 <= ord(c) <= 0xFEFF))
    latin_cnt = sum(1 for c in chars if (0x0041 <= ord(c) <= 0x005A or 0x0061 <= ord(c) <= 0x007A))

    pua_cnt = sum(1 for c in chars if 0xE000 <= ord(c) <= 0xF8FF)
    replacement_cnt = sum(1 for c in chars if ord(c) == 0xFFFD or (ord(c) < 0x20 and c not in "\t\n\r"))
    latin1_symbol_cnt = sum(1 for c in chars if 0x00A0 <= ord(c) <= 0x00FF)

    # Compute ratios
    pua_ratio = round(pua_cnt / total_chars, 4)
    rep_ratio = round(replacement_cnt / total_chars, 4)
    sym_ratio = round(latin1_symbol_cnt / total_chars, 4)

    if expected_lang == "hi" or expected_lang == "sa":
        exp_script_cnt = devanagari_cnt
    elif expected_lang == "te":
        exp_script_cnt = telugu_cnt
    elif expected_lang == "ur":
        exp_script_cnt = arabic_urdu_cnt
    else:
        exp_script_cnt = latin_cnt

    exp_ratio = round(exp_script_cnt / total_chars, 4)

    # Classification logic
    classification = "ok"
    notes_list = []

    if pua_ratio > 0.15:
        classification = "legacy_encoding"
        notes_list.append(f"High Private-Use-Area glyph ratio ({pua_ratio:.1%})")
    elif expected_lang in ["hi", "te", "ur", "sa"]:
        # Non-Latin book expected to have native Unicode script
        if exp_ratio < 0.15 and (sym_ratio > 0.08 or latin_cnt / total_chars > 0.40):
            classification = "legacy_encoding"
            notes_list.append(
                f"Legacy font encoding detected: expected {expected_lang} script {exp_ratio:.1%}, "
                f"Latin/Symbol glyphs {latin_cnt / total_chars:.1%}"
            )
        elif exp_ratio < 0.30:
            classification = "mixed"
            notes_list.append(f"Low native script ratio ({exp_ratio:.1%})")
    elif rep_ratio > 0.10:
        classification = "mixed"
        notes_list.append(f"High replacement character ratio ({rep_ratio:.1%})")

    notes = "; ".join(notes_list) if notes_list else "Valid standard Unicode text"

    return {
        "total_pages": total_pages,
        "sampled_pages": len(sample_pages),
        "total_chars": total_chars,
        "expected_script_ratio": exp_ratio,
        "pua_ratio": pua_ratio,
        "replacement_ratio": rep_ratio,
        "latin1_symbol_ratio": sym_ratio,
        "classification": classification,
        "notes": notes,
    }


def run_preflight(
    inventory_csv_path: Optional[Path] = None,
    textbooks_dir: Optional[Path] = None,
    output_csv_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Runs text-quality preflight over all inventory PDFs.
    Returns (records, summary_stats).
    """
    inv_path = inventory_csv_path or (PIPELINE_OUTPUT_ROOT / "inventory" / "textbooks_inventory.csv")
    tb_dir = textbooks_dir or TEXTBOOKS_DIR
    out_csv = output_csv_path or PREFLIGHT_CSV_PATH
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not inv_path.exists():
        raise FileNotFoundError(f"Inventory CSV not found at {inv_path}")

    records: List[Dict[str, Any]] = []
    classification_counts: Dict[str, int] = {
        "ok": 0,
        "legacy_encoding": 0,
        "scanned_image_only": 0,
        "unreadable": 0,
        "mixed": 0,
    }
    by_class_lang: Dict[Tuple[str, str, str], int] = {}

    with open(inv_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    print("=" * 80)
    print("  EduSim Text Quality Preflight (954 PDFs)")
    print("=" * 80)
    print(f"  Inventory CSV: {inv_path}")
    print(f"  Total files  : {len(reader)}")
    print("-" * 80)

    for idx, row in enumerate(reader, 1):
        fn = row.get("file", "")
        rel = row.get("rel_path", "")
        board = row.get("board", "ncert")
        cls = str(row.get("class", ""))
        subj = row.get("subject", "")
        lang_hint = row.get("language", "")

        pdf_path = tb_dir / rel if rel else (tb_dir / ("ncert books" if board == "ncert" else "Text Books") / fn)
        exp_lang = detect_expected_language(fn, rel, lang_hint)

        res = analyze_pdf_text_quality(pdf_path, exp_lang)
        cls_res = res["classification"]
        classification_counts[cls_res] = classification_counts.get(cls_res, 0) + 1

        ckey = (cls, exp_lang, cls_res)
        by_class_lang[ckey] = by_class_lang.get(ckey, 0) + 1

        rec = {
            "file": fn,
            "board": board,
            "class": cls,
            "subject": subj,
            "language": exp_lang,
            "total_pages": res["total_pages"],
            "sampled_pages": res["sampled_pages"],
            "total_chars": res["total_chars"],
            "expected_script_ratio": res["expected_script_ratio"],
            "pua_ratio": res["pua_ratio"],
            "replacement_ratio": res["replacement_ratio"],
            "latin1_symbol_ratio": res["latin1_symbol_ratio"],
            "classification": cls_res,
            "notes": res["notes"],
        }
        records.append(rec)

        if idx % 100 == 0 or idx == len(reader):
            print(
                f"  [{idx:3d}/{len(reader):3d}] Preflight in progress... "
                f"(OK: {classification_counts['ok']}, Legacy: {classification_counts['legacy_encoding']}, "
                f"Unreadable: {classification_counts['unreadable']}, Scanned: {classification_counts['scanned_image_only']}, "
                f"Mixed: {classification_counts['mixed']})"
            )

    # Write preflight.csv
    cols = [
        "file", "board", "class", "subject", "language", "total_pages",
        "sampled_pages", "total_chars", "expected_script_ratio", "pua_ratio",
        "replacement_ratio", "latin1_symbol_ratio", "classification", "notes"
    ]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "total_files": len(records),
        "classifications": classification_counts,
        "by_class_lang": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in by_class_lang.items()},
    }

    print("-" * 80)
    print("Preflight Summary:")
    print(f"  Total Files Analyzed : {len(records)}")
    print(f"  Standard Unicode (ok): {classification_counts['ok']}")
    print(f"  Legacy Encoded       : {classification_counts['legacy_encoding']}")
    print(f"  Scanned Image Only   : {classification_counts['scanned_image_only']}")
    print(f"  Mixed / Corrupted    : {classification_counts['mixed']}")
    print(f"  [OK] Preflight CSV written -> {out_csv}")
    print("=" * 80)

    return records, summary
