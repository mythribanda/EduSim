"""
EduSim RAG - Phase 2 Textbook Ingestion & Extraction Engine
Robust extraction, denoising, and chunking with full font decoding,
repeated header/footer suppression, and safety gates.
"""

import os
import sys
import re
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Generator
from collections import Counter

import fitz  # PyMuPDF
from transformers import AutoTokenizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest")

# ─────────────────────────────────────────────────────────────────────────────
# Complete Font & Symbol Mapping Tables
# ─────────────────────────────────────────────────────────────────────────────

ADOBE_SYMBOL_MAP = {
    0xF020: " ", 0xF021: "!", 0xF022: "∀", 0xF023: "#", 0xF024: "∃",
    0xF025: "%", 0xF026: "&", 0xF027: "∍", 0xF028: "(", 0xF029: ")",
    0xF02A: "∗", 0xF02B: "+", 0xF02C: ",", 0xF02D: "−", 0xF02E: ".",
    0xF02F: "/", 0xF030: "0", 0xF031: "1", 0xF032: "2", 0xF033: "3",
    0xF034: "4", 0xF035: "5", 0xF036: "6", 0xF037: "7", 0xF038: "8",
    0xF039: "9", 0xF03A: ":", 0xF03B: ";", 0xF03C: "<", 0xF03D: "=",
    0xF03E: ">", 0xF03F: "?", 0xF040: "≅", 0xF041: "Α", 0xF042: "Β",
    0xF043: "Χ", 0xF044: "Δ", 0xF045: "Ε", 0xF046: "Φ", 0xF047: "Γ",
    0xF048: "Η", 0xF049: "Ι", 0xF04A: "ϑ", 0xF04B: "Κ", 0xF04C: "Λ",
    0xF04D: "Μ", 0xF04E: "Ν", 0xF04F: "Ο", 0xF050: "Π", 0xF051: "Θ",
    0xF052: "Ρ", 0xF053: "Σ", 0xF054: "Τ", 0xF055: "Υ", 0xF056: "ς",
    0xF057: "Ω", 0xF058: "Ξ", 0xF059: "Ψ", 0xF05A: "Ζ", 0xF05B: "[",
    0xF05C: "∴", 0xF05D: "]", 0xF05E: "⊥", 0xF05F: "_", 0xF060: "‾",
    0xF061: "α", 0xF062: "β", 0xF063: "χ", 0xF064: "δ", 0xF065: "ε",
    0xF066: "φ", 0xF067: "γ", 0xF068: "η", 0xF069: "ι", 0xF06A: "ϕ",
    0xF06B: "κ", 0xF06C: "λ", 0xF06D: "μ", 0xF06E: "ν", 0xF06F: "ο",
    0xF070: "π", 0xF071: "θ", 0xF072: "ρ", 0xF073: "σ", 0xF074: "τ",
    0xF075: "υ", 0xF076: "ϖ", 0xF077: "ω", 0xF078: "ξ", 0xF079: "ψ",
    0xF07A: "ζ", 0xF07B: "{", 0xF07C: "|", 0xF07D: "}", 0xF07E: "~",
    0xF0A0: "€", 0xF0A1: "ϒ", 0xF0A2: "′", 0xF0A3: "≤", 0xF0A4: "⁄",
    0xF0A5: "∞", 0xF0A6: "ƒ", 0xF0A7: "♣", 0xF0A8: "♦", 0xF0A9: "♥",
    0xF0AA: "♠", 0xF0AB: "↔", 0xF0AC: "←", 0xF0AD: "↑", 0xF0AE: "→",
    0xF0AF: "↓", 0xF0B0: "°", 0xF0B1: "±", 0xF0B2: "″", 0xF0B3: "≥",
    0xF0B4: "×", 0xF0B5: "∝", 0xF0B6: "∂", 0xF0B7: "•", 0xF0B8: "÷",
    0xF0B9: "≠", 0xF0BA: "≡", 0xF0BB: "≈", 0xF0BC: "…", 0xF0BD: "⏐",
    0xF0BE: "⎯", 0xF0BF: "↵", 0xF0C0: "ℵ", 0xF0C1: "ℑ", 0xF0C2: "ℜ",
    0xF0C3: "℘", 0xF0C4: "⊗", 0xF0C5: "⊕", 0xF0C6: "∅", 0xF0C7: "∩",
    0xF0C8: "∪", 0xF0C9: "⊃", 0xF0CA: "⊇", 0xF0CB: "⊄", 0xF0CC: "⊂",
    0xF0CD: "⊆", 0xF0CE: "∈", 0xF0CF: "∉", 0xF0D0: "∠", 0xF0D1: "∇",
    0xF0D2: "®", 0xF0D3: "©", 0xF0D4: "™", 0xF0D5: "∏", 0xF0D6: "√",
    0xF0D7: "⋅", 0xF0D8: "¬", 0xF0D9: "∧", 0xF0DA: "∨", 0xF0DB: "⇔",
    0xF0DC: "⇐", 0xF0DD: "⇑", 0xF0DE: "⇒", 0xF0DF: "⇓", 0xF0E0: "◊",
    0xF0E1: "〈", 0xF0E2: "®", 0xF0E3: "©", 0xF0E4: "™", 0xF0E5: "∑",
    0xF0E6: "⎛", 0xF0E7: "⎜", 0xF0E8: "⎝", 0xF0E9: "⎡", 0xF0EA: "⎢",
    0xF0EB: "⎣", 0xF0EC: "⎧", 0xF0ED: "⎨", 0xF0EE: "⎩", 0xF0EF: "⎪",
    0xF0F1: "〉", 0xF0F2: "∫", 0xF0F3: "⌠", 0xF0F4: "⎮", 0xF0F5: "⌡",
    0xF0F6: "⎞", 0xF0F7: "⎟", 0xF0F8: "⎠", 0xF0F9: "⎤", 0xF0FA: "⎥",
    0xF0FB: "⎦", 0xF0FC: "⎫", 0xF0FD: "⎬", 0xF0FE: "⎭",
    # Additional high Symbol matrix bracket glyphs
    0xF8E6: "⎛", 0xF8E7: "⎜", 0xF8E8: "⎝", 0xF8E9: "⎡", 0xF8EA: "⎢",
    0xF8EB: "⎣", 0xF8EC: "⎧", 0xF8ED: "⎨", 0xF8EE: "⎩", 0xF8EF: "│",
    0xF8F0: "⎰", 0xF8F1: "〉", 0xF8F2: "∫", 0xF8F3: "⌠", 0xF8F4: "⎮",
    0xF8F5: "⌡", 0xF8F6: "⎞", 0xF8F7: "⎟", 0xF8F8: "⎠", 0xF8F9: "⎤",
    0xF8FA: "⎥", 0xF8FB: "⎦", 0xF8FC: "⎫", 0xF8FD: "⎬", 0xF8FE: "⎭",
}

