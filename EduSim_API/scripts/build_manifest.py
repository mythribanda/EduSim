#!/usr/bin/env python3
"""
Phase 1 — Build PDF Manifest
=============================
Scans all PDFs in textbooks/ and produces:
  data/manifest.json             — fully resolved entries (one per PDF)
  data/manifest_unresolved.json  — entries that could not be confidently classified

Entry schema:
  file_path       str   relative to EduSim_API/
  sha256          str
  page_count      int
  board           "NCERT" | "SSC"
  class_num       int | null
  subject         str | null
  book_title      str | null   (NCERT: series name; SSC: cover page title)
  book_code       str | null   (NCERT: e.g. "keph1"; SSC: null)
  chapter_number  int | null   (NCERT: chapter within volume; SSC: null — whole book)
  chapter_title   str | null   (NCERT: extracted from PDF text; SSC: null)
  medium          "English" | "Hindi" | "Urdu" | "Sanskrit" | "Unknown"
  volume          int | null   (NCERT: part/volume number, e.g. 1 or 2)
  language        "English" | "Hindi" | "Telugu" | "Urdu" | "Mixed" | "Unknown"
  text_extractable  bool
  needs_ocr       bool         True = skip in Phase 2-3; handled in separate OCR pass

Run from EduSim_API/:
    python scripts/build_manifest.py [--textbooks-dir textbooks] [--output-dir data]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("build_manifest")

# ─────────────────────────────────────────────────────────────────────────────
# NCERT Decoding Tables
# ─────────────────────────────────────────────────────────────────────────────

NCERT_CLASS_LETTER: Dict[str, int] = {
    "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6,
    "g": 7, "h": 8, "i": 9, "j": 10, "k": 11, "l": 12,
}

NCERT_MEDIUM_LETTER: Dict[str, str] = {
    "e": "English", "h": "Hindi", "u": "Urdu", "s": "Sanskrit",
}

# 2-char subject codes derived from:
#   analyze_ncert.py NCERT_SUBJECT_MAP  +  empirical prefix analysis of the corpus
NCERT_SUBJECT_MAP: Dict[str, str] = {
    "ac": "Accountancy",
    "at": "Hindi",              # Aroh / Antra (class 11-12)
    "be": "Economics",
    "bo": "Biology",
    "bs": "Business_Studies",
    "bt": "Biotechnology",
    "ch": "Chemistry",
    "cs": "Computer_Science",
    "cu": "Science",            # Curiosity (class 3-5 science)
    "eb": "Economics",
    "ec": "Economics",
    "ee": "Environmental_Studies",
    "es": "Social_Science",     # Exploring Society / EVS
    "ev": "Environmental_Studies",
    "ga": "Hindi",              # Ganga / Hindi reader
    "go": "Geography",
    "gp": "Mathematics",        # Ganita Prakash (class 6+)
    "gy": "Geography",
    "he": "Health_and_Physical_Education",
    "hs": "History",
    "hv": "Hindi",              # Hindi Vasant variant
    "jm": "Mathematics",        # Joyful Mathematics (class 1-5)
    "kl": "English",            # Kaleidoscope / Kalika (class 12)
    "ks": "Hindi",              # Kshitij (class 9-10)
    "mh": "Mathematics",
    "ml": "Hindi",              # Malhar / Rimjhim variant
    "mm": "Mathematics",        # Maths Magic (class 1-8 legacy)
    "mr": "English",            # Marigold (English reader class 1-5)
    "ph": "Physics",
    "pr": "English",            # Poorvi
    "ps": "Political_Science",
    "py": "Psychology",
    "sa": "Sanskrit",
    "sc": "Science",
    "sr": "Hindi",              # Rimjhim (Hindi reader class 1-5)
    "ss": "Social_Science",
    "st": "Statistics",
    "sy": "Sociology",
    "ve": "Hindi",              # Vasant (Hindi reader class 6-8)
    "we": "English",            # Words and Expressions (class 9-10 workbook)
    "ww": "English",            # Woven Words (class 11)
}

# ─────────────────────────────────────────────────────────────────────────────
# SSC (Telangana) Tables
# ─────────────────────────────────────────────────────────────────────────────

SSC_ROMAN: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12,
}

SSC_ORDINAL: Dict[str, int] = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
}

# Ordered so longer/more-specific keywords match first
SSC_SUBJECT_KEYWORDS: List[Tuple[str, str]] = [
    ("fl hindi",               "Hindi"),
    ("fl telugu",              "Telugu"),
    ("tel fl",                 "Telugu"),
    ("telugu",                 "Telugu"),
    ("hindi",                  "Hindi"),
    ("urdu",                   "Urdu"),
    ("general science",        "Science"),
    ("physics",                "Physics"),
    ("biology",                "Biology"),
    ("chemistry",              "Chemistry"),
    ("social studies",         "Social_Studies"),
    ("social",                 "Social_Studies"),
    ("mathematics",            "Mathematics"),
    ("maths",                  "Mathematics"),
    ("math",                   "Mathematics"),
    ("environmental studies",  "Environmental_Studies"),
    ("we - our environment",   "Environmental_Studies"),
    ("evs",                    "Environmental_Studies"),
    ("evm",                    "Environmental_Studies"),
    ("english reader",         "English"),
    ("english textbook",       "English"),
    ("english",                "English"),
    ("engish",                 "English"),
    ("science",                "Science"),
    ("sanskrit",               "Sanskrit"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Language / OCR Detection
# ─────────────────────────────────────────────────────────────────────────────

def normalize_pua_ascii(text: str) -> str:
    """
    Decodes standard Symbol/Type 1 fonts where ASCII characters (0x20..0x7E)
    are placed in the PUA block 0xF020..0xF0FE.
    """
    return "".join(chr(ord(c) - 0xF000) if 0xF020 <= ord(c) <= 0xF0FE else c for c in text)


def _sample_text(doc: fitz.Document, max_pages: int = 5) -> str:
    parts: List[str] = []
    for i in range(min(max_pages, len(doc))):
        try:
            raw = doc[i].get_text()
            parts.append(normalize_pua_ascii(raw))
        except Exception:
            pass
    return "\n".join(parts)


def detect_language_and_ocr(
    text: str, fname: str
) -> Tuple[str, bool, bool]:
    """
    Returns (language, text_extractable, needs_ocr).

    needs_ocr=True when:
      • Text is overwhelmingly Private-Use-Area characters (Telugu PUA font).
      • Text has legacy ligature/Latin combo with no Devanagari (Krutidev/ISM font).
      • Filename implies a language but no corresponding Unicode script found.
    """
    fname_lower = fname.lower()

    if not text or len(text.strip()) < 50:
        return "Unknown", False, True

    total_chars = max(len(text), 1)

    # ── PUA detection (Telugu encoded with Windows-1252 PUA font) ──────────
    pua_count = sum(1 for c in text if "\ue000" <= c <= "\uf8ff")
    pua_ratio = pua_count / total_chars
    if pua_ratio > 0.05:
        return "Telugu", False, True

    # ── Script presence ─────────────────────────────────────────────────────
    has_devanagari = any("\u0900" <= c <= "\u097f" for c in text)
    has_telugu     = any("\u0c00" <= c <= "\u0c7f" for c in text)
    has_arabic     = any("\u0600" <= c <= "\u06ff" for c in text)
    has_latin      = any("a" <= c.lower() <= "z"  for c in text)

    # ── Legacy Hindi font detection (Krutidev, ISM, etc.) ───────────────────
    # These encode Devanagari using Latin codepoints + typographic ligatures.
    # Signature: Latin text with chars like ÁÆÊÎÔÙÝàáâãäå, ﬁﬂ ligatures, etc.
    ligature_count = sum(1 for c in text if "\ufb00" <= c <= "\ufb4f")
    special_latin  = sum(1 for c in text if c in
                         "ÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ")
    weird_ratio = (ligature_count + special_latin) / total_chars
    if weird_ratio > 0.04 and not has_devanagari:
        is_hindi_fname = "hindi" in fname_lower or "fl hindi" in fname_lower
        return "Hindi", False, True if is_hindi_fname else (True, False, True)

    # ── Filename-clued checks ────────────────────────────────────────────────
    if ("tel fl" in fname_lower or "telugu" in fname_lower or "tel " in fname_lower):
        if not has_telugu:
            return "Telugu", False, True  # Filename says Telugu but no Unicode Telugu → PUA

    if ("fl hindi" in fname_lower or "hindi" in fname_lower):
        if not has_devanagari and has_latin:
            return "Hindi", False, True  # Legacy Hindi font

    # ── Primary language ─────────────────────────────────────────────────────
    if has_telugu:
        lang = "Telugu"
    elif has_devanagari and has_latin:
        lang = "Mixed"   # e.g. Hindi-medium NCERT with some Latin headers
    elif has_devanagari:
        lang = "Hindi"
    elif has_arabic:
        lang = "Urdu"
    elif has_latin:
        lang = "English"
    else:
        lang = "Unknown"

    text_extractable = len(text.strip()) > 100
    needs_ocr = not text_extractable
    return lang, text_extractable, needs_ocr


# ─────────────────────────────────────────────────────────────────────────────
# NCERT Filename Parser
# ─────────────────────────────────────────────────────────────────────────────

_NCERT_RE = re.compile(r"^([a-l])([a-z]{2,4})(\d{2,4})$")


def parse_ncert_filename(fname: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Decode NCERT filename: [class_letter][medium][subject_2chars][volume][chapter_2d].pdf
    e.g. keph101 → class=11, English, Physics, vol=1, chapter=01

    Returns (meta_dict, None) on success or (None, reason_str) on failure.
    """
    stem = Path(fname).stem.rstrip(".").lower()
    m = _NCERT_RE.match(stem)
    if not m:
        return None, f"Filename '{fname}' does not match NCERT pattern [class][alpha][digits]"

    class_char, alpha, digits = m.group(1), m.group(2), m.group(3)

    class_num = NCERT_CLASS_LETTER.get(class_char)
    if class_num is None:
        return None, f"Unknown class letter '{class_char}' in '{fname}'"

    # Parse medium from position 0 of alpha, subject from positions 1-2
    medium_char  = alpha[0]
    subject_code = alpha[1:3]
    medium       = NCERT_MEDIUM_LETTER.get(medium_char)
    subject      = NCERT_SUBJECT_MAP.get(subject_code)

    # Fallback: try positions 0-1 as subject (no medium encoding)
    if subject is None:
        subject_code_alt = alpha[:2]
        subject_alt      = NCERT_SUBJECT_MAP.get(subject_code_alt)
        if subject_alt:
            subject      = subject_alt
            medium       = None
            subject_code = subject_code_alt

    # Digits: first digit = volume, last 2 = chapter number
    # e.g. "101" → vol=1, ch=1 ; "201" → vol=2, ch=1 ; "113" → vol=1, ch=13
    volume     = int(digits[0])
    chapter_no = int(digits[1:]) if len(digits) > 1 else None

    # Book code: class + alpha + volume digit
    book_code = f"{class_char}{alpha}{digits[0]}"

    # Derive book series name from known mappings (best-effort)
    subject_label = subject or "Unknown"
    medium_label  = medium or "Unknown"
    book_title    = f"NCERT {subject_label} (Class {class_num}, {medium_label} medium, Vol {volume})"

    meta: Dict[str, Any] = {
        "board":         "NCERT",
        "class_num":     class_num,
        "medium":        medium or "Unknown",
        "subject":       subject,
        "book_title":    book_title,
        "book_code":     book_code,
        "volume":        volume,
        "chapter_number": chapter_no,
    }

    if subject is None:
        return None, (
            f"Unknown subject code '{subject_code}' (alpha='{alpha}') in '{fname}'. "
            f"class={class_num}, medium_char='{medium_char}'. "
            f"Add the 2-char code to NCERT_SUBJECT_MAP."
        )

    return meta, None


