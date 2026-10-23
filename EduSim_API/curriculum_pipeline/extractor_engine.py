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
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from curriculum_pipeline.adapters.specialized_adapters import get_adapter_for_subject
from curriculum_pipeline.catalog_builder import build_books_catalog
from curriculum_pipeline.coverage_prover import CoverageProver
from curriculum_pipeline.page_extractor import PageExtractor, compute_file_sha256
from curriculum_pipeline.pipeline_config import (
    NCERT_PATTERN,
    PIPELINE_OUTPUT_ROOT,
    TEXTBOOKS_DIR,
)
from curriculum_pipeline.style_profiler import StyleProfiler
from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

CURRICULUM_OUT_DIR = PIPELINE_OUTPUT_ROOT / "curriculum"
BOOKS_OUT_DIR = CURRICULUM_OUT_DIR / "books"
REPORTS_OUT_DIR = PIPELINE_OUTPUT_ROOT / "reports"


class CurriculumExtractorEngine:
    def __init__(self, textbooks_dir: Optional[Path] = None, resume: bool = True):
        self.textbooks_dir = textbooks_dir or TEXTBOOKS_DIR
        self.resume = resume
        self.page_extractor = PageExtractor()
        self.style_profiler = StyleProfiler()
        self.coverage_prover = CoverageProver()

        BOOKS_OUT_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_OUT_DIR.mkdir(parents=True, exist_ok=True)

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
            if not txt or len(txt) < 2:
                continue
            # Skip lone chapter numbers (e.g. "1") or "Chapter 1"
            if re.match(r"^\d+$", txt) or re.match(r"^(Chapter|Unit|Theme|CHAPTER|इकाई|पाठ)\b", txt, re.I):
                continue
            # Skip copyright/reprint
            if re.search(r"\b(Reprint|Rationalised|ISBN|Published by)\b", txt, re.I):
                continue

            l_spans = l.get("spans", [])
            max_span_size = max((s.get("size", 0.0) for s in l_spans), default=0.0)
            is_bold = any(s.get("bold", False) for s in l_spans)
            candidate_lines.append({
                "index": l_idx,
                "text": txt,
                "bbox": l.get("bbox", [0, 0, 0, 0]),
                "size": max_span_size,
                "bold": is_bold,
            })

        if not candidate_lines:
            return f"Chapter {ch_no}", wrapper, None

        # Find the maximum font size among candidate lines
        max_size = max(c["size"] for c in candidate_lines)
        if max_size < 12.0:
            return candidate_lines[0]["text"], wrapper, None

        # Filter lines that match title size (within 1.5 pt of max_size)
        title_lines = [c for c in candidate_lines if abs(c["size"] - max_size) <= 1.5]

        # Merge consecutive, vertically adjacent title lines
        merged_groups: List[List[Dict[str, Any]]] = []
        for tl in title_lines:
            if not merged_groups:
                merged_groups.append([tl])
            else:
                last_group = merged_groups[-1]
                prev_line = last_group[-1]
                y_gap = tl["bbox"][1] - prev_line["bbox"][3]
                idx_diff = tl["index"] - prev_line["index"]
                if idx_diff == 1 or (-15.0 <= y_gap <= 25.0):
                    last_group.append(tl)
                else:
                    merged_groups.append([tl])

        best_group = merged_groups[0]
        merged_title = " ".join(tl["text"] for tl in best_group)
        merged_title = re.sub(r"\s+", " ", merged_title).strip()
        return merged_title, wrapper, None


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

        # 1. Page extraction for each chapter file
        jsonl_files = []
        source_shas = []
        missing_langs = set()

        # Sort file entries by chapter number
        def get_ch_num(entry):
            m = NCERT_PATTERN.match(entry["file"])
            return int(m.group(5)) if m else 0

        file_entries_sorted = sorted(file_entries, key=get_ch_num)

        for entry in file_entries_sorted:
            fn = entry["file"]
            pdf_path = self.textbooks_dir / "ncert books" / fn
            extract_res = self.page_extractor.extract_file(pdf_path, file_id=fn, force=not self.resume)
            out_jsonl = self.page_extractor.get_output_path(fn)
            jsonl_files.append(out_jsonl)
            if extract_res.get("sha256"):
                source_shas.append(extract_res["sha256"])
            for ml in extract_res.get("missing_ocr_languages", []):
                missing_langs.add(ml)

        # 2. Style profile
        style_profile = self.style_profiler.profile_book(book_code, jsonl_files, force=not self.resume)
        adapter = get_adapter_for_subject(subject, style_profile, language=medium)

        # 3. Chapter & node extraction
        tree_builder = CurriculumTreeBuilder(book_code)
        chapters: List[Dict[str, Any]] = []
        all_book_pages: List[Dict[str, Any]] = []
        page_offset = 0

        for idx, (entry, j_path) in enumerate(zip(file_entries_sorted, jsonl_files)):
            fn = entry["file"]
            m = NCERT_PATTERN.match(fn)
            ch_no = int(m.group(5)) if m else (idx + 1)

            # Read page records from jsonl
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
                review_queue.append({
                    "file": fn,
                    "page": 1,
                    "problem": "zero_pages_or_unreadable",
                    "found_text": "",
                    "suggested_action": "Check file corruption or reader permissions",
                })
                continue

            ch_start = page_offset + 1
            ch_end = page_offset + ch_pages_count
            page_offset = ch_end

            # Shift page numbers for unified book view
            for p in pages:
                shifted_p = dict(p)
                shifted_p["page_no"] = ch_start + p.get("page_no", 1) - 1
                all_book_pages.append(shifted_p)

            # Extract title & wrapper
            ch_title, wrapper, conflict_note = self.extract_ncert_chapter_title_from_p1(pages, ch_no)
            if conflict_note:
                review_queue.append({
                    "file": fn,
                    "page": ch_start,
                    "problem": "chapter_title_conflict",
                    "found_text": conflict_note,
                    "suggested_action": "Review official chapter title on page 1",
                })

            # Extract raw node candidates from chapter pages
            adapter.reset_chapter_state(chapter_number=ch_no)
            raw_candidates = []
            for p in pages:
                page_actual = ch_start + p.get("page_no", 1) - 1
                method = p.get("method", "")
                garbled_ratio = p.get("garbled_ratio", 0.0)
                garbled_pct = p.get("garbled_pct", 0.0)
                ocr_needed = p.get("ocr_needed", False)

                # Garbled pages produce NO nodes at all
                if "ocr_needed" in str(method) or ocr_needed or garbled_ratio > 0.05 or garbled_pct > 5.0:
                    continue

                lines_data = p.get("lines", [])
                if lines_data:
                    nodes = adapter.extract_nodes_from_lines(page_actual, lines_data)
                else:
                    nodes = adapter.extract_nodes_from_lines(page_actual, [{"text": l, "spans": p.get("spans", [])} for l in p.get("text", "").splitlines()])
                raw_candidates.extend(nodes)

            # Filter candidates: remove duplicate of chapter title or wrapper, add file_id and ocr_needed
            norm_ch_title = re.sub(r"[^\w]", "", ch_title).lower()
            norm_wrapper = re.sub(r"[^\w]", "", str(wrapper or "")).lower()
            ocr_pages_set = {p.get("page_no") for p in pages if p.get("ocr_needed")}
            ch_ocr_needed = bool(ocr_pages_set)

            filtered_candidates = []
            for c in raw_candidates:
                c_title = c.get("official_title", "")
                norm_c = re.sub(r"[^\w]", "", c_title).lower()
                c_page = c.get("page", 0)

                # Filter out title block fragments on chapter's first page (only if unnumbered)
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
                c_page_local = c_page - ch_start + 1
                c["ocr_needed"] = c_page_local in ocr_pages_set
                c["source_file"] = fn
                filtered_candidates.append(c)


            ch_info = {
                "id": f"{book_code}_ch_{ch_no}",
                "official_number": str(ch_no),
                "official_title": ch_title,
                "wrapper": wrapper,
                "evidence": f"File {fn} - Chapter {ch_no}: {ch_title}",
                "confidence": 0.95,
                "rule_id": "rule_ncert_file_chapter",
                "source_file": fn,
                "ocr_needed": ch_ocr_needed,
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


            if chapter_node.get("structure_unresolved"):
                review_queue.append({
                    "file": fn,
                    "page": ch_start,
                    "problem": "structure_unresolved",
                    "found_text": ch_title,
                    "suggested_action": "No headings found below chapter level; review manually",
                })

            chapters.append(chapter_node)

        # 4. Coverage proof
        expected_chapters = len(file_entries_sorted)
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
            "source_files": [entry["file"] for entry in file_entries_sorted],
            "chapters": chapters,
            "coverage_proof": coverage_proof,
        }

        # Export 40 subheading samples if requested
        if book_code in ["kech1", "khat1", "gees2"] or "ssc_4th_tel" in book_code:
            self._export_subheading_sample(book_code, chapters)

        # Write book output
        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        with open(book_json_path, "w", encoding="utf-8") as f:
            json.dump(book_curriculum, f, indent=2, ensure_ascii=False)

        return book_curriculum

    def process_ssc_book(
        self,
        book_info: Dict[str, Any],
        entry: Dict[str, Any],
        review_queue: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        book_code = book_info["book_code"]
        fn = entry["file"]
        pdf_path = self.textbooks_dir / "Text Books" / fn

        subject = book_info["subject"]
        medium = book_info["medium"]
        book_title = book_info["book_title"]
        cls = book_info["class"]

        is_flagged = (
            "errata" in fn.lower()
            or fn == "5em.pdf"
            or fn == "English - Class VI - Total Book - 08.11.2024.pdf"
        )

        if is_flagged:
            # Step A.2 & A.3: keep flagged, do not process nodes
            coverage_proof = self.coverage_prover.prove_coverage(
                book_code=book_code,
                chapters=[],
                pages_records=[],
                expected_chapters_count=0,
                is_flagged_book=True,
            )
            return {
                "book_code": book_code,
                "board": "ssc",
                "class": cls,
                "subject": subject,
                "medium": medium,
                "book_title": book_title,
                "adapter": "none",
                "source_sha256": entry.get("sha256", ""),
                "chapters": [],
                "coverage_proof": coverage_proof,
            }

        # Extract pages
        extract_res = self.page_extractor.extract_file(pdf_path, file_id=fn, force=not self.resume)
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

        # Step D: SSC Chapter boundaries using order of trust:
        # 1. Embedded PDF outline (TOC)
        # 2. Printed Table of Contents page detection
        # 3. Chapter title style detection
        toc_outline = meta_rec.get("toc", [])
        chapter_ranges: List[Tuple[str, int, int, str]] = []  # (title, start, end, source)

        if toc_outline:
            # Filter level 1 entries and exclude front-matter/prelim/appendix/total-book
            l1 = [
                e for e in toc_outline
                if e[0] == 1
                and e[2] > 0
                and not any(x in e[1].lower() for x in ["initial", "total book", "prelim", "appendix", "cover"])
                and e[1].strip() != "00"
            ]
            for i, entry_toc in enumerate(l1):
                t_title = entry_toc[1].strip()
                t_start = entry_toc[2]
                t_end = l1[i + 1][2] - 1 if i + 1 < len(l1) else len(pages)
                t_end = max(t_start, min(t_end, len(pages)))
                chapter_ranges.append((t_title, t_start, t_end, "outline"))

        if not chapter_ranges:
            # Fallback to style detection for chapters
            # Look for lines with 'Chapter N' or large title font
            for p in pages:
                p_no = p.get("page_no", 1)
                for line in p.get("text", "").splitlines():
                    line_s = line.strip()
                    if re.match(r"^(Chapter|Lesson|Unit|PART)\s*([0-9IVX]+)", line_s, re.I):
                        chapter_ranges.append((line_s, p_no, p_no, "body_style"))
            # Adjust ranges
            adjusted = []
            for i, cr in enumerate(chapter_ranges):
                c_end = chapter_ranges[i + 1][1] - 1 if i + 1 < len(chapter_ranges) else len(pages)
                adjusted.append((cr[0], cr[1], max(cr[1], c_end), "body_style"))
            chapter_ranges = adjusted

        # If still no chapter ranges, treat whole book as 1 chapter
        if not chapter_ranges:
            chapter_ranges = [(book_title, 1, len(pages), "fallback_single_chapter")]

        # Build printed TOC mapping from early pages if available
        printed_toc_map: Dict[int, str] = {}
        months_set = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
        for p in pages[:15]:
            p_text = p.get("text", "")
            if "index" in p_text.lower() or "contents" in p_text.lower():
                lines = [l.strip() for l in p_text.splitlines() if l.strip()]
                for i_l, l_str in enumerate(lines):
                    m1 = re.match(r"^(\d{1,2})\s+([A-Za-z][A-Za-z\s\-–—&,\(\)]+)$", l_str)
                    if m1 and int(m1.group(1)) <= 30 and len(m1.group(2).strip()) > 2:
                        printed_toc_map[int(m1.group(1))] = m1.group(2).strip()
                    elif l_str.isdigit() and int(l_str) <= 30 and i_l + 1 < len(lines):
                        nxt = lines[i_l + 1]
                        if re.match(r"^[A-Za-z][A-Za-z\s\-–—&,\(\)]+$", nxt) and not nxt.isdigit() and len(nxt) > 2 and "government" not in nxt.lower():
                            c_num = int(l_str)
                            if c_num not in printed_toc_map:
                                printed_toc_map[c_num] = nxt.strip()

        tree_builder = CurriculumTreeBuilder(book_code)
        chapters: List[Dict[str, Any]] = []

        for idx, (c_title, c_start, c_end, c_src) in enumerate(chapter_ranges):
            # 2.6d SSC books: TOC-driven only. Extract clean title and wrapper from page c_start if outline is a filename/unit tag
            clean_ch_title = c_title
            ch_idx = idx + 1
            is_bad_outline = (
                not clean_ch_title
                or clean_ch_title.endswith(".pdf")
                or clean_ch_title.isdigit()
                or re.match(r"^(lesson|unit|chapter)[-_ ]?\d+(\.pdf)?$", clean_ch_title, re.I)
            )

            # Check printed TOC first
            if is_bad_outline and ch_idx in printed_toc_map:
                cand_t = printed_toc_map[ch_idx]
                if not any(m in cand_t.lower() for m in months_set) and len(cand_t) > 3:
                    clean_ch_title = cand_t
                    is_bad_outline = False

            wrapper = None
            if is_bad_outline or not clean_ch_title:
                # Inspect c_start and c_start + 1
                for p_check in [c_start, c_start + 1]:
                    p_rec = next((p for p in pages if p.get("page_no") == p_check), None)
                    if not p_rec:
                        continue
                    p_text_lines = [l.strip() for l in p_rec.get("text", "").splitlines() if l.strip()]
                    # If this page is a unit reading-selection divider e.g. "A - ...", "B - ...", skip to next page
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
                        # Match '1. Personality Development'
                        m_num = re.match(r"^\d{1,2}\.?\s+([A-Za-z][A-Za-z\s\-–—&,\(\)]+)$", ls)
                        if m_num:
                            cand = m_num.group(1).strip()
                            if not any(m in cand.lower() for m in months_set) and len(cand) > 3:
                                clean_ch_title = cand
                                is_bad_outline = False
                                break
                        # Match plain title
                        if re.match(r"^[A-Za-z][A-Za-z\s\-–—&,\(\)]+$", ls):
                            if not any(m in ls.lower() for m in months_set) and len(ls) > 3:
                                if ls.lower() not in ["chapter", "lesson", "unit", "index", "contents"]:
                                    clean_ch_title = ls
                                    is_bad_outline = False
                                    break
                    if not is_bad_outline:
                        break

            norm_c_title = re.sub(r"[^\w]", "", clean_ch_title).lower()
            ocr_pages_set = {p.get("page_no") for p in pages if p.get("ocr_needed")}
            ch_ocr_needed = any(p_no in ocr_pages_set for p_no in range(c_start, c_end + 1))

            # Extract raw node candidates from chapter pages
            adapter.reset_chapter_state(chapter_number=idx + 1)
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
                # 2.6d: Do NOT infer Topic/Subtopic/Activity from font size in SSC books.
                # Only keep Activity nodes matching controlled keyword list.
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
                "official_number": str(idx + 1),
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

        # Build TOC entries from outline if present
        toc_entries = []
        if toc_outline:
            for entry_toc in toc_outline:
                toc_entries.append({
                    "number": None,
                    "title": entry_toc[1].strip(),
                    "page": entry_toc[2],
                    "level": "chapter" if entry_toc[0] == 1 else "section",
                })

        coverage_proof = self.coverage_prover.prove_coverage(
            book_code=book_code,
            chapters=chapters,
            pages_records=pages,
            expected_chapters_count=len(chapter_ranges),
            toc_entries=toc_entries if toc_entries else None,
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
            "extraction_status": "needs_review",
            "source_sha256": extract_res.get("sha256", ""),
            "source_files": [fn],
            "chapters": chapters,
            "coverage_proof": coverage_proof,
        }

        # Export 40 subheading samples if requested
        if book_code in ["kech1", "khat1", "gees2"] or "ssc_4th_tel" in book_code:
            self._export_subheading_sample(book_code, chapters)

        book_json_path = BOOKS_OUT_DIR / f"{book_code}.json"
        with open(book_json_path, "w", encoding="utf-8") as f:
            json.dump(book_curriculum, f, indent=2, ensure_ascii=False)

        return book_curriculum

    def _export_subheading_sample(self, book_code: str, chapters: List[Dict[str, Any]]):
        """Exports up to 40 random subheadings for audit."""
        debug_dir = PIPELINE_OUTPUT_ROOT / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        out_csv = debug_dir / f"subheading_sample_{book_code}.csv"

        subheadings = []
        def _find_sh(node, parent_name):
            if node.get("level") == "subheading":
                subheadings.append({
                    "text": node.get("official_title", ""),
                    "page": node.get("page_start", ""),
                    "size": node.get("font_size", ""),
                    "bold": node.get("bold", ""),
                    "detection_method": node.get("detection_method", ""),
                    "parent": parent_name,
                })
            p_name = node.get("official_title", "")
            for ch in node.get("nodes", []):
                _find_sh(ch, p_name)

        for ch in chapters:
            _find_sh(ch, ch.get("official_title", ""))

        sample = subheadings
        if len(subheadings) > 40:
            import random
            rnd = random.Random(42)
            sample = rnd.sample(subheadings, 40)

        fieldnames = ["text", "page", "size", "bold", "detection_method", "parent"]
        with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in sample:
                writer.writerow(s)