MATHTYPE_MAP = {
    0xF0AB: "⇌", 0xF0AE: "→", 0xF02B: "+", 0xF02D: "−", 0xF03D: "=",
    0xF0A3: "≤", 0xF0B3: "≥", 0xF0B4: "×", 0xF0B9: "≠", 0xF0D6: "√",
}

def decode_span_text(font_name: str, text: str) -> str:
    """Decodes span text using exact font-family awareness."""
    if not text:
        return ""

    font_lower = font_name.lower()
    is_symbol_font = any(s in font_lower for s in ["symbol", "euclidsymbol", "symbolmt", "symboltiger"])
    is_mathtype = any(s in font_lower for s in ["mathextra", "mtextra", "mathb", "mathc", "wp-math", "euclidmath", "euclidextra"])
    is_decorative = any(s in font_lower for s in ["wingdings", "webdings", "zapfdingbats"])

    out = []
    for c in text:
        cp = ord(c)

        # Control character cleaning (e.g. 0x07 bell used for bullets)
        if cp < 32 and c not in '\n\r\t':
            out.append("• " if cp == 7 else " ")
            continue

        # In-line formula artifact glyphs (0xF001-0xF004)
        if 0xF001 <= cp <= 0xF004:
            continue

        if is_decorative:
            out.append("• " if cp in [0xF06E, 0xF075, 0xF06C, 0xF076, 0x6E, 0x75] else " ")
            continue

        if is_symbol_font:
            if cp in ADOBE_SYMBOL_MAP:
                out.append(ADOBE_SYMBOL_MAP[cp])
            elif 0x20 <= cp <= 0x7E and (0xF000 + cp) in ADOBE_SYMBOL_MAP:
                out.append(ADOBE_SYMBOL_MAP[0xF000 + cp])
            else:
                out.append(c)
        elif is_mathtype:
            if cp in MATHTYPE_MAP:
                out.append(MATHTYPE_MAP[cp])
            elif cp in ADOBE_SYMBOL_MAP:
                out.append(ADOBE_SYMBOL_MAP[cp])
            else:
                out.append(c)
        elif 0xF020 <= cp <= 0xF0FE:
            ascii_cp = cp - 0xF000
            out.append(chr(ascii_cp))
        elif cp in ADOBE_SYMBOL_MAP:
            out.append(ADOBE_SYMBOL_MAP[cp])
        elif cp == 0xF091:
            out.append("‘")
        elif cp == 0xF092:
            out.append("’")
        elif cp == 0xF093:
            out.append("“")
        elif cp == 0xF094:
            out.append("”")
        elif cp == 0xF096:
            out.append("–")
        elif cp == 0xF097:
            out.append("—")
        elif cp == 0xF0B4:
            out.append("×")
        elif cp == 0xF0B7:
            out.append("•")
        else:
            out.append(c)

    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Header / Footer / Layout Noise Filtering
