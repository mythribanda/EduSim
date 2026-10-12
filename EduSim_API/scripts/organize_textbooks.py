"""
Organize Textbooks Script for EduSim RAG Pipeline.

Two modes:
  Phase A: python -m scripts.organize_textbooks scan --src "<folder>"
  Phase B: python -m scripts.organize_textbooks apply [--phase 1|2|all] [--dest "<dest>"]

Source folder is treated as strictly read-only: never modify, move or delete anything in it.
"""

import os
import sys
import argparse
import hashlib
import csv
import json
import shutil
import re
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
except ImportError:
    pdfminer_extract = None

# Reconfigure stdout to UTF-8 for Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure TESSDATA_PREFIX is configured if tessdata exists locally
LOCAL_TESSDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tessdata')
if os.path.exists(LOCAL_TESSDATA) and 'TESSDATA_PREFIX' not in os.environ:
    os.environ['TESSDATA_PREFIX'] = os.path.abspath(LOCAL_TESSDATA)

# Regex for NCERT chapter files (tolerating double dot like "jewe204..pdf")
NCERT_REGEX = re.compile(r'^([a-l])([ehu])([a-z]{2})(\d)(\d{2})\.+pdf$', re.IGNORECASE)

NCERT_CLASS_MAP = {
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6,
    'g': 7, 'h': 8, 'i': 9, 'j': 10, 'k': 11, 'l': 12
}

NCERT_LANG_MAP = {
    'e': 'en',
    'h': 'hi',
    'u': 'ur'
}

# Whitelist ONLY
# sc=science, ph=physics, ch=chemistry, bo=biology,
# cu=science (classes 6-8 only, "Curiosity"),
# mh=mathematics,
# gp=mathematics (classes 6-8 only, "Ganita Prakash")
NCERT_WHITELIST = {
    'sc': 'science',
    'ph': 'physics',
    'ch': 'chemistry',
    'bo': 'biology',
    'cu': 'science',
    'mh': 'mathematics',
    'gp': 'mathematics'
}

WORD_NUMBER_MAP = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
    'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
    'nineteen': 19, 'twenty': 20
}

ROMAN_CLASS_MAP = {
    'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
    'IV': 4, 'V': 5, 'I': 1, 'II': 2, 'III': 3
}

CSV_COLUMNS = [
    'file',
    'board',
    'class',
    'subject',
    'part',
    'language',
    'chapter_no',
    'book_chapter_no',
    'verified',
    'verification_note',
    'chapter_title',
    'pages',
    'sha256',
    'duplicate_of',
    'extraction_method',
    'garbled_pct',
    'chars_per_page',
    'needs_ocr',
    'cover_line',
    'toc_level1_count',
    'toc_sample',
    'phase',
    'action',
    'confidence',
    'reason'
]


