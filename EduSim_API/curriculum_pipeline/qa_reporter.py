"""
EduSim Curriculum Pipeline — QA Reporter
========================================
Generates comprehensive quality assurance reports across extracted curriculum books.

Outputs:
  - output/reports/qa_report.md: Human-readable markdown summary report
  - output/reports/qa_report.json: Machine-readable JSON summary report

Metrics tracked:
  - Node counts per level per book (chapter, topic, subtopic, activity, subheading)
  - Zero-chapter files
  - OCR-needed pages per book
  - Unmapped files
  - Validator errors and warnings
  - Suspicion score (from CurriculumValidator heuristics)
  - Low-density chapters (pages per topic > 12)
  - Summary comparison table
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from curriculum_pipeline.pipeline_config import (
    CURRICULUM_JSON_DIR,
    PIPELINE_OUTPUT_ROOT,
    REPORTS_DIR,
)
from curriculum_pipeline.validator import CurriculumValidator

logger = logging.getLogger("EduSim.qa_reporter")
DEFAULT_BOOKS_DIR = PIPELINE_OUTPUT_ROOT / "curriculum" / "books"
DEFAULT_QA_MD_PATH = REPORTS_DIR / "qa_report.md"
DEFAULT_QA_JSON_PATH = REPORTS_DIR / "qa_report.json"


def generate_qa_report(
    books_dir: Optional[Path] = None,
    output_md_path: Optional[Path] = None,
    output_json_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Scans all assembled curriculum JSON books and compiles a QA report."""
    b_dir = books_dir or DEFAULT_BOOKS_DIR
    out_md = output_md_path or DEFAULT_QA_MD_PATH
    out_json = output_json_path or DEFAULT_QA_JSON_PATH
    out_md.parent.mkdir(parents=True, exist_ok=True)

    validator = CurriculumValidator()

    # 1. Load preflight classifications if available
    preflight_by_file: Dict[str, str] = {}
    preflight_csv = REPORTS_DIR / "preflight.csv"
    if preflight_csv.exists():
        try:
            with open(preflight_csv, "r", encoding="utf-8") as pf:
                for row in csv.DictReader(pf):
                    preflight_by_file[row.get("file", "")] = row.get("classification", "ok")
        except Exception:
            pass

    # 2. Load unmapped files if available
    unmapped_files: List[Dict[str, Any]] = []
    unmapped_csv = REPORTS_DIR / "unmapped_files.csv"
    if unmapped_csv.exists():
        try:
            with open(unmapped_csv, "r", encoding="utf-8") as uf:
                unmapped_files = list(csv.DictReader(uf))
        except Exception:
            pass

    needs_resupply_files = [
        {"file": fn, "reason": "Zero bytes / unopenable (needs re-supply)"}
        for fn, cls in preflight_by_file.items()
        if cls == "unreadable"
    ]
    resupply_names = {x["file"] for x in needs_resupply_files}
    unmapped_files = [u for u in unmapped_files if u.get("file") not in resupply_names]

    # 3. Scan book files
    book_files = sorted(list(b_dir.glob("*.json"))) if b_dir.exists() else []

    book_reports: List[Dict[str, Any]] = []
    zero_chapter_books: List[Dict[str, Any]] = []
    total_level_counts = {"chapter": 0, "topic": 0, "subtopic": 0, "activity": 0, "subheading": 0}
    total_ocr_pages = 0
    total_val_errors = 0
    total_val_warnings = 0
    low_density_chapters: List[Dict[str, Any]] = []

    for bfile in book_files:
        try:
            with open(bfile, "r", encoding="utf-8") as f:
                bdata = json.load(f)
        except Exception as e:
            book_reports.append({
                "book_code": bfile.stem,
                "title": bfile.name,
                "status": "error",
                "error": str(e),
            })
            continue

        bcode = bdata.get("book_code", bfile.stem)
        btitle = bdata.get("book_title") or bdata.get("title", bcode)
        board = bdata.get("board", "ncert")
        cls = bdata.get("class", "")
        subject = bdata.get("subject", "")
        chapters = bdata.get("chapters", [])
        total_pages = bdata.get("total_pages", 0)

        # Count nodes per level
        lvl_counts = {"chapter": len(chapters), "topic": 0, "subtopic": 0, "activity": 0, "subheading": 0}
        book_ocr_pages = 0

        def _count_nodes(node: Dict[str, Any]):
            nonlocal book_ocr_pages
            lvl = node.get("level")
            if lvl in lvl_counts:
                lvl_counts[lvl] += 1
            if node.get("ocr_needed"):
                book_ocr_pages += 1
            for child in node.get("nodes", []):
                _count_nodes(child)

        for ch in chapters:
            if ch.get("ocr_needed"):
                book_ocr_pages += 1
            # Check low-density chapters (pages per topic > 12)
            ch_pages = max(1, ch.get("page_end", 0) - ch.get("page_start", 0) + 1)
            ch_topics = [n for n in ch.get("nodes", []) if n.get("level") == "topic"]
            topic_count = len(ch_topics)
            pages_per_topic = round(ch_pages / max(1, topic_count), 1)
            if ch_pages > 12 and (topic_count <= 1 or pages_per_topic > 12):
                low_density_chapters.append({
                    "book_code": bcode,
                    "chapter_number": ch.get("official_number"),
                    "chapter_title": ch.get("official_title"),
                    "chapter_pages": ch_pages,
                    "topic_count": topic_count,
                    "pages_per_topic": pages_per_topic,
                })

            for n in ch.get("nodes", []):
                _count_nodes(n)

        for k, v in lvl_counts.items():
            total_level_counts[k] += v
        total_ocr_pages += book_ocr_pages

        # Text quality determination
        src_files = bdata.get("source_files", [])
        primary_file = src_files[0] if src_files else f"{bcode}.pdf"
        t_quality = preflight_by_file.get(primary_file, bdata.get("text_quality", "ok"))

        # Fix A: If book is non-ok text quality or explicitly skipped, do not validate nodes into garbage errors
        is_skipped = bdata.get("extraction_status", "").startswith("skipped_") or t_quality != "ok"
        if is_skipped:
            val_errors = []
            val_warnings = []
            suspicion_score = 0.0
            calc_status = bdata.get("extraction_status", f"skipped_{t_quality}")
        else:
            val_issues = validator.validate_data(bdata, source_filename=bfile.name)
            val_errors = [i for i in val_issues if i.severity == "ERROR"]
            val_warnings = [i for i in val_issues if i.severity == "WARNING"]
            total_val_errors += len(val_errors)
            total_val_warnings += len(val_warnings)

            is_ssc = (board.lower() == "ssc")
            suspicion_score, calc_status = validator.get_suspicion_metrics(is_ssc=is_ssc)

        if len(chapters) == 0:
            zero_chapter_books.append({
                "book_code": bcode,
                "title": btitle,
                "file": primary_file,
                "status": bdata.get("extraction_status", calc_status),
                "notes": bdata.get("notes", f"text_quality={t_quality}"),
            })

        book_reports.append({
            "book_code": bcode,
            "title": btitle,
            "board": board,
            "class": cls,
            "subject": subject,
            "chapters_count": len(chapters),
            "total_pages": total_pages,
            "level_counts": lvl_counts,
            "ocr_needed_pages": book_ocr_pages,
            "text_quality": t_quality,
            "validator_errors": len(val_errors),
            "validator_warnings": len(val_warnings),
            "suspicion_score": suspicion_score,
            "extraction_status": bdata.get("extraction_status", calc_status),
        })

    # Summary dictionary
    summary_data = {
        "total_books_audited": len(book_files),
        "total_nodes_by_level": total_level_counts,
        "total_ocr_needed_pages": total_ocr_pages,
        "zero_chapter_books": zero_chapter_books,
        "needs_resupply_files": needs_resupply_files,
        "unmapped_files_count": len(unmapped_files),
        "total_validator_errors": total_val_errors,
        "total_validator_warnings": total_val_warnings,
        "low_density_chapters_count": len(low_density_chapters),
        "low_density_chapters": low_density_chapters,
        "books": book_reports,
    }

    # Write JSON report
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    # Generate Markdown report
    md_lines: List[str] = [
        "# EduSim Curriculum Pipeline — QA Quality Report",
        "",
        "## Executive Summary",
        "",
        f"- **Total Books Audited**: {len(book_files)}",
        f"- **Total Curriculum Nodes**: {sum(total_level_counts.values())} "
        f"(Chapters: {total_level_counts['chapter']}, Topics: {total_level_counts['topic']}, "
        f"Subtopics: {total_level_counts['subtopic']}, Activities: {total_level_counts['activity']}, "
        f"Subheadings: {total_level_counts['subheading']})",
        f"- **Zero-Chapter Books (Skipped / Flagged)**: {len(zero_chapter_books)}",
        f"- **Books Needing Re-Supply**: {len(needs_resupply_files)}",
        f"- **OCR-Needed Pages**: {total_ocr_pages}",
        f"- **Unmapped Files**: {len(unmapped_files)}",
        f"- **Validator Issues (ok books)**: {total_val_errors} Error(s), {total_val_warnings} Warning(s)",
        "",
        "## Book Extraction Summary Table",
        "",
        "| Book Code | Board | Class | Subject | Chapters | Topics | Subtopics | Activities | OCR Pages | Quality | Status | Suspicion |",
        "|-----------|-------|-------|---------|----------|--------|-----------|------------|-----------|---------|--------|-----------|",
    ]

    for b in book_reports:
        lc = b.get("level_counts", {})
        md_lines.append(
            f"| `{b['book_code']}` | {b['board'].upper()} | {b['class']} | {b['subject']} | "
            f"{b['chapters_count']} | {lc.get('topic', 0)} | {lc.get('subtopic', 0)} | {lc.get('activity', 0)} | "
            f"{b['ocr_needed_pages']} | `{b['text_quality']}` | `{b['extraction_status']}` | {b['suspicion_score']:.2f} |"
        )

    md_lines.extend([
        "",
        "## Low-Density Chapters (Pages Per Topic > 12)",
        "",
        "Chapters with high page-to-topic ratio where topics may be sparse or candidates missed:",
        "",
        "| Book Code | Ch # | Chapter Title | Pages | Topics | Pages/Topic |",
        "|-----------|------|---------------|-------|--------|-------------|",
    ])

    if low_density_chapters:
        for ldc in low_density_chapters:
            md_lines.append(
                f"| `{ldc['book_code']}` | {ldc['chapter_number']} | {ldc['chapter_title']} | "
                f"{ldc['chapter_pages']} | {ldc['topic_count']} | {ldc['pages_per_topic']} |"
            )
    else:
        md_lines.append("| - | - | None detected | - | - | - |")

    md_lines.extend([
        "",
        "## Books Needing Re-Supply (Unreadable / Zero Bytes)",
        "",
    ])
    if needs_resupply_files:
        for nr in needs_resupply_files:
            md_lines.append(f"- `{nr['file']}` — {nr['reason']}")
    else:
        md_lines.append("No unreadable files detected.")

    md_lines.extend([
        "",
        "## Zero-Chapter Books (Skipped / Flagged)",
        "",
    ])
    if zero_chapter_books:
        for z in zero_chapter_books:
            md_lines.append(f"- `{z['book_code']}` ({z['title']}) — Status: `{z['status']}`, Note: {z.get('notes', 'none')}")
    else:
        md_lines.append("Zero unparseable or zero-chapter files detected.")

    md_lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print("=" * 80)
    print("  EduSim QA Report Generator")
    print("=" * 80)
    print(f"  Books Audited        : {len(book_files)}")
    print(f"  Total Nodes          : {sum(total_level_counts.values())}")
    print(f"  Zero-Chapter Books   : {len(zero_chapter_books)}")
    print(f"  Needs Re-Supply      : {len(needs_resupply_files)}")
    print(f"  OCR-Needed Pages     : {total_ocr_pages}")
    print(f"  Validator Issues     : {total_val_errors} Error(s), {total_val_warnings} Warning(s)")
    print(f"  Low-Density Chapters : {len(low_density_chapters)}")
    print(f"  [OK] QA Markdown Report -> {out_md}")
    print(f"  [OK] QA JSON Report     -> {out_json}")
    print("=" * 80)

    return summary_data