# ─────────────────────────────────────────────────────────────────────────────

DISCARD_LINE_PATTERNS = [
    re.compile(r"^\d{1,4}$"),               # Standalone page number
    re.compile(r"^[ivxlcdm]{1,6}$", re.I),  # Roman page number
    re.compile(r"^\[\s*\d{1,4}\s*\]$"),     # Bracketed page number [ 12 ]
    re.compile(r"^\(\s*[ivxlcdm0-9]+\s*\)$", re.I), # Parenthesized page number (vii)
    re.compile(r"^Government’?s\s+Gift\s+for\s+Students’?\s+Progress", re.I),
    re.compile(r"^State\s+Council\s+of\s+Educational", re.I),
    re.compile(r"^Published\s+by\s+The\s+Government\s+of\s+Telangana", re.I),
    re.compile(r"^Reprint\s+20\d\d[-–]\d\d", re.I),
    re.compile(r"^Rationalised\s+20\d\d[-–]\d\d", re.I),
    re.compile(r"^Free\s+Distribution\s+by\s+T\.S\.\s+Government", re.I),
]

def find_repeated_headers_footers(doc: fitz.Document) -> Tuple[set, set]:
    header_counts = Counter()
    footer_counts = Counter()

    for pno in range(len(doc)):
        p = doc[pno]
        h = p.rect.height
        d = p.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            y0 = b["bbox"][1]
            y1 = b["bbox"][3]
            txt = " ".join("".join(s["text"] for s in l.get("spans", [])) for l in b.get("lines", [])).strip()
            if not txt:
                continue
            if y1 <= h * 0.12:
                header_counts[txt] += 1
            elif y0 >= h * 0.88:
                footer_counts[txt] += 1

    threshold = 3
    bad_headers = {t for t, cnt in header_counts.items() if cnt >= threshold}
    bad_footers = {t for t, cnt in footer_counts.items() if cnt >= threshold}
    return bad_headers, bad_footers