def compute_sha256(filepath: str) -> str:
    """Compute sha256 checksum of a file efficiently."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculate_garbled_rate(text: str) -> Tuple[int, int, float]:
    """Calculate total characters, garbled characters (PUA or \ufffd), and garbled %."""
    total = len(text)
    if total == 0:
        return 0, 0, 0.0
    garbled = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF or ch == '\ufffd')
    return total, garbled, round(garbled / total * 100.0, 2)


def extract_text_with_fallbacks(filepath: str, doc_fitz: fitz.Document) -> Tuple[str, str, float, float]:
    """
    Extract text across pages trying:
      1) pymupdf
      2) pdfminer.six
      3) pypdfium2
      4) pymupdf get_textpage_ocr(full=True)
    Returns: (sample_text, method_name, garbled_pct, chars_per_page)
    Uses the first method whose garbled rate is under 2.0% (or fallback to best).
    """
    pages = len(doc_fitz)
    if pages == 0:
        return "", "pymupdf", 0.0, 0.0

    # Page sampling for metrics
    sample_indices = list(range(pages)) if pages <= 12 else (
        list(range(min(5, pages))) + [pages // 2] + list(range(pages - 3, pages))
    )
    sample_indices = sorted(list(set(sample_indices)))

    # Step 1: Try PyMuPDF
    fitz_texts = [doc_fitz[i].get_text() for i in sample_indices]
    fitz_full = "".join(fitz_texts)
    t_tot, t_garb, fitz_garb_pct = calculate_garbled_rate(fitz_full)
    chars_per_page = round(t_tot / len(sample_indices), 1) if sample_indices else 0.0

    if fitz_garb_pct < 2.0 and chars_per_page >= 80.0:
        return fitz_full, "pymupdf", fitz_garb_pct, chars_per_page

    # If garbled rate > 15% or text poor, try fallbacks in order:
    # Fallback 1: pdfminer.six
    if pdfminer_extract is not None:
        try:
            miner_text = pdfminer_extract(filepath, page_numbers=sample_indices)
            m_tot, m_garb, miner_garb_pct = calculate_garbled_rate(miner_text)
            if miner_garb_pct < 2.0 and (m_tot / len(sample_indices)) >= 80.0:
                return miner_text, "pdfminer.six", miner_garb_pct, round(m_tot / len(sample_indices), 1)
        except Exception:
            pass

    # Fallback 2: pypdfium2
    if pdfium is not None:
        try:
            pdf_ium = pdfium.PdfDocument(filepath)
            ium_texts = [pdf_ium[i].get_textpage().get_text_range() for i in sample_indices]
            ium_full = "".join(ium_texts)
            i_tot, i_garb, ium_garb_pct = calculate_garbled_rate(ium_full)
            if ium_garb_pct < 2.0 and (i_tot / len(sample_indices)) >= 80.0:
                return ium_full, "pypdfium2", ium_garb_pct, round(i_tot / len(sample_indices), 1)
        except Exception:
            pass

    # Fallback 3: PyMuPDF OCR (full=True)
    try:
        ocr_texts = []
        for i in sample_indices:
            tp = doc_fitz[i].get_textpage_ocr(language='eng', full=True)
            ocr_texts.append(tp.extractText())
        ocr_full = "".join(ocr_texts)
        o_tot, o_garb, ocr_garb_pct = calculate_garbled_rate(ocr_full)
        if o_tot > 0 and (o_tot / len(sample_indices)) >= 60.0:
            return ocr_full, "tesseract_ocr", ocr_garb_pct, round(o_tot / len(sample_indices), 1)
    except Exception:
        pass

    # Default to PyMuPDF if none reached < 2%
    return fitz_full, "pymupdf", fitz_garb_pct, chars_per_page


def extract_ncert_chapter_info(doc: fitz.Document, method: str) -> Tuple[Optional[int], str]:
    """
    Extract chapter number and title from page 1 of an NCERT chapter file.
    Only explicit 'Chapter N' / 'CHAPTER N' / 'Unit N' / 'UNIT N' tokens are parsed.
    Standalone digits or 'N.1' are NOT used.
    """
    if len(doc) == 0:
        return None, ''

    if method == "tesseract_ocr":
        try:
            tp = doc[0].get_textpage_ocr(language='eng', full=True)
            p1_text = tp.extractText()
        except Exception:
            p1_text = doc[0].get_text()
    else:
        p1_text = doc[0].get_text()

    lines = [l.strip() for l in p1_text.splitlines() if l.strip()]
    found_num: Optional[int] = None
    title: str = ''

    # Read number only from explicit tokens
    for idx, l in enumerate(lines[:25]):
        # 'Chapter 4', 'CHAPTER FOUR', 'Chapter: 4', 'Unit 1', 'UNIT 1'
        m = re.match(r'^(?:CHAPTER|Chapter|UNIT|Unit)\s*[:\-\s]?\s*([A-Za-z0-9]+)$', l, re.IGNORECASE)
        if m:
            v = m.group(1).lower()
            val = int(v) if v.isdigit() else WORD_NUMBER_MAP.get(v)
            if val is not None:
                found_num = val
                if idx + 1 < len(lines):
                    title = lines[idx + 1]
                elif idx > 0:
                    title = lines[idx - 1]
                break

        # 'Chapter\n4' or 'Unit\n1'
        if l.lower() in ('chapter', 'unit'):
            if idx + 1 < len(lines):
                next_l = lines[idx + 1].lower()
                val = int(next_l) if next_l.isdigit() else WORD_NUMBER_MAP.get(next_l)
                if val is not None:
                    found_num = val
                    if idx + 2 < len(lines):
                        title = lines[idx + 2]
                    elif idx > 0:
                        title = lines[idx - 1]
                    break

        # '4 CHAPTER' or '1 Unit'
        m_rev = re.match(r'^([A-Za-z0-9]+)\s+(?:CHAPTER|Chapter|UNIT|Unit)$', l, re.IGNORECASE)
        if m_rev:
            v = m_rev.group(1).lower()
            val = int(v) if v.isdigit() else WORD_NUMBER_MAP.get(v)
            if val is not None:
                found_num = val
                if idx > 0:
                    title = lines[idx - 1]
                elif idx + 1 < len(lines):
                    title = lines[idx + 1]
                break

    # Title fallback if title is not yet captured
    if not title:
        blocks = doc[0].get_text('blocks')
        for b in sorted(blocks, key=lambda x: (x[1], x[0])):
            if b[1] > 260:
                continue
            b_lines = [bl.strip() for bl in b[4].splitlines() if bl.strip()]
            for bl in b_lines:
                if re.match(r'^(?:CHAPTER|Chapter|Unit|UNIT|\d+|Reprint|MATHEMATICS|Physics|Chemistry|Biology|Curiosity)', bl, re.IGNORECASE):
                    continue
                if len(bl) > 3 and not re.match(r'^\d+\.\d+', bl):
                    title = bl
                    break
            if title:
                break

    return found_num, ' '.join(title.split())


def build_ncert_part_max_map(src_dir: str) -> Dict[Tuple[str, int], int]:
    """Pre-scan all valid NCERT files to determine max chapter_no per (book_code, part)."""
    part_max: Dict[Tuple[str, int], int] = defaultdict(int)
    for fname in os.listdir(src_dir):
        m = NCERT_REGEX.match(fname)
        if not m:
            continue
        c, lang, code, part_str, ch_str = m.groups()
        c_num = NCERT_CLASS_MAP.get(c.lower(), 0)
        if 6 <= c_num <= 12 and lang.lower() == 'e' and code.lower() in NCERT_WHITELIST:
            if code.lower() in ('cu', 'gp') and c_num not in (6, 7, 8):
                continue
            book_key = f"{c.lower()}e{code.lower()}"
            part = int(part_str)
            ch_no = int(ch_str)
            if ch_no > part_max[(book_key, part)]:
                part_max[(book_key, part)] = ch_no
    return part_max


def calculate_book_chapter_no(book_code: str, part: int, chapter_no: int, part_max_map: Dict[Tuple[str, int], int]) -> int:
    """Compute continuous book_chapter_no = chapter_no + sum(max chapter_no of earlier parts)."""
    offset = 0
    for p in range(1, part):
        offset += part_max_map.get((book_code, p), 0)
    return chapter_no + offset


def parse_ncert(
    filename: str,
    filepath: str,
    match: re.Match,
    part_max_map: Dict[Tuple[str, int], int],
    skipped_codes_agg: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Parse and classify an NCERT chapter file with soft verification."""
    c_letter, lang_letter, code, part_str, ch_str = match.groups()
    c_letter = c_letter.lower()
    lang_letter = lang_letter.lower()
    code = code.lower()
    part = int(part_str)
    ch_no = int(ch_str)

    cls = NCERT_CLASS_MAP.get(c_letter, 0)
    lang = NCERT_LANG_MAP.get(lang_letter, 'other')
    book_code = f"{c_letter}{lang_letter}{code}"

    book_ch_no = calculate_book_chapter_no(book_code, part, ch_no, part_max_map)

    row: Dict[str, Any] = {
        'file': filename,
        'board': 'ncert',
        'class': cls if cls > 0 else '',
        'subject': '',
        'part': part,
        'language': lang,
        'chapter_no': ch_no,
        'book_chapter_no': book_ch_no,
        'verified': False,
        'verification_note': '',
        'chapter_title': '',
        'pages': 0,
        'sha256': '',
        'duplicate_of': '',
        'extraction_method': 'pymupdf',
        'garbled_pct': 0.0,
        'chars_per_page': 0.0,
        'needs_ocr': False,
        'cover_line': '',
        'toc_level1_count': 0,
        'toc_sample': '',
        'phase': 'skip',
        'action': 'skip',
        'confidence': 1.0,
        'reason': ''
    }

    # 1. Language check: Anything not en -> skip
    if lang != 'en':
        row['reason'] = f"language '{lang}' not in scope (en only)"
        return row

    # 2. Class check: Only classes 6-12 are in scope
    if cls < 6 or cls > 12:
        row['reason'] = f"class {cls} not in scope (6-12 only)"
        return row

    # 3. Whitelist check
    if code not in NCERT_WHITELIST:
        row['reason'] = "code not whitelisted"
        if code not in skipped_codes_agg:
            skipped_codes_agg[code] = {'count': 0, 'sample_file': filename, 'heading': ''}
        skipped_codes_agg[code]['count'] += 1
        return row

    # Specific whitelist constraint: cu and gp only for classes 6-8
    if code in ('cu', 'gp') and cls not in (6, 7, 8):
        row['reason'] = f"code '{code}' only valid for classes 6-8 (found class {cls})"
        if code not in skipped_codes_agg:
            skipped_codes_agg[code] = {'count': 0, 'sample_file': filename, 'heading': ''}
        skipped_codes_agg[code]['count'] += 1
        return row

    subject = NCERT_WHITELIST[code]
    row['subject'] = subject

    # Phase assignment
    if subject in ('science', 'physics', 'chemistry', 'biology'):
        row['phase'] = '1'
    elif subject == 'mathematics':
        row['phase'] = '2'

    size = os.path.getsize(filepath)
    if size == 0:
        row['action'] = 'skip'
        row['reason'] = "0-byte file"
        row['confidence'] = 0.0
        return row

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        row['action'] = 'skip'
        row['reason'] = f"unreadable PDF: {e}"
        row['confidence'] = 0.0
        return row

    row['pages'] = len(doc)

    # Text extraction with fallbacks (pdfminer.six, pypdfium2, Tesseract OCR)
    _, method, garbled_pct, chars_per_page = extract_text_with_fallbacks(filepath, doc)
    row['extraction_method'] = method
    row['garbled_pct'] = garbled_pct
    row['chars_per_page'] = chars_per_page
    row['needs_ocr'] = (chars_per_page < 80.0) or (garbled_pct > 15.0)

    # Extract soft chapter info
    ext_ch_no, ext_title = extract_ncert_chapter_info(doc, method)
    row['chapter_title'] = ext_title

    # SOFT verification check:
    # verified=true if page-1 text number equals chapter_no or book_chapter_no
    if ext_ch_no is not None and (ext_ch_no == ch_no or ext_ch_no == book_ch_no):
        row['verified'] = True
        row['verification_note'] = f"verified against text number ({ext_ch_no})"
    else:
        row['verified'] = False
        if ext_ch_no is not None:
            row['verification_note'] = f"page-1 text number ({ext_ch_no}) differs from ch={ch_no} and book_ch={book_ch_no}"
        else:
            row['verification_note'] = "no explicit chapter number token on page 1"

    # Action is authoritative from filename (soft verification does NOT review)
    if row['needs_ocr'] and method != 'tesseract_ocr':
        row['action'] = 'review'
        row['reason'] = f"poor text extraction (garbled={garbled_pct}%, chars/page={chars_per_page})"
        row['confidence'] = 0.6
    else:
        row['action'] = 'copy'
        row['reason'] = "valid NCERT chapter"
        row['confidence'] = 1.0

    return row


