"""
EduSim Curriculum Pipeline — Page Extractor
Streams PDF page by page using PyMuPDF (memory-safe).
Extracts:
  - page_no (1-indexed)
  - text
  - char_count
  - script (latin, devanagari, telugu, arabic/urdu, unknown)
  - method (native, ocr, none)
  - status (ok, garbled, needs_ocr)
  - quality_metrics (control_char_ratio, outside_script_ratio, replacement_char_ratio)
  - spans [{text, size, bold, font, bbox}]
  - lines [{text, bbox, spans}] (preserves line structure and stitches split numbers)
  - doc outline (TOC)
Detects and strips repeated headers/footers (>40% of pages at the same position).
Resumable: skips if sha256 and extractor version hash match.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import fitz

from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT

logger = logging.getLogger("EduSim.page_extractor")

EXTRACTOR_VERSION = "2.2.0"
PAGES_DIR = PIPELINE_OUTPUT_ROOT / "pages"
OCR_CACHE_DIR = PIPELINE_OUTPUT_ROOT / "ocr_cache"


def decode_pua_ascii(text: str) -> str:
    """Decodes Adobe/Windows Symbol font PUA glyphs (0xF020-0xF0FF) back to ASCII characters."""
    if not any(0xF020 <= ord(ch) <= 0xF0FF for ch in text):
        return text
    chars = []
    for ch in text:
        cp = ord(ch)
        if 0xF020 <= cp <= 0xF07E:
            chars.append(chr(cp - 0xF000))
        elif cp == 0xF092:
            chars.append("’")
        elif cp == 0xF093:
            chars.append("“")
        elif cp == 0xF094:
            chars.append("”")
        elif cp == 0xF096:
            chars.append("–")
        elif cp == 0xF097:
            chars.append("—")
        else:
            chars.append(ch)
    return "".join(chars)


def normalize_devanagari(text: str) -> str:
    """
    Normalizes Devanagari text:
      - Applies Unicode NFC normalization
      - Deduplicates multiple consecutive viramas (\u094d+)
      - Strips stray ZWJ (\u200d) and ZWNJ (\u200c) around viramas that break conjuncts
      - Repairs duplicated consonants in broken ligatures (e.g. पंक््\u200dतति -> पंक्ति)
      - Cleans isolated zero-width formatting characters (preserving eyelash-ra \u0930\u094d\u200d)
    """
    if not text:
        return text
    # 1. Unicode NFC normalization
    text = unicodedata.normalize("NFC", text)
    # 2. Fix multiple consecutive viramas (halant): e.g. ्् -> ्
    text = re.sub(r"\u094d+", "\u094d", text)
    # 3. Strip stray ZWJ and ZWNJ following or preceding virama
    text = re.sub(r"\u094d[\u200c\u200d]+", "\u094d", text)
    text = re.sub(r"[\u200c\u200d]+\u094d", "\u094d", text)
    # 4. Fix doubled consonants in broken ligatures before matra i (\u093f): e.g. पंक््तति -> पंक्ति
    text = re.sub(r"(\u094d([\u0915-\u0939]))\2\u093f", lambda m: m.group(1) + "\u093f", text)
    # 5. Clean up any remaining isolated zero-width characters not preceded by virama + Ra (eyelash-ra)
    text = re.sub(r"(?<!\u0930\u094d)[\u200c\u200d]", "", text)
    return text


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


def compute_page_quality_metrics(
    text: str,
    expected_lang: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes text quality metrics per page:
      (a) control_char_ratio: ratio of control chars (\x00-\x1f except \n, \t, \r)
      (b) outside_script_ratio: ratio of characters outside expected script for the book's language
      (c) replacement_char_ratio: ratio of replacement (\ufffd) and PUA (\ue000-\uf8ff) chars
    Pages exceeding thresholds get is_garbled=True (status="garbled").
    """
    total = len(text)
    if total == 0:
        return {
            "control_char_ratio": 0.0,
            "outside_script_ratio": 0.0,
            "replacement_char_ratio": 0.0,
            "total_chars": 0,
            "letter_count": 0,
            "is_garbled": False,
            "garbled_reasons": [],
        }

    # (a) Control chars (\x00-\x1f except \n, \t, \r)
    ctrl_count = sum(1 for ch in text if ord(ch) < 32 and ch not in ("\n", "\t", "\r"))
    control_char_ratio = round(ctrl_count / total, 4)

    # (c) Replacement & PUA chars (\ufffd, 0xE000-0xF8FF)
    pua_count = sum(1 for ch in text if ch == "\ufffd" or 0xE000 <= ord(ch) <= 0xF8FF)
    replacement_char_ratio = round(pua_count / total, 4)

    # (b) Outside expected script ratio
    letters = [ch for ch in text if ch.isalpha()]
    letter_count = len(letters)
    outside_script_ratio = 0.0
    lang = (expected_lang or "").strip().lower()

    if letter_count >= 30 and lang:
        if lang in ("tel", "telugu", "te"):
            tel_count = sum(1 for ch in letters if 0x0C00 <= ord(ch) <= 0x0C7F)
            outside_script_ratio = round((letter_count - tel_count) / letter_count, 4)
        elif lang in ("hin", "hindi", "hi", "sa", "sanskrit"):
            hin_count = sum(1 for ch in letters if 0x0900 <= ord(ch) <= 0x097F)
            outside_script_ratio = round((letter_count - hin_count) / letter_count, 4)
        elif lang in ("urd", "urdu", "ur"):
            urd_count = sum(
                1 for ch in letters
                if (0x0600 <= ord(ch) <= 0x06FF or 0x0750 <= ord(ch) <= 0x077F or
                    0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF)
            )
            outside_script_ratio = round((letter_count - urd_count) / letter_count, 4)
        elif lang in ("eng", "english", "en"):
            eng_count = sum(
                1 for ch in letters
                if (0x0041 <= ord(ch) <= 0x005A or 0x0061 <= ord(ch) <= 0x007A or 0x00C0 <= ord(ch) <= 0x024F)
            )
            outside_script_ratio = round((letter_count - eng_count) / letter_count, 4)

    is_garbled = False
    garbled_reasons = []

    if control_char_ratio > 0.02:
        is_garbled = True
        garbled_reasons.append(f"control_chars_high ({control_char_ratio:.2%})")

    if replacement_char_ratio > 0.05:
        is_garbled = True
        garbled_reasons.append(f"replacement_chars_high ({replacement_char_ratio:.2%})")

    # If non-English language has > 50% letters outside expected script
    if lang in ("tel", "telugu", "te", "hin", "hindi", "hi", "sa", "sanskrit", "urd", "urdu", "ur"):
        if letter_count >= 30 and outside_script_ratio > 0.50:
            is_garbled = True
            garbled_reasons.append(f"outside_script_high ({outside_script_ratio:.2%} non-{lang})")

    return {
        "control_char_ratio": control_char_ratio,
        "outside_script_ratio": outside_script_ratio,
        "replacement_char_ratio": replacement_char_ratio,
        "total_chars": total,
        "letter_count": letter_count,
        "is_garbled": is_garbled,
        "garbled_reasons": garbled_reasons,
    }