def classify_page_type(page_text: str, page_num: int, total_pages: int) -> str:
    t_lower = page_text.lower()

    if page_num <= 10:
        if any(term in t_lower for term in [
            "textbook development committee", "foreword", "preface",
            "constitution of india", "national anthem", "pledge",
            "table of contents", "contents", "index\nsl. no."
        ]):
            return "front_matter"
        if len(page_text.strip()) < 100 and ("reprint" in t_lower or "edition" in t_lower):
            return "front_matter"

    if page_num >= total_pages - 15:
        if any(term in t_lower for term in [
            "syllabus maths", "syllabus coverage", "appendix", "answers", "model question paper"
        ]):
            return "summary_back_matter"

    if len(page_text.strip()) < 40:
        return "blank_or_ornament"

    return "content"


# ─────────────────────────────────────────────────────────────────────────────
# Heading Detection
# ─────────────────────────────────────────────────────────────────────────────

HEADING_PATTERNS = [
    re.compile(r"^(?:CHAPTER|UNIT)\s+[0-9IVXLCDM]+", re.IGNORECASE),
    re.compile(r"^\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\s+[A-Z\u0900-\u097F]"),
    re.compile(r"^(?:Section|Exercise|Activity|Summary|Points to ponder)\s+", re.IGNORECASE),
]

def is_heading(line: str, font_size: float, is_bold: bool, avg_font_size: float) -> bool:
    line_s = line.strip()
    if not line_s or len(line_s) > 120:
        return False
    if any(p.match(line_s) for p in HEADING_PATTERNS):
        return True
    if font_size >= avg_font_size * 1.25 and len(line_s.split()) <= 10:
        return True
    if is_bold and font_size >= avg_font_size * 1.1 and len(line_s.split()) <= 8:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Extraction Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_pages(
    doc: fitz.Document,
    ssc_chapters: Optional[List[Dict[str, Any]]] = None,
    default_ch_no: Optional[int] = None,
    default_ch_title: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    bad_headers, bad_footers = find_repeated_headers_footers(doc)
    current_heading = default_ch_title or ""
    total_pages = len(doc)

    for pno in range(total_pages):
        page = doc[pno]
        page_num = pno + 1
        page_h = page.rect.height

        ch_no = default_ch_no
        ch_title = default_ch_title

        if ssc_chapters:
            for ch in ssc_chapters:
                if ch["page_start"] <= page_num <= ch["page_end"]:
                    ch_no = ch["chapter_no"]
                    ch_title = ch["chapter_title"]
                    break

        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])

        raw_page_text = page.get_text()
        section_type = classify_page_type(raw_page_text, page_num, total_pages)

        if section_type != "content":
            continue

        sizes: List[float] = []
        for b in blocks:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    sizes.append(s["size"])
        avg_font_size = sum(sizes) / len(sizes) if sizes else 10.0

        page_paragraphs: List[Tuple[str, str]] = []
        current_para_lines: List[str] = []

        for b in blocks:
            if b.get("type") != 0:
                continue

            y0 = b["bbox"][1]
            y1 = b["bbox"][3]

            for line_obj in b.get("lines", []):
                spans = line_obj.get("spans", [])
                line_text = "".join(decode_span_text(s["font"], s["text"]) for s in spans).strip()

                if not line_text:
                    continue
                if any(p.match(line_text) for p in DISCARD_LINE_PATTERNS):
                    continue
                if (y1 <= page_h * 0.12 and line_text in bad_headers) or (y0 >= page_h * 0.88 and line_text in bad_footers):
                    continue

                line_size = max((s["size"] for s in spans), default=avg_font_size)
                line_bold = any(("Bold" in s["font"] or "bold" in s["font"]) for s in spans)

                if is_heading(line_text, line_size, line_bold, avg_font_size):
                    if current_para_lines:
                        p_txt = " ".join(current_para_lines).strip()
                        if len(p_txt) > 20:
                            h_path = f"{ch_title} > {current_heading}" if (ch_title and current_heading and ch_title != current_heading) else (current_heading or ch_title or "")
                            page_paragraphs.append((h_path, p_txt))
                        current_para_lines = []
                    current_heading = line_text
                else:
                    current_para_lines.append(line_text)

            if current_para_lines:
                p_txt = " ".join(current_para_lines).strip()
                if len(p_txt) > 20:
                    h_path = f"{ch_title} > {current_heading}" if (ch_title and current_heading and ch_title != current_heading) else (current_heading or ch_title or "")
                    page_paragraphs.append((h_path, p_txt))
                current_para_lines = []

        for h_path, p_txt in page_paragraphs:
            yield {
                "page_num": page_num,
                "chapter_no": ch_no,
                "chapter_title": ch_title,
                "heading_path": h_path,
                "text": p_txt,
            }


