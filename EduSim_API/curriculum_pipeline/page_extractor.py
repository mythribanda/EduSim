"""
EduSim Curriculum Pipeline — Page Extractor
Streams PDF page by page using PyMuPDF (memory-safe).
Extracts:
  - page_no (1-indexed)
  - text
  - char_count
  - script (latin, devanagari, telugu, arabic/urdu, unknown)
  - method (native, ocr, none)
  - spans [{text, size, bold, font, bbox}]
  - lines [{text, bbox, spans}] (preserves line structure and stitches split numbers)
  - doc outline (TOC)
Detects and strips repeated headers/footers (>40% of pages at the same position).
Resumable: skips if sha256 and extractor version hash match.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import fitz

from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT

EXTRACTOR_VERSION = "2.1.0"
PAGES_DIR = PIPELINE_OUTPUT_ROOT / "pages"


def detect_script(text: str) -> str:
    """Detect dominant script of the text."""
    if not text.strip():
        return "none"
    counts = Counter()
    for ch in text:
        if ch.isspace() or ch.isdigit():
            continue
        try:
            name = unicodedata.name(ch).split()[0].upper()
            if "DEVANAGARI" in name:
                counts["devanagari"] += 1
            elif "TELUGU" in name:
                counts["telugu"] += 1
            elif "ARABIC" in name:
                counts["urdu"] += 1
            elif "LATIN" in name:
                counts["latin"] += 1
            else:
                counts["other"] += 1
        except ValueError:
            counts["unknown"] += 1

    if not counts:
        return "latin"
    dominant, _ = counts.most_common(1)[0]
    return dominant


def calculate_garbled_metrics(text: str) -> Tuple[int, int, float]:
    """Calculate total characters, PUA/replacement characters, and garbled percentage."""
    total = len(text)
    if total == 0:
        return 0, 0, 0.0
    garbled = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF or ch == "\ufffd")
    return total, garbled, round((garbled / total) * 100.0, 2)


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class PageExtractor:
    def __init__(self, pages_output_dir: Optional[Path] = None):
        self.pages_dir = pages_output_dir or PAGES_DIR
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.has_tesseract = shutil.which("tesseract") is not None

    def get_output_path(self, file_id: str) -> Path:
        clean_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", file_id)
        return self.pages_dir / f"{clean_id}.jsonl"

    def is_cached_and_valid(self, file_id: str, current_sha256: str) -> bool:
        """Check if output file exists and has matching file sha256 + extractor version."""
        out_path = self.get_output_path(file_id)
        if not out_path.exists():
            return False
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if not first_line:
                    return False
                meta = json.loads(first_line)
                if meta.get("type") == "metadata":
                    return (
                        meta.get("sha256") == current_sha256
                        and meta.get("extractor_version") == EXTRACTOR_VERSION
                    )
        except Exception:
            return False
        return False

    def extract_file(
        self,
        pdf_path: Path,
        file_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        fid = file_id or pdf_path.name
        out_path = self.get_output_path(fid)

        if not pdf_path.exists():
            return {"file_id": fid, "status": "failed", "error": "File does not exist"}

        size = pdf_path.stat().st_size
        if size == 0:
            return {
                "file_id": fid,
                "status": "failed",
                "reason": "empty_or_corrupt (0-byte file)",
                "pages_extracted": 0,
            }

        file_sha256 = compute_file_sha256(pdf_path)

        if not force and self.is_cached_and_valid(fid, file_sha256):
            return {"file_id": fid, "status": "skipped_cached", "sha256": file_sha256}

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            return {
                "file_id": fid,
                "status": "failed",
                "reason": f"unreadable PDF: {e}",
                "pages_extracted": 0,
            }

        num_pages = len(doc)
        if num_pages == 0:
            return {
                "file_id": fid,
                "status": "failed",
                "reason": "empty_or_corrupt (0 pages in document)",
                "pages_extracted": 0,
            }

        toc = doc.get_toc()

        # Step 1: Detect repeated headers & footers across pages
        top_candidates = Counter()
        bottom_candidates = Counter()
        sample_limit = min(50, num_pages)
        step = max(1, num_pages // sample_limit)

        for p_idx in range(0, num_pages, step):
            page = doc[p_idx]
            rect = page.rect
            blocks = page.get_text("blocks")
            for b in blocks:
                b_text = b[4].strip()
                if not b_text or len(b_text) > 120:
                    continue
                # top 10%
                if b[1] <= rect.height * 0.12:
                    top_candidates[b_text] += 1
                # bottom 10%
                elif b[3] >= rect.height * 0.88:
                    bottom_candidates[b_text] += 1

        sampled_count = len(range(0, num_pages, step))
        threshold = max(2, int(sampled_count * 0.40))

        repeated_headers = {k for k, v in top_candidates.items() if v >= threshold}
        repeated_footers = {k for k, v in bottom_candidates.items() if v >= threshold}
        repeated_lines = repeated_headers | repeated_footers

        # Step 2: Stream page by page and write JSONL
        temp_out = out_path.with_suffix(".tmp")
        missing_ocr_languages: Set[str] = set()
        pages_needing_ocr = 0

        with open(temp_out, "w", encoding="utf-8") as out_f:
            meta_record = {
                "type": "metadata",
                "file_id": fid,
                "filename": pdf_path.name,
                "sha256": file_sha256,
                "extractor_version": EXTRACTOR_VERSION,
                "pages_count": num_pages,
                "toc": toc,
                "repeated_headers_removed": list(repeated_headers),
                "repeated_footers_removed": list(repeated_footers),
            }
            out_f.write(json.dumps(meta_record, ensure_ascii=False) + "\n")

            for page_idx in range(num_pages):
                page = doc[page_idx]
                page_rect = page.rect
                page_dict = page.get_text("dict")

                spans: List[Dict[str, Any]] = []
                cleaned_text_lines: List[str] = []
                lines_records: List[Dict[str, Any]] = []

                for block in page_dict.get("blocks", []):
                    if block.get("type") == 0:  # Text block
                        raw_block_lines = block.get("lines", [])
                        i = 0
                        while i < len(raw_block_lines):
                            curr_line = raw_block_lines[i]
                            line_spans = curr_line.get("spans", [])
                            line_text = "".join(s.get("text", "") for s in line_spans).strip()

                            if not line_text:
                                i += 1
                                continue

                            # Check header/footer filter
                            bbox = curr_line.get("bbox", [0, 0, 0, 0])
                            is_header_zone = bbox[1] <= page_rect.height * 0.12
                            is_footer_zone = bbox[3] >= page_rect.height * 0.88

                            if (is_header_zone or is_footer_zone) and line_text in repeated_lines:
                                i += 1
                                continue

                            # Check if lone section number e.g. "1.1", "1.2", "2.4" that was split from next line
                            if re.match(r"^\d+(\.\d+){1,3}$", line_text) and i + 1 < len(raw_block_lines):
                                next_line = raw_block_lines[i + 1]
                                next_bbox = next_line.get("bbox", [0, 0, 0, 0])
                                # If on same line or directly adjacent vertically
                                if abs(bbox[1] - next_bbox[1]) < 6.0 or (next_bbox[1] >= bbox[1] and next_bbox[1] - bbox[3] < 8.0):
                                    next_spans = next_line.get("spans", [])
                                    next_text = "".join(s.get("text", "") for s in next_spans).strip()
                                    combined_text = f"{line_text} {next_text}"
                                    combined_spans = line_spans + next_spans
                                    combined_bbox = [
                                        min(bbox[0], next_bbox[0]),
                                        min(bbox[1], next_bbox[1]),
                                        max(bbox[2], next_bbox[2]),
                                        max(bbox[3], next_bbox[3]),
                                    ]
                                    line_text = combined_text
                                    line_spans = combined_spans
                                    bbox = combined_bbox
                                    i += 1  # consumed both

                            cleaned_text_lines.append(line_text)

                            # Clean spans
                            parsed_line_spans = []
                            for sp in line_spans:
                                sp_text = sp.get("text", "")
                                if not sp_text.strip():
                                    continue
                                flags = sp.get("flags", 0)
                                is_bold = bool(flags & 2 or "bold" in sp.get("font", "").lower())
                                sp_dict = {
                                    "text": sp_text,
                                    "size": round(sp.get("size", 0.0), 2),
                                    "bold": is_bold,
                                    "font": sp.get("font", ""),
                                    "bbox": [round(c, 2) for c in sp.get("bbox", [])],
                                }
                                spans.append(sp_dict)
                                parsed_line_spans.append(sp_dict)

                            lines_records.append({
                                "text": line_text,
                                "bbox": [round(c, 2) for c in bbox],
                                "spans": parsed_line_spans,
                            })

                            i += 1

                full_cleaned_text = "\n".join(cleaned_text_lines)
                char_count = len(full_cleaned_text)
                script = detect_script(full_cleaned_text)
                total_c, garb_c, garb_pct = calculate_garbled_metrics(full_cleaned_text)

                method = "native"
                ocr_needed = False
                ocr_lang_needed = None

                # Flag garbled Devanagari/Telugu/Urdu or low text
                if (char_count < 60) or (garb_pct > 15.0):
                    ocr_needed = True
                    pages_needing_ocr += 1

                    if "telugu" in script or (garb_c > 0 and "tel" in pdf_path.name.lower()):
                        ocr_lang_needed = "tel"
                    elif "devanagari" in script or (garb_c > 0 and ("hindi" in pdf_path.name.lower() or "h" == fid[1:2])):
                        ocr_lang_needed = "hin"
                    elif "urdu" in script or ("u" == fid[1:2]):
                        ocr_lang_needed = "urd"
                    else:
                        ocr_lang_needed = "eng"

                    if not self.has_tesseract:
                        missing_ocr_languages.add(ocr_lang_needed)
                        method = "none (ocr_needed)"
                    else:
                        try:
                            tp = page.get_textpage_ocr(language=ocr_lang_needed, full=True)
                            ocr_text = tp.extractText()
                            if len(ocr_text) > char_count:
                                full_cleaned_text = ocr_text
                                char_count = len(full_cleaned_text)
                                method = "ocr"
                        except Exception:
                            missing_ocr_languages.add(ocr_lang_needed)
                            method = "none (ocr_failed)"

                page_record = {
                    "page_no": page_idx + 1,
                    "text": full_cleaned_text,
                    "char_count": char_count,
                    "script": script,
                    "method": method,
                    "ocr_needed": ocr_needed,
                    "ocr_lang_needed": ocr_lang_needed,
                    "garbled_pct": garb_pct,
                    "spans": spans,
                    "lines": lines_records,
                }
                out_f.write(json.dumps(page_record, ensure_ascii=False) + "\n")

        # Atomic rename
        if out_path.exists():
            out_path.unlink()
        temp_out.rename(out_path)

        return {
            "file_id": fid,
            "status": "extracted",
            "pages_extracted": num_pages,
            "pages_needing_ocr": pages_needing_ocr,
            "missing_ocr_languages": list(missing_ocr_languages),
            "sha256": file_sha256,
        }