# ─────────────────────────────────────────────────────────────────────────────
# SSC Filename Parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ssc_class(fname: str, doc_text: str = "") -> Optional[int]:
    """Extract class number from SSC human-readable filename or document text."""
    stem = Path(fname).stem.rstrip(".")

    # Roman numeral at start: "IX Biology", "X Mathematics", "VI General Science"
    m = re.match(r"^(XII|XI|IX|VIII|VII|VI|IV|III|II|I|X|V)\s", stem, re.IGNORECASE)
    if m:
        return SSC_ROMAN.get(m.group(1).upper())

    # Ordinal: "1st class", "2nd Class", "4th Class", "4th Tel", "6th Social", "7th Science"
    m = re.match(r"^(\d+(?:st|nd|rd|th))\b", stem, re.IGNORECASE)
    if m:
        return SSC_ORDINAL.get(m.group(1).lower())

    # Plain digit prefix: "7 English Reader", "8 Maths EM", "9 Social", "5em"
    m = re.match(r"^(\d+)(?:\s+|[a-zA-Z])", stem)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return n

    # "Class X", "Class - X", "Class VI" in the filename
    m = re.search(r"\bClass\s*[-–—]?\s*(XII|XI|IX|VIII|VII|VI|IV|III|II|I|X|V|\d+)\b", stem, re.IGNORECASE)
    if m:
        val = m.group(1).upper()
        if val in SSC_ROMAN:
            return SSC_ROMAN[val]
        if val.isdigit() and 1 <= int(val) <= 12:
            return int(val)

    # Check first few pages of text if available
    if doc_text:
        m = re.search(r"\bCLASS\s*[-–—]?\s*(XII|XI|IX|VIII|VII|VI|IV|III|II|I|X|V|\d+)\b", doc_text, re.IGNORECASE)
        if m:
            val = m.group(1).upper()
            if val in SSC_ROMAN:
                return SSC_ROMAN[val]
            if val.isdigit() and 1 <= int(val) <= 12:
                return int(val)

    return None