def extract_ssc_cover_and_toc(doc: fitz.Document, default_subject: str) -> Tuple[str, str, int, str]:
    """
    Extract the exact cover line used for subject determination, and embedded TOC metadata.
    Returns: (exact_cover_line, resolved_subject, toc_level1_count, toc_sample)
    """
    exact_line = ""
    resolved_subject = default_subject

    # Check first 3 pages
    found = False
    for pno in range(min(3, len(doc))):
        lines = [l.strip() for l in doc[pno].get_text().splitlines() if l.strip()]
        for l in lines:
            if re.search(r'\bPhysical\s+Sciences?\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'physical-science'
                found = True
                break
        if found:
            break
        for l in lines:
            if re.search(r'\bBiological\s+Sciences?\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'biological-science'
                found = True
                break
        if found:
            break
        for l in lines:
            if re.search(r'\bGeneral\s+Science\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'science'
                found = True
                break
        if found:
            break
        for l in lines:
            if re.search(r'\bBiology\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'biology'
                found = True
                break
        if found:
            break
        for l in lines:
            if re.search(r'\b(?:Maths|Mathematics)\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'mathematics'
                found = True
                break
        if found:
            break
        for l in lines:
            if re.search(r'\bScience\b', l, re.IGNORECASE):
                exact_line = l
                resolved_subject = 'science'
                found = True
                break
        if found:
            break

    # Extract TOC
    toc = doc.get_toc()
    l1_entries = [entry for entry in toc if entry[0] == 1]
    sample_first_5 = "; ".join([f"L{e[0]}: {e[1]} (p{e[2]})" for e in toc[:5]])

    return exact_line, resolved_subject, len(l1_entries), sample_first_5


def parse_ssc(
    filename: str,
    filepath: str
) -> Dict[str, Any]:
    """Parse and classify an SSC book file."""
    row: Dict[str, Any] = {
        'file': filename,
        'board': 'ssc',
        'class': '',
        'subject': '',
        'part': '',
        'language': '',
        'chapter_no': '',
        'book_chapter_no': '',
        'verified': True,
        'verification_note': 'SSC whole book',
        'chapter_title': '',
        'pages': 0,
        'sha256': '',
        'duplicate_of': '',
        'extraction_method': 'pymupdf',
        'garbled_pct': 0.0,
        'chars_per_page': 0.0,
        'needs_ocr': False,
        'cover_line': '',
        'toc_level1_count': 0,
        'toc_sample': '',
        'phase': 'skip',
        'action': 'skip',
        'confidence': 1.0,
        'reason': ''
    }

    f_lower = filename.lower()
    if filename == '5em.pdf':
        row['reason'] = "ambiguous filename '5em.pdf'"
        return row

    if 'errata' in f_lower:
        row['reason'] = "errata-only file"
        return row

    if any(k in f_lower for k in ['social', 'english', 'evs', 'hindi', 'tel', 'telugu']):
        row['reason'] = "subject not in scope (Social/English/EVS/Hindi/Telugu)"
        return row

    if not re.search(r'\bEM\b', filename, re.IGNORECASE):
        row['reason'] = "medium not EM (English medium)"
        return row
    row['language'] = 'en'

    # Extract class
    cls: Optional[int] = None
    m_rom = re.match(r'^(VIII|VII|VI|IX|IV|V|X)\b', filename, re.IGNORECASE)
    if m_rom:
        cls = ROMAN_CLASS_MAP.get(m_rom.group(1).upper())

    if cls is None:
        m_ord = re.match(r'^(\d+)(?:st|nd|rd|th)\b', filename, re.IGNORECASE)
        if m_ord:
            cls = int(m_ord.group(1))

    if cls is None:
        m_num = re.match(r'^(\d+)\b', filename)
        if m_num:
            cls = int(m_num.group(1))

    if cls is None:
        row['reason'] = "could not parse class from filename"
        return row

    row['class'] = cls

    if cls < 6 or cls > 10:
        row['reason'] = f"class {cls} not in scope (6-10 only)"
        return row

    # Initial filename subject
    fn_subject: Optional[str] = None
    if re.search(r'\b(?:Maths|Mathematics)\b', filename, re.IGNORECASE):
        fn_subject = 'mathematics'
    elif re.search(r'\b(?:Physical Science)\b', filename, re.IGNORECASE):
        fn_subject = 'physical-science'
    elif re.search(r'\b(?:Biological Science)\b', filename, re.IGNORECASE):
        fn_subject = 'biological-science'
    elif re.search(r'\b(?:Physics)\b', filename, re.IGNORECASE):
        fn_subject = 'physics'
    elif re.search(r'\b(?:Biology)\b', filename, re.IGNORECASE):
        fn_subject = 'biology'
    elif re.search(r'\b(?:General Science|Science)\b', filename, re.IGNORECASE):
        fn_subject = 'science'

    if fn_subject is None:
        row['reason'] = "could not identify in-scope subject token in filename"
        return row

    size = os.path.getsize(filepath)
    if size == 0:
        row['reason'] = "0-byte file"
        row['confidence'] = 0.0
        return row

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        row['reason'] = f"unreadable PDF: {e}"
        row['confidence'] = 0.0
        return row

    row['pages'] = len(doc)

    _, method, garbled_pct, chars_per_page = extract_text_with_fallbacks(filepath, doc)
    row['extraction_method'] = method
    row['garbled_pct'] = garbled_pct
    row['chars_per_page'] = chars_per_page
    row['needs_ocr'] = (chars_per_page < 80.0) or (garbled_pct > 15.0)

    # Extract exact cover line and TOC
    cover_line, resolved_subj, toc_l1_count, toc_sample = extract_ssc_cover_and_toc(doc, fn_subject)
    row['cover_line'] = cover_line
    row['subject'] = resolved_subj
    row['toc_level1_count'] = toc_l1_count
    row['toc_sample'] = toc_sample

    if resolved_subj in ('physics', 'biology', 'science', 'physical-science', 'biological-science'):
        row['phase'] = '1'
    elif resolved_subj == 'mathematics':
        row['phase'] = '2'

    # Verify class in cover
    cover_text = "".join([doc[i].get_text() for i in range(min(3, len(doc)))])
    class_regexes = {
        6: [r'\bVI\b', r'\bClass\s*(?:-|:)?\s*VI\b', r'\bClass\s*(?:-|:)?\s*6\b'],
        7: [r'\bVII\b', r'\bClass\s*(?:-|:)?\s*VII\b', r'\bClass\s*(?:-|:)?\s*7\b'],
        8: [r'\bVIII\b', r'\bClass\s*(?:-|:)?\s*VIII\b', r'\bClass\s*(?:-|:)?\s*8\b'],
        9: [r'\bIX\b', r'\bClass\s*(?:-|:)?\s*IX\b', r'\bClass\s*(?:-|:)?\s*9\b'],
        10: [r'\bX\b', r'\bClass\s*(?:-|:)?\s*X\b', r'\bClass\s*(?:-|:)?\s*10\b']
    }
    class_verified = any(re.search(pat, cover_text, re.IGNORECASE) for pat in class_regexes.get(cls, []))

    if not class_verified:
        row['action'] = 'review'
        row['reason'] = f"cover text does not clearly confirm Class {cls}"
        row['confidence'] = 0.7
    elif row['needs_ocr'] and method != 'tesseract_ocr':
        row['action'] = 'review'
        row['reason'] = "poor text extraction on book (needs OCR)"
        row['confidence'] = 0.6
    else:
        row['action'] = 'copy'
        row['confidence'] = 1.0
        row['reason'] = f"verified SSC book cover (subject={resolved_subj}, class={cls})"

    return row


def scan_textbooks(src_dir: str, manifest_csv: str) -> List[Dict[str, Any]]:
    """Scan and analyze all textbooks, producing a manifest CSV."""
    if not os.path.exists(src_dir):
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    files = sorted(os.listdir(src_dir))
    pdf_files = [f for f in files if f.lower().endswith('.pdf')]
    non_pdf_files = [f for f in files if not f.lower().endswith('.pdf')]

    print(f"Scanning directory: {src_dir}")
    print(f"Total files found: {len(files)} (PDFs: {len(pdf_files)}, non-PDF ignored: {len(non_pdf_files)})")

    # Pre-scan NCERT earlier parts to build part_max map
    part_max_map = build_ncert_part_max_map(src_dir)

    skipped_codes_agg: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    sha_map: Dict[str, str] = {}

    for idx, fname in enumerate(pdf_files, 1):
        fpath = os.path.join(src_dir, fname)

        ncert_m = NCERT_REGEX.match(fname)
        if ncert_m:
            row = parse_ncert(fname, fpath, ncert_m, part_max_map, skipped_codes_agg)
        else:
            row = parse_ssc(fname, fpath)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
            digest = compute_sha256(fpath)
            row['sha256'] = digest
            if digest in sha_map:
                row['duplicate_of'] = sha_map[digest]
                if row['action'] == 'copy':
                    row['action'] = 'skip'
                    row['reason'] = f"duplicate of {sha_map[digest]}"
            else:
                sha_map[digest] = fname

        rows.append(row)

    # Populate headings for skipped codes
    for code, info in skipped_codes_agg.items():
        sample_path = os.path.join(src_dir, info['sample_file'])
        try:
            doc = fitz.open(sample_path)
            if len(doc) > 0:
                lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
                for l in lines:
                    if len(l) > 3 and not re.match(r'^(?:CHAPTER|Chapter|Unit|UNIT|\d+|Reprint)', l, re.IGNORECASE):
                        info['heading'] = l
                        break
        except Exception:
            pass

    out_dir = os.path.dirname(manifest_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(manifest_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"\nWrote manifest to: {manifest_csv} ({len(rows)} rows)\n")
    print_summary(rows, skipped_codes_agg, part_max_map)
    return rows


def print_summary(
    rows: List[Dict[str, Any]],
    skipped_codes_agg: Dict[str, Dict[str, Any]],
    part_max_map: Dict[Tuple[str, int], int]
):
    """Print clean terminal summaries as specified by Phase A."""
    print("=" * 80)
    print("                      TEXTBOOK SCAN SUMMARY REPORT                      ")
    print("=" * 80)

    # Actions summary
    action_counts = Counter(r['action'] for r in rows)
    print("\nACTION BREAKDOWN:")
    for act, cnt in sorted(action_counts.items()):
        print(f"  {act.upper():<10}: {cnt}")

    # Phase breakdown
    phase_counts = Counter(r['phase'] for r in rows)
    print("\nPHASE BREAKDOWN:")
    for ph, cnt in sorted(phase_counts.items()):
        print(f"  Phase {ph:<6}: {cnt}")

    # Copied files breakdown
    print("\nCOPIED FILES BREAKDOWN (action=copy):")
    board_class_subj = Counter((r['board'], r['class'], r['subject'], r['phase']) for r in rows if r['action'] == 'copy')
    print(f"  {'Board':<8} {'Class':<6} {'Subject':<20} {'Phase':<6} {'Count':<6}")
    print("  " + "-" * 50)
    for (b, c, s, ph), cnt in sorted(board_class_subj.items(), key=lambda x: (x[0][0], int(x[0][1]) if str(x[0][1]).isdigit() else 0, x[0][2])):
        print(f"  {b:<8} {c:<6} {s:<20} {ph:<6} {cnt:<6}")

    # Per-book expected-vs-found counts
    print("\n" + "=" * 80)
    print("         PER-BOOK EXPECTED-VS-FOUND COUNTS (NCERT 4-letter + part)       ")
    print("=" * 80)
    print(f"  {'Book (4-letter + part)':<25} {'Range':<12} {'Found':<8} {'Expected':<10} {'Status'}")
    print("  " + "-" * 65)

    ncert_groups = defaultdict(list)
    for r in rows:
        if r['board'] == 'ncert' and r['action'] == 'copy':
            c_char = chr(ord('a') + int(r['class']) - 1)
            # find original 2-letter code
            sub = r['subject']
            # lookup reverse code or from filename
            fname = r['file']
            bcode = fname[:4]
            part = r['part']
            ncert_groups[(bcode, part)].append(int(r['chapter_no']))

    for (bcode, part), ch_list in sorted(ncert_groups.items()):
        ch_list = sorted(ch_list)
        min_c = min(ch_list)
        max_c = max(ch_list)
        found_cnt = len(ch_list)
        expected_cnt = max_c - min_c + 1
        stat = "COMPLETE" if found_cnt == expected_cnt else f"GAP ({expected_cnt - found_cnt} missing)"
        print(f"  {f'{bcode} part {part}':<25} {f'[{min_c}..{max_c}]':<12} {found_cnt:<8} {expected_cnt:<10} {stat}")

    # Skipped NCERT codes table
    print("\n" + "=" * 80)
    print("                 DISTINCT SKIPPED NCERT CODES TABLE                     ")
    print("=" * 80)
    print(f"{'Code':<6} {'Count':<8} {'Sample File':<16} {'Sample First Heading Text'}")
    print("-" * 80)
    for code, info in sorted(skipped_codes_agg.items()):
        heading = info['heading'][:50] if info['heading'] else '<no heading detected>'
        print(f"{code:<6} {info['count']:<8} {info['sample_file']:<16} {heading}")

    # Review rows
    review_rows = [r for r in rows if r['action'] == 'review']
    print("\n" + "=" * 80)
    print(f"                FILES REQUIRING REVIEW ({len(review_rows)} files)                   ")
    print("=" * 80)
    if review_rows:
        print(f"{'File':<36} {'Board':<7} {'Class':<6} {'Subj':<16} {'Reason'}")
        print("-" * 80)
        for r in review_rows:
            f_disp = r['file'][:35]
            print(f"{f_disp:<36} {r['board']:<7} {str(r['class']):<6} {str(r['subject']):<16} {r['reason']}")
    else:
        print("None! All candidate files passed cleanly.")

    # Needs OCR rows
    ocr_rows = [r for r in rows if r['needs_ocr']]
    print("\n" + "=" * 80)
    print(f"                FILES NEEDING OCR ({len(ocr_rows)} files)                         ")
    print("=" * 80)
    if ocr_rows:
        for r in ocr_rows:
            print(f"  {r['file']}: method={r['extraction_method']}, garbled={r['garbled_pct']}%, chars/page={r['chars_per_page']}")
    else:
        print("None!")

    print("=" * 80 + "\n")


def apply_textbooks(
    src_dir: str,
    manifest_csv: str = 'data/textbooks_manifest.csv',
    dest_dir: str = 'data/textbooks',
    phase_filter: Optional[str] = None
):
    """
    Phase B: Copy action=copy files into organized destination folder.
    Refuses to run while any row in manifest is 'review'.
    """
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"Manifest not found: {manifest_csv}. Run 'scan' first.")

    with open(manifest_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    review_rows = [r for r in rows if r['action'] == 'review']
    if review_rows:
        print(f"\nERROR: Refusing to apply while {len(review_rows)} row(s) are marked 'review'.")
        print("Please resolve review items in the manifest or address issues before applying.")
        sys.exit(1)

    copy_rows = [r for r in rows if r['action'] == 'copy']
    if phase_filter and phase_filter.lower() != 'all':
        copy_rows = [r for r in copy_rows if str(r['phase']) == str(phase_filter)]

    print(f"Applying changes: copying {len(copy_rows)} files to {dest_dir}...")
    manifest_records: List[Dict[str, Any]] = []

    for r in copy_rows:
        src_path = os.path.join(src_dir, r['file'])
        board = r['board']
        cls = r['class']
        subject = r['subject']

        target_dir = os.path.join(dest_dir, board, str(cls), subject)
        os.makedirs(target_dir, exist_ok=True)

        if board == 'ncert':
            part = int(r['part'])
            ch_no = int(r['chapter_no'])
            clean_name = f"{subject}-c{cls}-p{part}-ch{ch_no:02d}.pdf"
        else:
            clean_name = f"{subject}-c{cls}.pdf"

        target_path = os.path.join(target_dir, clean_name)
        shutil.copy2(src_path, target_path)

        rec = dict(r)
        rec['destination_path'] = target_path.replace('\\', '/')
        rec['clean_name'] = clean_name
        manifest_records.append(rec)

    manifest_json_path = os.path.join(dest_dir, 'manifest.json')
    with open(manifest_json_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_records, f, indent=2, ensure_ascii=False)

    print(f"Successfully copied {len(copy_rows)} files.")
    print(f"Wrote metadata manifest: {manifest_json_path}")


def main():
    parser = argparse.ArgumentParser(description="Organize textbooks for EduSim RAG rebuild.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan source textbook folder and generate manifest CSV.")
    scan_parser.add_argument("--src", required=True, help="Path to source textbooks folder (read-only).")
    scan_parser.add_argument("--out", default="data/textbooks_manifest.csv", help="Output path for manifest CSV.")

    apply_parser = subparsers.add_parser("apply", help="Copy validated textbooks according to manifest.")
    apply_parser.add_argument("--src", default=r"C:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API\textbooks", help="Path to source textbooks folder.")
    apply_parser.add_argument("--manifest", default="data/textbooks_manifest.csv", help="Path to manifest CSV.")
    apply_parser.add_argument("--dest", default="data/textbooks", help="Destination folder.")
    apply_parser.add_argument("--phase", default=None, help="Filter by phase (1, 2, or all).")

    args = parser.parse_args()

    if args.command == "scan":
        scan_textbooks(src_dir=args.src, manifest_csv=args.out)
    elif args.command == "apply":
        apply_textbooks(src_dir=args.src, manifest_csv=args.manifest, dest_dir=args.dest, phase_filter=args.phase)


if __name__ == "__main__":
    main()