# ─────────────────────────────────────────────────────────────────────────────
# Sentence Splitting & Chunking
# ─────────────────────────────────────────────────────────────────────────────

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।;\n])\s+(?=[A-Z0-9\u0900-\u097F\(\[\"\'])")

def split_into_sentences(text: str) -> List[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]

def chunk_document(
    extracted_items: List[Dict[str, Any]],
    tokenizer: Any,
    manifest_entry: Dict[str, Any],
    target_tokens: int = 380,
    max_tokens: int = 450,
    overlap_tokens: int = 60,
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    current_sentences: List[str] = []
    current_heading_path = ""
    current_ch_no = None
    current_ch_title = None
    page_start = None
    page_end = None

    def _flush_chunk(sents, h_path, c_no, c_title, p_start, p_end):
        nonlocal chunk_index
        if not sents:
            return None
        body_text = " ".join(sents).strip()
        full_text = "passage: " + body_text
        tokens = len(tokenizer.encode(full_text, add_special_tokens=True))
        if tokens > 512:
            raise ValueError(f"CRITICAL: Chunk exceeds 512 tokens ({tokens})")
        if tokens < 30 and len(body_text.split()) < 6:
            return None

        sha = manifest_entry.get("sha256", "unknown")[:8]
        cid = f"{sha}_{chunk_index:04d}"
        chunk_index += 1

        return {
            "chunk_id": cid,
            "source_file": manifest_entry.get("file_path"),
            "sha256": manifest_entry.get("sha256"),
            "board": manifest_entry.get("board"),
            "class": manifest_entry.get("class_num"),
            "subject": manifest_entry.get("subject"),
            "book": manifest_entry.get("book_title"),
            "chapter_no": c_no or manifest_entry.get("chapter_number"),
            "chapter_title": c_title or manifest_entry.get("chapter_title"),
            "heading_path": h_path or c_title or manifest_entry.get("chapter_title", ""),
            "page_start": p_start,
            "page_end": p_end,
            "language": manifest_entry.get("language", "en"),
            "tokens": tokens,
            "text": full_text,
        }

    for item in extracted_items:
        p_num = item["page_num"]
        h_path = item["heading_path"]
        c_no = item["chapter_no"]
        c_title = item["chapter_title"]
        p_text = item["text"]

        sentences = split_into_sentences(p_text)
        if not sentences:
            continue

        refined_sentences: List[str] = []
        for s in sentences:
            s_tok = len(tokenizer.encode("passage: " + s, add_special_tokens=True))
            if s_tok <= max_tokens:
                refined_sentences.append(s)
            else:
                words = s.split()
                sub_buf: List[str] = []
                for w in words:
                    sub_buf.append(w)
                    if len(tokenizer.encode("passage: " + " ".join(sub_buf), add_special_tokens=True)) >= 380:
                        refined_sentences.append(" ".join(sub_buf))
                        sub_buf = []
                if sub_buf:
                    refined_sentences.append(" ".join(sub_buf))

        for sent in refined_sentences:
            test_sentences = current_sentences + [sent]
            test_text = "passage: " + " ".join(test_sentences)
            token_len = len(tokenizer.encode(test_text, add_special_tokens=True))

            if page_start is None:
                page_start = p_num
            page_end = p_num

            if not current_heading_path and h_path:
                current_heading_path = h_path
            if current_ch_no is None:
                current_ch_no = c_no
            if current_ch_title is None:
                current_ch_title = c_title

            if token_len <= max_tokens:
                current_sentences.append(sent)
            else:
                if current_sentences:
                    chunk = _flush_chunk(
                        current_sentences,
                        current_heading_path,
                        current_ch_no,
                        current_ch_title,
                        page_start,
                        page_end,
                    )
                    if chunk:
                        chunks.append(chunk)

                overlap_sents: List[str] = []
                for s in reversed(current_sentences):
                    test_ol = "passage: " + " ".join([s] + overlap_sents)
                    if len(tokenizer.encode(test_ol, add_special_tokens=True)) <= overlap_tokens:
                        overlap_sents.insert(0, s)
                    else:
                        break

                current_sentences = overlap_sents + [sent]
                current_heading_path = h_path
                current_ch_no = c_no
                current_ch_title = c_title
                page_start = p_num
                page_end = p_num

    if current_sentences:
        chunk = _flush_chunk(
            current_sentences,
            current_heading_path,
            current_ch_no,
            current_ch_title,
            page_start,
            page_end,
        )
        if chunk:
            chunks.append(chunk)

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Post-Chunking Quality Gate Check
# ─────────────────────────────────────────────────────────────────────────────

ILLEGAL_CHAR_RE = re.compile(r"[\uE000-\uF8FF\uFFFD\x00-\x08\x0B\x0C\x0E-\x1F]")

def verify_chunk_safety_gate(chunks: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    violations = []
    for c in chunks:
        raw = c["text"][9:]
        matches = ILLEGAL_CHAR_RE.findall(raw)
        if matches:
            violations.append(f"Chunk {c['chunk_id']} has {len(matches)} illegal chars: {[ord(m) for m in matches[:3]]}")
    return len(violations) == 0, violations


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion Worker
# ─────────────────────────────────────────────────────────────────────────────

def parse_ssc_chapters(doc: fitz.Document) -> List[Dict[str, Any]]:
    chapters = []
    toc = doc.get_toc()
    if not toc:
        return chapters

    valid_toc = [e for e in toc if e[0] == 1 and e[2] > 0]
    filtered_toc = []
    for e in valid_toc:
        t_low = e[1].lower()
        if "cover" in t_low or "total book" in t_low or (len(filtered_toc) > 0 and e[2] < filtered_toc[-1][2]):
            continue
        filtered_toc.append(e)

    for i, item in enumerate(filtered_toc):
        lvl, title, start_p = item
        end_p = filtered_toc[i+1][2] - 1 if i+1 < len(filtered_toc) else len(doc)
        clean_t = re.sub(r"^(?:Ch\s*\d+|Unit\s*\d+|\d{1,2})\s*[-_.:]?\s*", "", title, flags=re.I)
        clean_t = re.sub(r"\.pdf$", "", clean_t, flags=re.I).replace("BIL", "").strip()

        ch_no_match = re.search(r"\b(?:Ch|Unit)?\s*0*(\d{1,2})\b", title, re.I)
        ch_no = int(ch_no_match.group(1)) if ch_no_match else (i + 1)

        chapters.append({
            "chapter_no": ch_no,
            "chapter_title": clean_t if clean_t else f"Chapter {ch_no}",
            "page_start": start_p,
            "page_end": end_p,
        })
    return chapters

def ingest_pdf_file(
    entry: Dict[str, Any],
    api_root: Path,
    output_dir: Path,
    tokenizer: Any,
) -> Tuple[int, Optional[str]]:
    fpath = api_root / entry["file_path"]
    if not fpath.exists():
        return 0, f"File not found: {fpath}"

    base_stem = fpath.stem
    out_file = output_dir / f"{base_stem}.jsonl"

    if out_file.exists() and out_file.stat().st_size > 0:
        with open(out_file, "r", encoding="utf-8") as f:
            count = sum(1 for _ in f)
        return count, None

    doc = None
    try:
        doc = fitz.open(fpath)
        ssc_chapters = parse_ssc_chapters(doc) if entry.get("board") == "SSC" else None

        extracted_items = list(
            extract_pdf_pages(
                doc,
                ssc_chapters=ssc_chapters,
                default_ch_no=entry.get("chapter_number"),
                default_ch_title=entry.get("chapter_title"),
            )
        )

        if not extracted_items:
            return 0, "No content text found"

        chunks = chunk_document(extracted_items, tokenizer=tokenizer, manifest_entry=entry)
        if not chunks:
            return 0, "No chunks generated"

        safe, violations = verify_chunk_safety_gate(chunks)
        if not safe:
            return 0, f"PUA/Control Gate Violation: {violations[0]}"

        with open(out_file, "w", encoding="utf-8") as f:
            for ch in chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + "\n")

        return len(chunks), None

    except Exception as e:
        return 0, str(e)
    finally:
        if doc:
            doc.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest Textbooks with Safety Gates")
    parser.add_argument("--manifest", default="data/manifest.json")
    parser.add_argument("--output-dir", default="data/chunks")
    parser.add_argument("--trial", action="store_true")
    args = parser.parse_args()

    api_root = Path(__file__).resolve().parents[1]
    manifest_path = api_root / args.manifest
    chunks_dir = api_root / args.output_dir
    chunks_dir.mkdir(parents=True, exist_ok=True)
    gate_failures_path = api_root / "data" / "evidence" / "pua_gate_failures.jsonl"
    gate_failures_path.parent.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-small")

    if args.trial:
        must_have = [
            "textbooks/ncert books/keph107.pdf",
            "textbooks/ncert books/ahsr101.pdf",
            "textbooks/ncert books/lemh103.pdf",
            "textbooks/ncert books/aejm101.pdf",
            "textbooks/Text Books/8 English F 08.11.24.pdf",
            "textbooks/Text Books/8 Maths EM 2025-26 Final 08.11.24.pdf",
        ]
        trial_files = [x for x in manifest if x["file_path"] in must_have]
        seen = {x["file_path"] for x in trial_files}
        candidates = [x for x in manifest if not x.get("needs_ocr") and x["file_path"] not in seen and x.get("page_count", 0) > 0]
        import random
        random.seed(42)
        trial_files.extend(random.sample(candidates, 20 - len(trial_files)))
        targets = trial_files
    else:
        targets = [x for x in manifest if not x.get("needs_ocr")]

    logger.info(f"Processing {len(targets)} targets (Trial={args.trial})...")

    total_chunks = 0
    failures = []

    for idx, entry in enumerate(targets, 1):
        fn = Path(entry["file_path"]).name
        num, err = ingest_pdf_file(entry, api_root, chunks_dir, tokenizer)
        if err:
            logger.warning(f"[{idx}/{len(targets)}] {fn} FAIL: {err}")
            failures.append({"file": fn, "error": err})
            with open(gate_failures_path, "a", encoding="utf-8") as gf:
                gf.write(json.dumps({"file": fn, "error": err}) + "\n")
        else:
            total_chunks += num
            if idx % 25 == 0 or idx == len(targets):
                logger.info(f"[{idx}/{len(targets)}] {fn} -> {num} chunks (Total: {total_chunks})")

    logger.info(f"Ingestion Finished: {total_chunks} chunks, {len(failures)} failures.")

if __name__ == "__main__":
    main()