def resolve_ocr_lang(
    expected_lang: Optional[str],
    detected_script: str,
    filename: str,
    file_id: str,
) -> str:
    lang = (expected_lang or "").strip().lower()
    fn_lower = f"{filename} {file_id}".lower()
    if lang in ("tel", "telugu", "te") or "tel" in fn_lower or detected_script == "telugu":
        return "tel"
    if lang in ("hin", "hindi", "hi", "sa", "sanskrit") or "hindi" in fn_lower or detected_script == "devanagari":
        return "hin"
    if lang in ("urd", "urdu", "ur") or "urdu" in fn_lower or detected_script == "urdu":
        return "urd"
    m = re.match(r"^[a-l]([ehus])", filename.lower())
    if m:
        c = m.group(1)
        if c == "h":
            return "hin"
        if c == "u":
            return "urd"
        if c == "s":
            return "hin"
    return "eng"


def infer_language_from_filename(filename: str) -> str:
    fn_lower = filename.lower()
    if re.search(r"(tel|telugu)", fn_lower) or "_tel_" in fn_lower or "tel" in fn_lower:
        return "tel"
    if re.search(r"(hin|hindi)", fn_lower) or "_hin_" in fn_lower or "hindi" in fn_lower:
        return "hin"
    if re.search(r"(urd|urdu)", fn_lower) or "_urd_" in fn_lower or "urdu" in fn_lower:
        return "urd"
    m = re.match(r"^[a-l]([ehus])", fn_lower)
    if m:
        code = m.group(1)
        if code == "h":
            return "hin"
        if code == "u":
            return "urd"
        if code == "s":
            return "hin"
        if code == "e":
            return "eng"
    return "eng"


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
    def __init__(self, pages_output_dir: Optional[Path] = None, enable_ocr: bool = False):
        self.pages_dir = pages_output_dir or PAGES_DIR
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.enable_ocr = enable_ocr
        self.has_tesseract = shutil.which("tesseract") is not None
        self._warned_no_tesseract = False

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

    def _get_ocr_cache_path(self, file_sha256: str, page_no: int, ocr_lang: str) -> Path:
        return OCR_CACHE_DIR / file_sha256 / f"p_{page_no}_{ocr_lang}.json"

    def is_ocr_cached(self, file_sha256: str, page_no: int, ocr_lang: str) -> bool:
        return self._get_ocr_cache_path(file_sha256, page_no, ocr_lang).exists()

    def _ocr_page_fallback(
        self,
        page: fitz.Page,
        page_no: int,
        ocr_lang: str,
        file_sha256: str,
    ) -> Optional[str]:
        cache_path = self._get_ocr_cache_path(file_sha256, page_no, ocr_lang)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("text")
            except Exception as e:
                logger.warning(f"Failed reading OCR cache {cache_path}: {e}")

        if not self.enable_ocr:
            return None

        if not self.has_tesseract:
            self.has_tesseract = shutil.which("tesseract") is not None

        if not self.has_tesseract:
            if not self._warned_no_tesseract:
                logger.warning(
                    "Tesseract OCR is requested (--ocr) but 'tesseract' executable was not found in PATH.\n"
                    "Please install Tesseract and language packs:\n"
                    "  Debian/Ubuntu: apt install tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin\n"
                    "  Windows: Download installer from UB-Mannheim/tesseract/wiki and add to system PATH."
                )
                self._warned_no_tesseract = True
            return None

        try:
            import pytesseract
            from PIL import Image

            # Rasterize page at 300 DPI
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            lang_map = {
                "tel": "tel",
                "hin": "hin",
                "eng": "eng",
                "urd": "urd",
            }
            tess_lang = lang_map.get(ocr_lang, ocr_lang)

            ocr_text = pytesseract.image_to_string(img, lang=tess_lang)
            if ocr_lang in ("hin", "sa"):
                ocr_text = normalize_devanagari(ocr_text)

            # Cache per PDF sha256
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "file_sha256": file_sha256,
                        "page_no": page_no,
                        "lang": ocr_lang,
                        "text": ocr_text,
                        "success": True,
                    },
                    f,
                    ensure_ascii=False,
                )
            return ocr_text
        except Exception as e:
            logger.warning(f"OCR failed for page {page_no} with lang {ocr_lang}: {e}")
            return None

    def extract_file(
        self,
        pdf_path: Path,
        file_id: Optional[str] = None,
        force: bool = False,
        expected_lang: Optional[str] = None,
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

        if not expected_lang:
            expected_lang = infer_language_from_filename(fid)

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
        pages_garbled = 0
        pages_passed = 0

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
                            line_text = decode_pua_ascii("".join(s.get("text", "") for s in line_spans).strip())

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
                                sp_text = decode_pua_ascii(sp.get("text", ""))
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

                # Normalize Devanagari text if language/script indicates Devanagari
                if expected_lang in ("hin", "hindi", "hi", "sa", "sanskrit") or detect_script(full_cleaned_text) == "devanagari":
                    full_cleaned_text = normalize_devanagari(full_cleaned_text)
                    for lr in lines_records:
                        lr["text"] = normalize_devanagari(lr["text"])

                char_count = len(full_cleaned_text)
                script = detect_script(full_cleaned_text)
                total_c, garb_c, garb_pct = calculate_garbled_metrics(full_cleaned_text)
                quality_metrics = compute_page_quality_metrics(full_cleaned_text, expected_lang=expected_lang)
                is_garbled = quality_metrics["is_garbled"]

                method = "native"
                ocr_needed = False
                ocr_lang_needed = resolve_ocr_lang(expected_lang, script, pdf_path.name, fid)
                status = "ok"

                # Check text-quality gate: garbled or low character count
                if is_garbled or (char_count < 60) or (garb_pct > 15.0):
                    ocr_needed = True
                    status = "garbled" if (is_garbled or garb_pct > 15.0) else "needs_ocr"

                    # OCR fallback attempt (if enabled or cached)
                    if self.enable_ocr or self.is_ocr_cached(file_sha256, page_idx + 1, ocr_lang_needed):
                        ocr_text = self._ocr_page_fallback(page, page_idx + 1, ocr_lang_needed, file_sha256)
                        if ocr_text:
                            ocr_text_clean = ocr_text.strip()
                            if ocr_lang_needed in ("hin", "sa"):
                                ocr_text_clean = normalize_devanagari(ocr_text_clean)
                            ocr_metrics = compute_page_quality_metrics(ocr_text_clean, expected_lang=expected_lang)
                            if not ocr_metrics["is_garbled"] and len(ocr_text_clean) >= 30:
                                full_cleaned_text = ocr_text_clean
                                char_count = len(full_cleaned_text)
                                script = detect_script(full_cleaned_text)
                                method = "ocr"
                                status = "ok"
                                ocr_needed = False
                                quality_metrics = ocr_metrics
                                garb_pct = ocr_metrics.get("replacement_char_ratio", 0.0) * 100.0

                    if ocr_needed:
                        pages_needing_ocr += 1
                        missing_ocr_languages.add(ocr_lang_needed)
                        if method == "native":
                            method = "none (ocr_needed)"

                if status == "garbled":
                    pages_garbled += 1
                elif status == "ok":
                    pages_passed += 1

                page_record = {
                    "page_no": page_idx + 1,
                    "text": full_cleaned_text,
                    "char_count": char_count,
                    "script": script,
                    "method": method,
                    "status": status,
                    "ocr_needed": ocr_needed,
                    "ocr_lang_needed": ocr_lang_needed,
                    "garbled_pct": garb_pct,
                    "quality_metrics": quality_metrics,
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
            "pages_garbled": pages_garbled,
            "pages_passed": pages_passed,
            "missing_ocr_languages": list(missing_ocr_languages),
            "sha256": file_sha256,
        }

    def extract_batch_parallel(
        self,
        tasks: List[Tuple[Any, ...]],
        workers: int = 4,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """Extracts a batch of PDF files in parallel using ProcessPoolExecutor."""
        from concurrent.futures import ProcessPoolExecutor

        if workers <= 1:
            res = []
            for item in tasks:
                p = item[0]
                fid = item[1]
                exp_lang = item[2] if len(item) > 2 else None
                res.append(self.extract_file(p, fid, force=force, expected_lang=exp_lang))
            return res

        args_list = [
            (
                str(item[0]),
                item[1],
                force,
                str(self.pages_dir),
                self.enable_ocr,
                item[2] if len(item) > 2 else None,
            )
            for item in tasks
        ]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_extract_file_worker, args_list))
        return results


def _extract_file_worker(args: Tuple[str, str, bool, str, bool, Optional[str]]) -> Dict[str, Any]:
    """Top-level picklable worker for parallel PDF extraction across processes."""
    pdf_path_str, file_id, force, output_dir_str, enable_ocr, exp_lang = args
    out_dir = Path(output_dir_str) if output_dir_str else None
    extractor = PageExtractor(pages_output_dir=out_dir, enable_ocr=enable_ocr)
    return extractor.extract_file(Path(pdf_path_str), file_id=file_id, force=force, expected_lang=exp_lang)