def _parse_ssc_subject(fname: str, doc_text: str = "") -> Optional[str]:
    """Extract subject from SSC human-readable filename or document text."""
    lower = fname.lower()
    for keyword, subject in SSC_SUBJECT_KEYWORDS:
        if keyword in lower:
            return subject
    if doc_text:
        doc_lower = doc_text.lower()
        for keyword, subject in SSC_SUBJECT_KEYWORDS:
            if keyword in doc_lower:
                return subject
    return None


def parse_ssc_filename(fname: str, doc_text: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse SSC (Telangana board) whole-book filename and text."""
    class_num = _parse_ssc_class(fname, doc_text)
    subject   = _parse_ssc_subject(fname, doc_text)

    meta: Dict[str, Any] = {
        "board":          "SSC",
        "class_num":      class_num,
        "medium":         "English",   # EM books; needs_ocr will be True for Tel/Hindi
        "subject":        subject,
        "book_title":     None,        # filled in from PDF cover page
        "book_code":      None,
        "volume":         None,
        "chapter_number": None,        # whole book — chapters extracted via ToC in Phase 2
    }

    issues: List[str] = []
    if class_num is None:
        issues.append(f"Could not determine class from '{fname}'")
    if subject is None:
        issues.append(f"Could not determine subject from '{fname}'")

    if issues:
        return None, "; ".join(issues)

    return meta, None


# ─────────────────────────────────────────────────────────────────────────────
# Chapter / Book Title Extraction
# ─────────────────────────────────────────────────────────────────────────────

_SKIP_HEADERS = frozenset({
    "PHYSICS", "CHEMISTRY", "BIOLOGY", "MATHEMATICS", "SCIENCE",
    "HISTORY", "GEOGRAPHY", "ENGLISH", "ECONOMICS", "COMPUTER SCIENCE",
    "SANSKRIT", "HINDI", "URDU", "POLITICAL SCIENCE", "PSYCHOLOGY",
    "SOCIOLOGY", "STATISTICS", "ACCOUNTANCY", "WOVEN WORDS",
    "CURIOSITY", "MARIGOLD", "POORVI", "VASANT", "GANITA PRAKASH",
    "JOYFUL MATHEMATICS", "MATH-MAGIC", "HONEYSUCKLE", "A PACT WITH THE SUN",
    "OUR ENVIRONMENT", "LOOKING AROUND", "AN ALIEN HAND", "HONEYDEW",
    "IT SO HAPPENED", "FIRST FLIGHT", "FOOTPRINTS WITHOUT FEET",
    "HORNBILL", "SNAPSHOTS", "KALEIDOSCOPE", "FLAMINGO", "VISTAS",
})

_SKIP_PATTERNS = re.compile(
    r"^(\d+|[ivxlcdm]+|chapter\s*\d+|unit\s*\d+)$",
    re.IGNORECASE,
)


def extract_chapter_title(doc: fitz.Document) -> Optional[str]:
    """
    Extract the chapter title from an NCERT chapter PDF.
    NCERT chapter PDFs have the title in the first 3 pages, typically as the
    first non-trivial line that isn't a page number, subject header, or
    bare chapter number.
    """
    for pg_idx in range(min(4, len(doc))):
        try:
            raw = doc[pg_idx].get_text()
            text = normalize_pua_ascii(raw)
        except Exception:
            continue
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines:
            line_clean = re.sub(r"^\d+\s+", "", line).strip()
            if len(line) < 4 or len(line) > 100:
                continue
            if line.upper() in _SKIP_HEADERS or line_clean.upper() in _SKIP_HEADERS:
                continue
            if "TEXTBOOK OF" in line.upper() or "REPRINT 20" in line.upper() or "UNIT I -" in line:
                continue
            if _SKIP_PATTERNS.match(line) or _SKIP_PATTERNS.match(line_clean):
                continue
            if line.startswith(("©", "•", "–", "—", "★", "●")):
                continue
            # Skip lines that are all-caps acronyms or roman numerals
            if re.match(r"^[IVXLCivxlc]+$", line):
                continue
            return line_clean if line_clean else line
    return None


def extract_book_title_from_pdf(doc: fitz.Document) -> Optional[str]:
    """
    For SSC whole-books: extract book title from first page.
    Returns the first meaningful line (>10 chars, not a page number).
    """
    if not doc:
        return None
    try:
        text = doc[0].get_text()
    except Exception:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:15]:
        if len(line) > 10 and not re.match(r"^\d+$", line):
            return line[:120]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SHA-256 (streaming)
# ─────────────────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Per-PDF Processing
# ─────────────────────────────────────────────────────────────────────────────

def process_pdf(
    path: Path,
    board: str,
    api_root: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Process a single PDF. Returns exactly one of:
      (resolved_entry, None)  — fully classified
      (None, unresolved_entry) — has issues, goes to manifest_unresolved.json
    """
    rel_path  = str(path.relative_to(api_root)).replace("\\", "/")
    fname     = path.name
    doc: Optional[fitz.Document] = None

    def _unresolved(reason: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
        base = {"file_path": rel_path, "board": board, "filename": fname, "reason": reason}
        if extra:
            base.update(extra)
        return base

    try:
        sha = sha256_file(path)
    except Exception as e:
        return None, _unresolved(f"sha256 failed: {e}")

    try:
        doc = fitz.open(str(path))
        page_count = len(doc)
    except Exception as e:
        return None, _unresolved(f"PDF open failed: {e}", {"sha256": sha})

    try:
        text_sample      = _sample_text(doc, max_pages=5)
        language, text_extractable, needs_ocr = detect_language_and_ocr(text_sample, fname)

        if board == "NCERT":
            meta, parse_err = parse_ncert_filename(fname)
            chapter_title   = extract_chapter_title(doc) if meta else None
            book_title      = meta.get("book_title") if meta else None
        else:
            meta, parse_err = parse_ssc_filename(fname, text_sample)
            chapter_title   = None  # whole book; chapters determined in Phase 2 via ToC
            pdf_title       = extract_book_title_from_pdf(doc)
            book_title      = pdf_title
            if meta:
                meta["book_title"] = pdf_title

        # For NCERT Hindi-medium books, the PDF content is Hindi but
        # cover page might have only English lines — re-check medium.
        if meta and meta.get("medium") == "Hindi" and language == "English":
            language = "Mixed"   # English structural text + Hindi body

        entry: Dict[str, Any] = {
            "file_path":       rel_path,
            "sha256":          sha,
            "page_count":      page_count,
            "board":           board,
            "class_num":       meta.get("class_num")     if meta else None,
            "subject":         meta.get("subject")       if meta else None,
            "book_title":      book_title,
            "book_code":       meta.get("book_code")     if meta else None,
            "chapter_number":  meta.get("chapter_number") if meta else None,
            "chapter_title":   chapter_title,
            "medium":          meta.get("medium")        if meta else None,
            "volume":          meta.get("volume")        if meta else None,
            "language":        language,
            "text_extractable": text_extractable,
            "needs_ocr":       needs_ocr,
        }

        if parse_err:
            entry["reason"] = parse_err
            return None, entry

        return entry, None

    except Exception as e:
        return None, _unresolved(f"Processing error: {e}", {"sha256": sha, "page_count": page_count if 'page_count' in dir() else None})
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def print_statistics(resolved: List[Dict], unresolved: List[Dict]) -> None:
    total = len(resolved) + len(unresolved)
    needs_ocr_resolved   = sum(1 for e in resolved   if e.get("needs_ocr"))
    needs_ocr_unresolved = sum(1 for e in unresolved if e.get("needs_ocr"))
    needs_ocr_total      = needs_ocr_resolved + needs_ocr_unresolved

    print()
    print("=" * 65)
    print("MANIFEST STATISTICS")
    print("=" * 65)
    print(f"Total PDFs scanned  : {total}")
    print(f"  Resolved          : {len(resolved)}")
    print(f"  Unresolved        : {len(unresolved)}")
    print(f"needs_ocr (skip P2) : {needs_ocr_total}")
    print()

    # ── NCERT breakdown ──────────────────────────────────────────────────────
    ncert = [e for e in resolved if e.get("board") == "NCERT"]
    print(f"NCERT resolved chapters: {len(ncert)}")
    cls_ctr  = Counter(e.get("class_num") for e in ncert)
    subj_ctr = Counter(e.get("subject")   for e in ncert)
    print("  By class:")
    for cls in sorted(c for c in cls_ctr if c is not None):
        print(f"    Class {cls:2d}  : {cls_ctr[cls]:4d} chapters")
    print("  By subject:")
    for subj, cnt in subj_ctr.most_common():
        print(f"    {(subj or 'None'):<30s}: {cnt:4d}")

    # ── SSC breakdown ────────────────────────────────────────────────────────
    ssc = [e for e in resolved if e.get("board") == "SSC"]
    print()
    print(f"SSC resolved books: {len(ssc)}")
    for e in sorted(ssc, key=lambda x: (x.get("class_num") or 0)):
        ocr_flag = " [needs_ocr]" if e.get("needs_ocr") else ""
        print(f"  Class {str(e.get('class_num') or '?'):>2s}  {(e.get('subject') or 'Unknown'):<22s}{ocr_flag}")

    # ── Language distribution ─────────────────────────────────────────────────
    lang_ctr = Counter(e.get("language") for e in resolved + unresolved)
    print()
    print("Language distribution (all files):")
    for lang, cnt in lang_ctr.most_common():
        print(f"  {(lang or 'None'):<12s}: {cnt}")

    # ── Unresolved list ───────────────────────────────────────────────────────
    if unresolved:
        print()
        print(f"Unresolved files ({len(unresolved)} total):")
        for u in unresolved:
            fpath = u.get("file_path", u.get("filename", "?"))
            reason = u.get("reason", "unknown")
            print(f"  [{u.get('board','?')}] {Path(fpath).name:<50s}  {reason[:80]}")
    print("=" * 65)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1: Build PDF manifest for EduSim RAG")
    parser.add_argument("--textbooks-dir", default="textbooks")
    parser.add_argument("--output-dir",    default="data")
    args = parser.parse_args()

    api_root      = Path(__file__).resolve().parents[1]   # EduSim_API/
    textbooks_dir = (api_root / args.textbooks_dir).resolve()
    output_dir    = (api_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ncert_dir = textbooks_dir / "ncert books"
    ssc_dir   = textbooks_dir / "Text Books"

    for d, label in ((ncert_dir, "NCERT"), (ssc_dir, "SSC")):
        if not d.exists():
            logger.error(f"{label} directory not found: {d}")
            sys.exit(1)

    ncert_pdfs = sorted(ncert_dir.glob("*.pdf"))
    ssc_pdfs   = sorted(ssc_dir.glob("*.pdf"))
    total      = len(ncert_pdfs) + len(ssc_pdfs)
    logger.info(f"Found {len(ncert_pdfs)} NCERT + {len(ssc_pdfs)} SSC = {total} PDFs")

    resolved:   List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    # ── Process NCERT ────────────────────────────────────────────────────────
    for i, path in enumerate(ncert_pdfs, 1):
        if i % 100 == 0 or i == len(ncert_pdfs):
            logger.info(f"  NCERT {i}/{len(ncert_pdfs)}  (resolved={len(resolved)}, unresolved={len(unresolved)})")
        ok, bad = process_pdf(path, "NCERT", api_root)
        if ok:
            resolved.append(ok)
        else:
            unresolved.append(bad)

    # ── Process SSC ──────────────────────────────────────────────────────────
    for i, path in enumerate(ssc_pdfs, 1):
        logger.info(f"  SSC [{i:2d}/{len(ssc_pdfs)}] {path.name[:60]}")
        ok, bad = process_pdf(path, "SSC", api_root)
        if ok:
            resolved.append(ok)
        else:
            unresolved.append(bad)

    # ── Write outputs ────────────────────────────────────────────────────────
    manifest_path   = output_dir / "manifest.json"
    unresolved_path = output_dir / "manifest_unresolved.json"

    with open(manifest_path,   "w", encoding="utf-8") as f:
        json.dump(resolved,   f, ensure_ascii=False, indent=2)
    with open(unresolved_path, "w", encoding="utf-8") as f:
        json.dump(unresolved, f, ensure_ascii=False, indent=2)

    logger.info(f"Wrote manifest        -> {manifest_path}")
    logger.info(f"Wrote manifest_unresolved -> {unresolved_path}")

    print_statistics(resolved, unresolved)


if __name__ == "__main__":
    main()
