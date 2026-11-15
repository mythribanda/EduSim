"""
EduSim Curriculum Pipeline — Main Extractor Engine
Orchestrates:
  Step A: Catalog gaps resolution
  Step B: Page extraction
  Step C: Style profiling
  Step D & E: Chapter & Node hierarchy extraction via subject adapters
  Step F: Coverage proof
  Step G: Outputs writing (book JSON, combined curriculum.json, extraction_report.csv, review_queue.csv)
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from curriculum_pipeline.adapters.specialized_adapters import get_adapter_for_subject
from curriculum_pipeline.coverage_prover import CoverageProver
from curriculum_pipeline.page_extractor import PageExtractor
from curriculum_pipeline.pipeline_config import (
    NCERT_PATTERN,
    PIPELINE_OUTPUT_ROOT,
    TEXTBOOKS_DIR,
    parse_ncert_filename,
    safe_int,
    normalize_unicode_numerals,
    is_numeric_numeral,
)
from curriculum_pipeline.style_profiler import StyleProfiler
from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

CURRICULUM_OUT_DIR = PIPELINE_OUTPUT_ROOT / "curriculum"
BOOKS_OUT_DIR = CURRICULUM_OUT_DIR / "books"
REPORTS_OUT_DIR = PIPELINE_OUTPUT_ROOT / "reports"

WORD_TO_NUM: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

ROMAN_TO_NUM: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}


class CurriculumExtractorEngine:
    def __init__(self, textbooks_dir: Optional[Path] = None, resume: bool = True, workers: int = 1, enable_ocr: bool = False):
        self.textbooks_dir = textbooks_dir or TEXTBOOKS_DIR
        self.resume = resume
        self.workers = max(1, workers)
        self.enable_ocr = enable_ocr
        self.page_extractor = PageExtractor(enable_ocr=enable_ocr)
        self.style_profiler = StyleProfiler()
        self.coverage_prover = CoverageProver()

        BOOKS_OUT_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_OUT_DIR.mkdir(parents=True, exist_ok=True)

        self.preflight_by_file: Dict[str, Dict[str, Any]] = {}
        preflight_csv = REPORTS_OUT_DIR / "preflight.csv"
        if preflight_csv.exists():
            try:
                with open(preflight_csv, "r", encoding="utf-8") as pf:
                    for row in csv.DictReader(pf):
                        self.preflight_by_file[row["file"]] = row
            except Exception:
                pass

    def extract_ncert_chapter_title_from_p1(self, pages: List[Dict[str, Any]], ch_no: int) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extracts chapter title and wrapper (Unit/Theme) from first page(s).
        Merges consecutive title-sized lines when they share font size/weight and are vertically adjacent.
        """
        if not pages:
            return f"Chapter {ch_no}", None, None

        p1 = pages[0]
        wrapper = None
        lines_data = p1.get("lines", [])

        # Extract wrapper (Unit/Theme/Lesson etc.)
        for l in lines_data:
            txt = l.get("text", "").strip()
            m_wrap = re.match(r"^(Unit|Theme|Lesson|इकाई|पाठ)\s*([A-Za-z0-9]+)?", txt, re.I)
            if m_wrap:
                wrapper = txt
                break
        if not wrapper:
            for l in [l.strip() for l in p1.get("text", "").splitlines() if l.strip()]:
                m_wrap = re.match(r"^(Unit|Theme|Lesson|इकाई|पाठ)\s*([A-Za-z0-9]+)?", l, re.I)
                if m_wrap:
                    wrapper = l
                    break

        if not lines_data:
            spans = p1.get("spans", [])
            if spans:
                sorted_spans = sorted(spans, key=lambda s: s.get("size", 0.0), reverse=True)
                for sp in sorted_spans:
                    txt = sp.get("text", "").strip()
                    if len(txt) > 3 and not re.match(r"^(Chapter|Unit|Theme|CHAPTER|\d+)\b", txt, re.I):
                        return txt, wrapper, None
            return f"Chapter {ch_no}", wrapper, None

        # Filter lines for title candidates
        candidate_lines = []
        for l_idx, l in enumerate(lines_data):
            txt = l.get("text", "").strip()
            if not txt or len(txt) < 3:
                continue
            if re.match(r"^(Chapter|Unit|Theme|Lesson|CHAPTER|UNIT|\d+)\b", txt, re.I):
                continue
            if any(x in txt.lower() for x in ["reprint", "national council", "ncert", "isbn", "preface", "textbook"]):
                continue
            candidate_lines.append(l)

        if not candidate_lines:
            return f"Chapter {ch_no}", wrapper, None

        # Pick largest font size among candidate lines
        def get_line_size(l):
            spans = l.get("spans", [])
            return max((s.get("size", 0.0) for s in spans), default=0.0)

        candidate_lines.sort(key=get_line_size, reverse=True)
        top_line = candidate_lines[0]
        top_size = get_line_size(top_line)

        # Merge vertically adjacent lines that share size within 1.0pt
        title_parts = [top_line.get("text", "").strip()]
        top_bbox = top_line.get("bbox", [0, 0, 0, 0])

        for other in candidate_lines[1:]:
            o_size = get_line_size(other)
            if abs(o_size - top_size) <= 1.0:
                o_bbox = other.get("bbox", [0, 0, 0, 0])
                # Check vertical proximity
                if abs(o_bbox[1] - top_bbox[3]) < 25.0 or abs(top_bbox[1] - o_bbox[3]) < 25.0:
                    title_parts.append(other.get("text", "").strip())

        merged_title = " ".join(title_parts).strip()
        return merged_title, wrapper, None

    def detect_ncert_chapters(
        self,
        pdf_path: Path,
        pages: List[Dict[str, Any]],
        meta_rec: Dict[str, Any],
        book_title: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Detects chapter boundaries in whole-book NCERT PDFs using bookmarks,
        printed TOC, and page text heading markers.
        """
        total_pages = len(pages)
        if total_pages == 0:
            return []

        # 1. Check doc TOC / bookmarks
        toc_outline = meta_rec.get("toc", [])
        if not toc_outline and pdf_path.exists():
            try:
                doc = fitz.open(pdf_path)
                toc_outline = doc.get_toc()
            except Exception:
                toc_outline = []

        if toc_outline:
            ch_bookmarks = []
            for e in toc_outline:
                lvl, title, pno = e[0], e[1].strip(), e[2]
                if pno <= 0 or pno > total_pages:
                    continue
                if any(x in title.lower() for x in ["initial", "total book", "prelim", "appendix", "cover", "title page", "contents", "preface"]):
                    continue
                if title in ("00", "0", ""):
                    continue
                if re.match(r"^(chapter|unit|theme|lesson|part|पाठ|अध्याय|इकाई)\b", title, re.I) or re.match(r"^[a-z]{4}\d{3}", title, re.I):
                    ch_bookmarks.append((title, pno))
                elif lvl == 1 and not title.endswith(".pdf"):
                    ch_bookmarks.append((title, pno))

            if len(ch_bookmarks) >= 2:
                sorted_bm = sorted(ch_bookmarks, key=lambda x: x[1])
                dedup = []
                for b in sorted_bm:
                    if not dedup or b[1] - dedup[-1][1] >= 2:
                        dedup.append(b)
                if len(dedup) >= 2:
                    ranges = []
                    for i, (b_title, b_start) in enumerate(dedup):
                        b_end = dedup[i + 1][1] - 1 if i + 1 < len(dedup) else total_pages
                        b_end = max(b_start, min(b_end, total_pages))
                        m_num = re.search(r"\b(\d+)\b", b_title)
                        num_str = m_num.group(1) if m_num else str(i + 1)
                        clean_t = re.sub(r"^(chapter|unit|theme)\s*([0-9a-zA-Z]+)?\s*[:\.\-–—]\s*", "", b_title, flags=re.I).strip()
                        ranges.append({
                            "official_number": num_str,
                            "official_title": clean_t or b_title,
                            "page_start": b_start,
                            "page_end": b_end,
                            "wrapper": None,
                            "detection_method": "outline",
                        })
                    return ranges

        # 2. Check for printed Table of Contents in first 15 pages
        printed_toc: Dict[int, str] = {}
        for p in pages[:15]:
            p_text = p.get("text", "")
            if any(k in p_text.lower() for k in ["contents", "index", "विषय-सूची", "विषय सूची", "table of contents"]):
                lines = [l.strip() for l in p_text.splitlines() if l.strip()]
                for l in lines:
                    m = re.match(r"^(?:Chapter\s*)?(\d{1,2})[\.\s]+([A-Za-z\u0900-\u097F].*)$", l)
                    if m and int(m.group(1)) <= 35:
                        cnum = int(m.group(1))
                        ctitle = re.sub(r"[\.\s\-\d]+$", "", m.group(2)).strip()
                        if len(ctitle) > 2 and ctitle.lower() not in ["page", "class", "chapter"]:
                            printed_toc[cnum] = ctitle

        # 3. Full page scan across the entire book
        chapter_starts = []
        seen_pages = set()

        for p_idx, p in enumerate(pages):
            pno = p.get("page_no", p_idx + 1)
            lines_data = p.get("lines", [])
            lines = [l.get("text", "").strip() if isinstance(l, dict) else str(l).strip() for l in lines_data]
            if not lines:
                lines = [l.strip() for l in p.get("text", "").splitlines() if l.strip()]
            if not lines:
                continue

            found_ch = None

            # 3A. Standalone large digit span (NCERT primary math books like aejm, bejm)
            spans = p.get("spans", [])
            for sp in spans:
                sz = sp.get("size", 0.0)
                if sz >= 30.0:
                    txt = sp.get("text", "").strip()
                    val = safe_int(txt)
                    if val is not None and 1 <= val <= 30:
                        c_num = val
                        # Gather title candidate spans on same page
                        title_parts = []
                        for other in spans:
                            o_txt = other.get("text", "").strip()
                            o_sz = other.get("size", 0.0)
                            if o_sz >= 20.0 and not is_numeric_numeral(o_txt) and len(o_txt) > 2:
                                if not any(x in o_txt.lower() for x in ["class", "reprint", "ncert", "unit", "chapter"]):
                                    title_parts.append(o_txt)
                        title = " ".join(title_parts).strip() or f"Chapter {c_num}"
                        found_ch = (str(c_num), title, pno, None)
                        break

            if not found_ch:
                for idx, line in enumerate(lines):
                    # Ignore inline cross-references
                    if any(x in line.lower() for x in ["class xi", "class xii", "see chapter", "last chapter", "next chapter", "refer to", "equation", "eq."]):
                        continue

                    # A. 'Chapter 1' / 'Chapter One'
                    m1 = re.match(r"^(?:Chapter|CHAPTER)\s+([0-9\u0660-\u0669\u0966-\u096f\u0c66-\u0c6f\u00b2\u00b3\u00b9\u2070-\u2079\u2080-\u2089]+|[a-zA-Z]+)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line)
                    if m1 and (not m1.group(2) or len(m1.group(2)) < 60):
                        raw_num = m1.group(1).lower()
                        val_num = safe_int(raw_num)
                        if raw_num in WORD_TO_NUM or val_num is not None:
                            c_num = WORD_TO_NUM.get(raw_num) or (val_num if val_num is not None else raw_num.upper())
                            rest = m1.group(2).strip()
                            title = rest
                            if not title and idx + 1 < len(lines):
                                cand = lines[idx + 1]
                                if len(cand) > 2 and not is_numeric_numeral(cand) and not cand.lower().startswith("unit"):
                                    title = cand
                            if not title and idx > 0:
                                cand = lines[idx - 1]
                                if len(cand) > 2 and not is_numeric_numeral(cand):
                                    title = cand
                            found_ch = (str(c_num), title or f"Chapter {c_num}", pno, None)
                            break

                    # A2. Line is 'Chapter' alone and preceding/next line is number (e.g. fecu.pdf)
                    if line.strip() in ("Chapter", "CHAPTER"):
                        c_num = None
                        title = None
                        if idx > 0 and is_numeric_numeral(lines[idx - 1]):
                            c_num = safe_int(lines[idx - 1])
                            title = lines[idx - 2] if idx > 1 else None
                        elif idx + 1 < len(lines) and is_numeric_numeral(lines[idx + 1]):
                            c_num = safe_int(lines[idx + 1])
                            title = lines[idx + 2] if idx + 2 < len(lines) else None
                        if c_num and c_num <= 35:
                            found_ch = (str(c_num), title or f"Chapter {c_num}", pno, None)
                            break

                    # B. Hindi: पाठ / अध्याय / इकाई
                    m_hi = re.match(r"^(पाठ|अध्याय|इकाई)\s*([0-9\u0966-\u096f]+)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line)
                    if m_hi:
                        lbl = m_hi.group(1)
                        raw_c_num = m_hi.group(2)
                        val_c_num = safe_int(raw_c_num)
                        c_num = str(val_c_num if val_c_num is not None else raw_c_num)
                        h_rest = m_hi.group(3).strip()
                        h_title = h_rest or (lines[idx + 1] if idx + 1 < len(lines) else f"{lbl} {c_num}")
                        found_ch = (c_num, h_title, pno, f"{lbl} {c_num}")
                        break

                    # C. Section X.1 marker: e.g. '1.1 Introduction', '2.1 Introduction'
                    m_sec = re.match(r"^(\d{1,2})\.1\.?\s+([A-Za-z\u0900-\u097F].*)$", line)
                    if m_sec:
                        sec_num = safe_int(m_sec.group(1))
                        if sec_num and sec_num <= 35:
                            c_num = str(sec_num)
                            t = printed_toc.get(sec_num)
                            if not t and idx > 0:
                                cand = lines[idx - 1]
                                if len(cand) > 2 and not is_numeric_numeral(cand) and not re.match(r"^\d+\.", cand):
                                    t = cand
                            if any(x in (t or "").lower() for x in ["exercise", "exercises", "summary", "points to ponder", "additional exercise", "question", "questions"]):
                                continue
                            found_ch = (c_num, t or f"Chapter {c_num}", pno, None)
                            break

                    # D. 'Unit N' / 'Theme N'
                    m_unit = re.match(r"^(?:UNIT|THEME|Theme)\s+([0-9IVX]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line)
                    if m_unit:
                        raw_u = m_unit.group(1).lower()
                        val_u = safe_int(raw_u)
                        u_num = WORD_TO_NUM.get(raw_u) or ROMAN_TO_NUM.get(m_unit.group(1).upper()) or (val_u if val_u is not None else raw_u)
                        u_rest = m_unit.group(2).strip()
                        title = u_rest or (lines[idx + 1] if idx + 1 < len(lines) else f"Theme {u_num}")
                        found_ch = (str(u_num), title, pno, line)
                        break

            if found_ch and pno not in seen_pages:
                c_num_val, c_title_val, c_pno_val, c_wrap_val = found_ch
                if not any(x in (c_title_val or "").lower() for x in ["exercise", "exercises", "summary", "points to ponder", "additional exercise"]):
                    seen_pages.add(pno)
                    chapter_starts.append(found_ch)

        if chapter_starts:
            chapter_starts = sorted(chapter_starts, key=lambda x: x[2])
            deduped = []
            seen_cnums = {}
            for cs in chapter_starts:
                c_num_str = cs[0]
                if c_num_str in seen_cnums and (cs[2] - seen_cnums[c_num_str] < 20):
                    continue
                if not deduped or cs[2] - deduped[-1][2] >= 2:
                    seen_cnums[c_num_str] = cs[2]
                    deduped.append(cs)

            ranges = []
            for i, (c_num, c_title, c_start, c_wrap) in enumerate(deduped):
                c_end = deduped[i + 1][2] - 1 if i + 1 < len(deduped) else total_pages
                c_end = max(c_start, min(c_end, total_pages))
                clean_title = c_title if not c_title.startswith(f"Chapter {c_num}: ") else c_title.replace(f"Chapter {c_num}: ", "")
                ranges.append({
                    "official_number": str(c_num),
                    "official_title": clean_title,
                    "page_start": c_start,
                    "page_end": c_end,
                    "wrapper": c_wrap,
                    "detection_method": "scan",
                })
            return ranges

        return [{
            "official_number": "1",
            "official_title": book_title or "Chapter 1",
            "page_start": 1,
            "page_end": total_pages,
            "wrapper": None,
            "detection_method": "single",
        }]

    def process_ncert_book(
        self,
        book_info: Dict[str, Any],
        file_entries: List[Dict[str, Any]],
        review_queue: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        book_code = book_info["book_code"]
        subject = book_info["subject"]
        medium = book_info["medium"]
        book_title = book_info["book_title"]
        cls = book_info["class"]

        # Resume support: check if already successfully extracted
        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        if self.resume and book_json_path.exists():
            try:
                with open(book_json_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("extraction_status") in ("ok", "flagged", "skipped_garbled") and cached.get("chapters"):
                    cached["title"] = book_title
                    cached["book_title"] = book_title
                    cached["subject"] = subject
                    cached["class"] = cls
                    cached["medium"] = medium
                    return cached
            except Exception:
                pass

        file_entries = [fe if isinstance(fe, dict) else {"file": str(fe)} for fe in file_entries]
        jsonl_files = []
        source_shas = []
        missing_langs = set()

        file_entries_sorted = file_entries

        # Check text quality from preflight
        book_tq = "ok"
        tq_reason = ""
        for fe in file_entries_sorted:
            fn = fe.get("file", "") if isinstance(fe, dict) else str(fe)
            pf = self.preflight_by_file.get(fn)
            if pf and pf.get("classification") != "ok":
                if medium.lower() == "english" and pf.get("classification") == "legacy_encoding":
                    continue
                book_tq = pf.get("classification")
                tq_reason = pf.get("notes", "")
                break

        if book_tq != "ok":
            print(f"  [SKIP] Skipping {book_code} ({book_title}) due to text_quality='{book_tq}' ({tq_reason})")
            coverage_proof = self.coverage_prover.prove_coverage(
                book_code=book_code,
                chapters=[],
                pages_records=[],
                expected_chapters_count=0,
                is_flagged_book=True,
            )
            result = {
                "book_code": book_code,
                "board": "ncert",
                "class": cls,
                "subject": subject,
                "medium": medium,
                "book_title": book_title,
                "adapter": "none",
                "source_files": [fe.get("file", str(fe)) if isinstance(fe, dict) else str(fe) for fe in file_entries_sorted],
                "source_sha256": "",
                "text_quality": book_tq,
                "extraction_status": f"skipped_{book_tq}",
                "notes": tq_reason,
                "total_pages": sum(int(fe.get("pages", 0)) if isinstance(fe, dict) else 0 for fe in file_entries_sorted),
                "chapters": [],
                "coverage_proof": coverage_proof,
            }
            b_out = BOOKS_OUT_DIR / f"{book_code}.json"
            with open(b_out, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result

        tasks = []
        for entry in file_entries_sorted:
            fn = entry.get("file", "") if isinstance(entry, dict) else str(entry)
            rel = entry.get("rel_path") if isinstance(entry, dict) else None
            if rel and (self.textbooks_dir / rel).exists():
                pdf_path = self.textbooks_dir / rel
            else:
                cand1 = self.textbooks_dir / "ncert books" / fn
                cand2 = self.textbooks_dir / "ncert books" / "language" / fn
                pdf_path = cand2 if cand2.exists() else cand1

            tasks.append((pdf_path, fn, medium))
            out_jsonl = self.page_extractor.get_output_path(fn)
            jsonl_files.append(out_jsonl)

        if self.workers > 1:
            batch_results = self.page_extractor.extract_batch_parallel(tasks, workers=self.workers, force=not self.resume)
        else:
            batch_results = [self.page_extractor.extract_file(p, fid, force=not self.resume, expected_lang=exp_lang) for p, fid, exp_lang in tasks]

        for extract_res in batch_results:
            if extract_res.get("sha256"):
                source_shas.append(extract_res["sha256"])
            for ml in extract_res.get("missing_ocr_languages", []):
                missing_langs.add(ml)

        # Style profile
        style_profile = self.style_profiler.profile_book(book_code, jsonl_files, force=not self.resume)
        adapter = get_adapter_for_subject(subject, style_profile, language=medium)

        tree_builder = CurriculumTreeBuilder(book_code)
        chapters: List[Dict[str, Any]] = []
        all_book_pages: List[Dict[str, Any]] = []

        # Whole-book NCERT PDF handling (Single PDF containing multiple chapters)
        if len(file_entries_sorted) == 1:
            entry = file_entries_sorted[0]
            fn = entry.get("file", "") if isinstance(entry, dict) else str(entry)
            j_path = jsonl_files[0]
            pages: List[Dict[str, Any]] = []
            meta_rec: Dict[str, Any] = {}

            if j_path.exists():
                with open(j_path, "r", encoding="utf-8") as jf:
                    for line in jf:
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        if rec.get("type") == "metadata":
                            meta_rec = rec
                        else:
                            pages.append(rec)

            pages.sort(key=lambda p: p.get("page_no", 1))
            all_book_pages = pages
            pdf_path_book = tasks[0][0]

            # Detect chapter ranges in whole book
            chapter_ranges = self.detect_ncert_chapters(pdf_path_book, pages, meta_rec, book_title)

            for ch_idx, c_info in enumerate(chapter_ranges):
                ch_num = c_info["official_number"]
                ch_title = c_info["official_title"]
                ch_start = c_info["page_start"]
                ch_end = c_info["page_end"]
                wrapper = c_info.get("wrapper")

                ch_pages = [p for p in pages if ch_start <= p.get("page_no", 1) <= ch_end]
                if not ch_pages:
                    continue

                # Check mini-toc on ch_start
                toc_sec_list = []
                for p in ch_pages:
                    if p.get("page_no", 1) == ch_start:
                        for l in p.get("lines", []):
                            m = re.match(r"^(\d+\.\d+)\s+", l.get("text", "").strip())
                            if m:
                                toc_sec_list.append(m.group(1))
                        break
                toc_sec_nums = set(toc_sec_list)
                has_mini_toc = (len(toc_sec_nums) >= 3) or (len(toc_sec_nums) >= 2 and len(toc_sec_list) > len(toc_sec_nums))

                effective_ch_num = str(ch_num)
                adapter.reset_chapter_state(chapter_number=effective_ch_num)
                raw_candidates = []

                for p in ch_pages:
                    page_actual = p.get("page_no", 1)
                    method = p.get("method", "")
                    garbled_ratio = p.get("garbled_ratio", 0.0)
                    garbled_pct = p.get("garbled_pct", 0.0)
                    ocr_needed = p.get("ocr_needed", False)

                    if "ocr_needed" in str(method) or ocr_needed or garbled_ratio > 0.05 or garbled_pct > 5.0:
                        continue

                    lines_data = p.get("lines", [])
                    if has_mini_toc and page_actual == ch_start and lines_data:
                        seen_sec_nums = set()
                        filtered_lines = []
                        for l in lines_data:
                            m = re.match(r"^(\d+\.\d+)\s+", l.get("text", "").strip())
                            if m and m.group(1) in toc_sec_nums:
                                if m.group(1) not in seen_sec_nums:
                                    seen_sec_nums.add(m.group(1))
                                    continue
                            filtered_lines.append(l)
                        lines_data = filtered_lines

                    if lines_data:
                        nodes = adapter.extract_nodes_from_lines(page_actual, lines_data)
                    else:
                        nodes = adapter.extract_nodes_from_lines(page_actual, [{"text": l, "spans": p.get("spans", [])} for l in p.get("text", "").splitlines()])
                    raw_candidates.extend(nodes)

                norm_ch_title = re.sub(r"[^\w]", "", ch_title).lower()
                norm_wrapper = re.sub(r"[^\w]", "", str(wrapper or "")).lower()
                ocr_pages_set = {p.get("page_no") for p in ch_pages if p.get("ocr_needed")}
                ch_ocr_needed = bool(ocr_pages_set)

                filtered_candidates = []
                for c in raw_candidates:
                    c_title = c.get("official_title", "")
                    norm_c = re.sub(r"[^\w]", "", c_title).lower()
                    c_page = c.get("page", 0)

                    if c_page == ch_start:
                        if not c.get("official_number"):
                            if norm_c and (norm_c in norm_ch_title or norm_ch_title in norm_c):
                                continue
                            if norm_wrapper and (norm_c in norm_wrapper or norm_wrapper in norm_c):
                                continue
                        if re.match(r"^chapter\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\b", c_title.strip(), re.I):
                            continue

                    if not c.get("official_number"):
                        if norm_c == norm_ch_title or (norm_wrapper and norm_c == norm_wrapper):
                            continue
                    if re.match(r"^chapter\s*\d+$", c_title.strip(), re.I):
                        continue
                    c["ocr_needed"] = c_page in ocr_pages_set
                    c["source_file"] = fn
                    filtered_candidates.append(c)

                ch_node_info = {
                    "id": f"{book_code}_ch_{ch_idx + 1}",
                    "official_number": str(ch_num),
                    "official_title": ch_title,
                    "wrapper": wrapper,
                    "evidence": f"File {fn} - Chapter {ch_num}: {ch_title}",
                    "confidence": 0.95,
                    "rule_id": "rule_ncert_chapter",
                    "source_file": fn,
                    "ocr_needed": ch_ocr_needed,
                }

                chapter_node = tree_builder.build_chapter_tree(
                    chapter_info=ch_node_info,
                    raw_candidates=filtered_candidates,
                    chapter_page_start=ch_start,
                    chapter_page_end=ch_end,
                    review_queue=review_queue,
                    file_id=fn,
                    end_matter_page=adapter.end_matter_page,
                    end_matter_label=getattr(adapter, "end_matter_label", None),
                )
                chapters.append(chapter_node)

            expected_chapters = len(chapter_ranges)

        else:
            # Multi-file NCERT books (where each PDF is a chapter)
            page_offset = 0
            for idx, (entry, j_path) in enumerate(zip(file_entries_sorted, jsonl_files)):
                fn = entry.get("file", "") if isinstance(entry, dict) else str(entry)
                m = NCERT_PATTERN.match(fn)
                ch_no = int(m.group(5)) if m and len(m.groups()) >= 5 and m.group(5) else (idx + 1)

                pages = []
                if j_path.exists():
                    with open(j_path, "r", encoding="utf-8") as jf:
                        for line in jf:
                            if not line.strip():
                                continue
                            rec = json.loads(line)
                            if rec.get("type") == "metadata":
                                continue
                            pages.append(rec)

                ch_pages_count = len(pages)
                if ch_pages_count == 0:
                    continue

                ch_start = page_offset + 1
                ch_end = page_offset + ch_pages_count
                page_offset = ch_end

                for p in pages:
                    shifted_p = dict(p)
                    shifted_p["page_no"] = ch_start + p.get("page_no", 1) - 1
                    all_book_pages.append(shifted_p)

                ch_title, wrapper, conflict_note = self.extract_ncert_chapter_title_from_p1(pages, ch_no)
                effective_ch_num = str(ch_no)
                adapter.reset_chapter_state(chapter_number=effective_ch_num)
                raw_candidates = []

                for p in pages:
                    page_actual = ch_start + p.get("page_no", 1) - 1
                    lines_data = p.get("lines", [])
                    if lines_data:
                        nodes = adapter.extract_nodes_from_lines(page_actual, lines_data)
                    else:
                        nodes = adapter.extract_nodes_from_lines(page_actual, [{"text": l, "spans": p.get("spans", [])} for l in p.get("text", "").splitlines()])
                    raw_candidates.extend(nodes)

                filtered_candidates = []
                for c in raw_candidates:
                    c["source_file"] = fn
                    filtered_candidates.append(c)

                ch_info = {
                    "id": f"{book_code}_ch_{ch_no}",
                    "official_number": str(effective_ch_num),
                    "official_title": ch_title,
                    "wrapper": wrapper,
                    "evidence": f"File {fn} - Chapter {ch_no}: {ch_title}",
                    "confidence": 0.95,
                    "rule_id": "rule_ncert_file_chapter",
                    "source_file": fn,
                    "ocr_needed": False,
                }

                chapter_node = tree_builder.build_chapter_tree(
                    chapter_info=ch_info,
                    raw_candidates=filtered_candidates,
                    chapter_page_start=ch_start,
                    chapter_page_end=ch_end,
                    review_queue=review_queue,
                    file_id=fn,
                    end_matter_page=adapter.end_matter_page,
                    end_matter_label=getattr(adapter, "end_matter_label", None),
                )
                chapters.append(chapter_node)

            expected_chapters = len(file_entries_sorted)

        # Coverage proof
        coverage_proof = self.coverage_prover.prove_coverage(
            book_code=book_code,
            chapters=chapters,
            pages_records=all_book_pages,
            expected_chapters_count=expected_chapters,
        )

        book_curriculum = {
            "book_code": book_code,
            "board": "ncert",
            "class": cls,
            "subject": subject,
            "medium": medium,
            "title": book_title,
            "book_title": book_title,
            "total_pages": coverage_proof.get("pages_total", len(all_book_pages)),
            "extraction_status": "ok",
            "adapter": adapter.adapter_name,
            "source_sha256": source_shas[0] if source_shas else "",
            "source_files": [entry.get("file", str(entry)) if isinstance(entry, dict) else str(entry) for entry in file_entries_sorted],
            "chapters": chapters,
            "coverage_proof": coverage_proof,
        }

        # Write book output
        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        with open(book_json_path, "w", encoding="utf-8") as f:
            json.dump(book_curriculum, f, indent=2, ensure_ascii=False)

        return book_curriculum

    def extract_ssc_printed_toc(self, pdf_path: Path) -> Dict[int, str]:
        """Extracts chapter titles from printed TOC table using PyMuPDF blocks."""
        toc_map: Dict[int, str] = {}
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return toc_map

        months_set = {
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        }
        for pno in range(min(15, len(doc))):
            page = doc[pno]
            txt = page.get_text()
            if "index" in txt.lower() or "contents" in txt.lower():
                blocks = page.get_text("blocks")
                for b in blocks:
                    btext = b[4].strip()
                    lines = [l.strip() for l in btext.splitlines() if l.strip()]
                    if not lines:
                        continue
                    m = re.match(r"^0?(\d{1,2})$", lines[0])
                    if m:
                        c_num = int(m.group(1))
                        title_parts = []
                        for l in lines[1:]:
                            if l.isdigit() or re.match(r"^\d+\s*[-–—]\s*\d+$", l):
                                continue
                            if any(mth in l.lower() for mth in months_set):
                                continue
                            if re.match(r"^(june|july|august|september|october|november|december)", l.lower()):
                                continue
                            title_parts.append(l)
                        clean_title = " ".join(title_parts).strip()
                        if clean_title and len(clean_title) > 2:
                            toc_map[c_num] = clean_title
                    elif "mathematical modelling" in btext.lower():
                        toc_map[15] = "Mathematical Modelling"
                if toc_map:
                    break
        return toc_map

    def process_ssc_book(
        self,
        book_info: Dict[str, Any],
        entry: Dict[str, Any],
        review_queue: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        book_code = book_info["book_code"]
        fn = entry.get("file", "") if isinstance(entry, dict) else str(entry)
        rel = entry.get("rel_path") if isinstance(entry, dict) else None

        if rel and (self.textbooks_dir / rel).exists():
            pdf_path = self.textbooks_dir / rel
        else:
            pdf_path = self.textbooks_dir / "Text Books" / fn

        subject = book_info["subject"]
        medium = book_info["medium"]
        book_title = book_info["book_title"]
        cls = book_info["class"]

        # Resume support: check if already successfully extracted
        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        if self.resume and book_json_path.exists():
            try:
                with open(book_json_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("extraction_status") == "ok" and cached.get("chapters"):
                    cached["title"] = book_title
                    cached["book_title"] = book_title
                    cached["subject"] = subject
                    cached["class"] = cls
                    cached["medium"] = medium
                    return cached
                elif cached.get("extraction_status") in ("skipped_corrupted", "skipped_errata"):
                    return cached
            except Exception:
                pass

        # Check preflight text quality
        pf = self.preflight_by_file.get(fn)
        ssc_tq = pf.get("classification", "ok") if pf else "ok"
        tq_reason = pf.get("notes", "") if pf else ""

        is_corrupted = (pdf_path.exists() and pdf_path.stat().st_size == 0)
        is_errata = "errata" in fn.lower()
        is_flagged = is_corrupted or is_errata

        if is_flagged:
            status = "skipped_corrupted" if is_corrupted else "skipped_errata"
            tq = "unreadable" if is_corrupted else "errata"
            reason = "Zero-byte corrupted file" if is_corrupted else "Errata file"

            print(f"  [SKIP] Skipping SSC book {book_code} ({book_title}) due to text_quality='{tq}' / flagged ({reason})")
            coverage_proof = self.coverage_prover.prove_coverage(
                book_code=book_code,
                chapters=[],
                pages_records=[],
                expected_chapters_count=0,
                is_flagged_book=True,
            )
            result = {
                "book_code": book_code,
                "board": "ssc",
                "class": cls,
                "subject": subject,
                "medium": medium,
                "book_title": book_title,
                "adapter": "none",
                "source_files": [fn],
                "source_sha256": entry.get("sha256", ""),
                "text_quality": tq,
                "extraction_status": status,
                "notes": reason,
                "chapters": [],
                "coverage_proof": coverage_proof,
            }
            b_out = BOOKS_OUT_DIR / f"{book_code}.json"
            with open(b_out, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return result

        # Extract pages
        extract_res = self.page_extractor.extract_file(pdf_path, file_id=fn, force=not self.resume, expected_lang=medium)
        j_path = self.page_extractor.get_output_path(fn)

        pages: List[Dict[str, Any]] = []
        meta_rec: Dict[str, Any] = {}
        if j_path.exists():
            with open(j_path, "r", encoding="utf-8") as jf:
                for line in jf:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("type") == "metadata":
                        meta_rec = rec
                    else:
                        pages.append(rec)

        # Style profile
        style_profile = self.style_profiler.profile_book(book_code, [j_path], force=not self.resume)
        adapter = get_adapter_for_subject(subject, style_profile, language=medium)

        # Chapter boundaries detection
        toc_outline = meta_rec.get("toc", [])
        chapter_ranges: List[Tuple[str, int, int, str]] = []

        if toc_outline:
            l1 = [
                e for e in toc_outline
                if e[0] == 1
                and e[2] > 0
                and not any(x in e[1].lower() for x in ["initial", "total book", "prelim", "appendix", "cover", "contents", "index"])
                and not e[1].strip().lower().startswith("00")
                and e[1].strip() != "0"
            ]
            for i, entry_toc in enumerate(l1):
                t_title = entry_toc[1].strip()
                t_start = entry_toc[2]
                t_end = l1[i + 1][2] - 1 if i + 1 < len(l1) else len(pages)
                t_end = max(t_start, min(t_end, len(pages)))
                chapter_ranges.append((t_title, t_start, t_end, "outline"))

        if not chapter_ranges:
            for p in pages:
                p_no = p.get("page_no", 1)
                for line in p.get("text", "").splitlines():
                    line_s = line.strip()
                    if re.match(r"^(Chapter|Lesson|Unit|PART)\s*([0-9IVX]+)", line_s, re.I):
                        chapter_ranges.append((line_s, p_no, p_no, "body_style"))
            adjusted = []
            for i, cr in enumerate(chapter_ranges):
                c_end = chapter_ranges[i + 1][1] - 1 if i + 1 < len(chapter_ranges) else len(pages)
                adjusted.append((cr[0], cr[1], max(cr[1], c_end), "body_style"))
            chapter_ranges = adjusted

        if not chapter_ranges:
            chapter_ranges = [(book_title, 1, len(pages), "fallback_single_chapter")]

        printed_toc_map = self.extract_ssc_printed_toc(pdf_path)
        months_set = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}

        tree_builder = CurriculumTreeBuilder(book_code)
        chapters: List[Dict[str, Any]] = []

        for idx, (c_title, c_start, c_end, c_src) in enumerate(chapter_ranges):
            clean_ch_title = c_title.strip()
            # Strip trailing .pdf
            clean_ch_title = re.sub(r"\.pdf$", "", clean_ch_title, flags=re.I).strip()
            # If title starts with a number like "01 kakku" or "1 TITALI AUR KALI", strip the leading chapter number
            m_lead = re.match(r"^0?(\d{1,2})\s*[-–—_.]?\s*(.+)$", clean_ch_title)
            lead_num = None
            if m_lead and len(m_lead.group(2).strip()) > 1:
                lead_num = str(safe_int(m_lead.group(1)) or (idx + 1))
                clean_ch_title = m_lead.group(2).strip()

            ch_idx = idx + 1
            is_bad_outline = (
                not clean_ch_title
                or clean_ch_title.endswith(".pdf")
                or clean_ch_title.isdigit()
                or re.match(r"^(lesson|unit|chapter)[-_ ]?\d+(\.pdf)?$", clean_ch_title, re.I)
            )

            if is_bad_outline and ch_idx in printed_toc_map:
                cand_t = printed_toc_map[ch_idx]
                if not any(m in cand_t.lower() for m in months_set) and len(cand_t) > 3:
                    clean_ch_title = cand_t
                    is_bad_outline = False

            norm_lower = clean_ch_title.strip().lower()
            if norm_lower in ["answers", "answer", "solutions", "revision", "syllabus", "academic standards", "instructions", "front pages", "0 front pages"] or norm_lower.startswith("answers"):
                continue

            wrapper = None
            if is_bad_outline or not clean_ch_title:
                for p_check in [c_start, c_start + 1]:
                    p_rec = next((p for p in pages if p.get("page_no") == p_check), None)
                    if not p_rec:
                        continue
                    p_text_lines = [l.strip() for l in p_rec.get("text", "").splitlines() if l.strip()]
                    if any(l.startswith(("A - ", "B - ", "A. ", "B. ")) for l in p_text_lines):
                        continue
                    for line in p_rec.get("text", "").splitlines():
                        ls = line.strip()
                        if not ls or len(ls) < 3:
                            continue
                        if re.match(r"^UNIT\s*[-–—]?\s*\d+", ls, re.I):
                            wrapper = ls
                            continue
                        if any(x in ls.lower() for x in ["government", "progress", "free distribution", "gift", "telangana", "fig-"]):
                            continue
                        if ls.isdigit() or re.match(r"^\d+\.\d+", ls):
                            continue
                        if re.match(r"^(lesson|unit|chapter)\s*[-–—]?\s*\d*$", ls, re.I):
                            continue
                        if ls.startswith(("A - ", "B - ", "C - ", "A. ", "B. ", "C. ")):
                            continue
                        m_num = re.match(r"^\d{1,2}\.?\s+([A-Za-z][A-Za-z\s\-–—&,\(\)]+)$", ls)
                        if m_num:
                            cand = m_num.group(1).strip()
                            if not any(m in cand.lower() for m in months_set) and len(cand) > 3:
                                clean_ch_title = cand
                                is_bad_outline = False
                                break
                        if re.match(r"^[A-Za-z][A-Za-z\s\-–—&,\(\)]+$", ls):
                            if not any(m in ls.lower() for m in months_set) and len(ls) > 3:
                                if ls.lower() not in ["chapter", "lesson", "unit", "index", "contents"]:
                                    clean_ch_title = ls
                                    is_bad_outline = False
                                    break
                    if not is_bad_outline:
                        break

            ocr_pages_set = {p.get("page_no") for p in pages if p.get("ocr_needed")}
            ch_ocr_needed = any(p_no in ocr_pages_set for p_no in range(c_start, c_end + 1))

            detected_prefix = None
            for p_no in range(c_start, min(c_end + 1, c_start + 4)):
                p_rec = next((p for p in pages if p.get("page_no") == p_no), None)
                if p_rec:
                    for l in p_rec.get("lines", []):
                        m_sec = re.match(r"^(\d{1,2})\.\d{1,2} ", l.get("text", "").strip())
                        if m_sec:
                            detected_prefix = m_sec.group(1)
                            break
                if detected_prefix:
                    break

            effective_ch_num = detected_prefix or lead_num or str(idx + 1)
            adapter.reset_chapter_state(chapter_number=effective_ch_num)
            raw_candidates = []
            for p_no in range(c_start, c_end + 1):
                p_rec = next((p for p in pages if p.get("page_no") == p_no), None)
                if not p_rec:
                    continue
                method = p_rec.get("method", "")
                garbled_ratio = p_rec.get("garbled_ratio", 0.0)
                garbled_pct = p_rec.get("garbled_pct", 0.0)
                ocr_needed = p_rec.get("ocr_needed", False)
                if "ocr_needed" in str(method) or ocr_needed or garbled_ratio > 0.05 or garbled_pct > 5.0:
                    continue
                lines_data = p_rec.get("lines", [])
                if lines_data:
                    nodes = adapter.extract_nodes_from_lines(p_no, lines_data)
                else:
                    nodes = adapter.extract_nodes_from_lines(p_no, [{"text": l, "spans": p_rec.get("spans", [])} for l in p_rec.get("text", "").splitlines()])
                raw_candidates.extend(nodes)

            filtered_candidates = []
            for c in raw_candidates:
                if c.get("level") == "activity":
                    act_title = c.get("official_title", "").strip()
                    if any(re.match(rf"^{re.escape(kw)}\b", act_title, re.I) for kw in adapter.activity_keywords):
                        c["ocr_needed"] = c.get("page", 0) in ocr_pages_set
                        c["source_file"] = fn
                        c["single_page"] = True
                        c["page_end"] = c.get("page", 0)
                        filtered_candidates.append(c)

            ch_info = {
                "id": f"{book_code}_ch_{idx + 1}",
                "official_number": effective_ch_num,
                "official_title": clean_ch_title,
                "wrapper": wrapper,
                "evidence": f"TOC {c_src}: {c_title} (p.{c_start}-{c_end})",
                "confidence": 0.95 if c_src == "outline" else 0.75,
                "rule_id": f"rule_ssc_chapter_{c_src}",
                "source_file": fn,
                "ocr_needed": ch_ocr_needed,
            }

            ch_node = tree_builder.build_chapter_tree(
                chapter_info=ch_info,
                raw_candidates=filtered_candidates,
                chapter_page_start=c_start,
                chapter_page_end=c_end,
                review_queue=review_queue,
                file_id=fn,
                end_matter_page=adapter.end_matter_page,
                end_matter_label=getattr(adapter, "end_matter_label", None),
            )
            chapters.append(ch_node)

        coverage_proof = self.coverage_prover.prove_coverage(
            book_code=book_code,
            chapters=chapters,
            pages_records=pages,
            expected_chapters_count=len(chapter_ranges),
        )

        book_curriculum = {
            "book_code": book_code,
            "board": "ssc",
            "class": cls,
            "subject": subject,
            "medium": medium,
            "title": book_title,
            "book_title": book_title,
            "total_pages": coverage_proof.get("pages_total", len(pages)),
            "adapter": adapter.adapter_name,
            "extraction_status": "ok",
            "source_sha256": extract_res.get("sha256", ""),
            "source_files": [fn],
            "chapters": chapters,
            "coverage_proof": coverage_proof,
        }

        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        with open(book_json_path, "w", encoding="utf-8") as f:
            json.dump(book_curriculum, f, indent=2, ensure_ascii=False)

        return book_curriculum
