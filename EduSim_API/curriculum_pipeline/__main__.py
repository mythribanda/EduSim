"""
EduSim Curriculum Pipeline — Main CLI Entry Point
Commands:
  extract [--pilot N] [--book CODE] [--all] [--resume] [--workers W] [--dry-run]
  validate
  report
  retry-failed
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure EduSim_API is in path
_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from curriculum_pipeline.catalog_builder import build_books_catalog
from curriculum_pipeline.extractor_engine import CurriculumExtractorEngine
from curriculum_pipeline.pipeline_config import (
    API_ROOT,
    NCERT_PATTERN,
    PIPELINE_OUTPUT_ROOT,
    TEXTBOOKS_DIR,
)

CURRICULUM_DIR = PIPELINE_OUTPUT_ROOT / "curriculum"
BOOKS_DIR = CURRICULUM_DIR / "books"
REPORTS_DIR = PIPELINE_OUTPUT_ROOT / "reports"
COMBINED_CURRICULUM_JSON = CURRICULUM_DIR / "curriculum.json"
EXTRACTION_REPORT_CSV = REPORTS_DIR / "extraction_report.csv"
REVIEW_QUEUE_CSV = REPORTS_DIR / "review_queue.csv"
COVERAGE_SUMMARY_JSON = REPORTS_DIR / "coverage_summary.json"


def cmd_extract(args: argparse.Namespace):
    tb_dir = Path(args.input).resolve() if getattr(args, "input", None) else TEXTBOOKS_DIR
    inv_path = PIPELINE_OUTPUT_ROOT / "inventory" / "textbooks_inventory.csv"

    if not inv_path.exists():
        print(f"[ERROR] Inventory CSV not found at {inv_path}. Run scan_textbooks first.")
        sys.exit(1)

    print(f"{'='*70}")
    print("  EduSim Curriculum Extractor — Stage 2")
    print(f"{'='*70}")
    print(f"  Textbooks source: {tb_dir}")
    print(f"  Resume mode     : {args.resume}")
    print(f"  Dry-run         : {args.dry_run}")
    print()

    # Step A: Build / load books catalog
    print("[1/5] Building books catalog (Step A)...")
    catalog_rows = build_books_catalog(inv_path, tb_dir)
    catalog_by_code = {r["book_code"]: r for r in catalog_rows}
    print(f"  Catalog ready: {len(catalog_rows)} distinct books catalogued.")

    with open(inv_path, "r", encoding="utf-8-sig") as f:
        inv_rows = list(csv.DictReader(f))

    # Group inventory files by book_code
    files_by_book = {}
    for r in inv_rows:
        fn = r["file"]
        m = NCERT_PATTERN.match(fn)
        if m:
            c, lang, code, part, ch = m.groups()
            bcode = f"{c.lower()}{lang.lower()}{code.lower()}{part}"
        else:
            clean_code = Path(fn).stem.lower()
            clean_code = "".join(ch if ch.isalnum() else "_" for ch in clean_code)[:48]
            bcode = f"ssc_{clean_code}"
        files_by_book.setdefault(bcode, []).append(r)

    engine = CurriculumExtractorEngine(textbooks_dir=tb_dir, resume=args.resume)
    review_queue: List[Dict[str, Any]] = []
    extraction_reports: List[Dict[str, Any]] = []
    all_books_curriculum: List[Dict[str, Any]] = []

    # Determine books to process
    books_to_process = []
    if args.book:
        if args.book in catalog_by_code:
            books_to_process = [args.book]
        else:
            print(f"[ERROR] Book code '{args.book}' not found in catalog.")
            sys.exit(1)
    elif args.pilot is not None:
        # Pilot selection
        # 10 diverse files per Step I:
        # 1. aejm101 (aejm1)
        # 2. aemr101 (aemr1)
        # 3. khat101 (khat1 - Hindi NCERT)
        # 4. kech101 (kech1 - Science/Chemistry NCERT)
        # 5. kemh101 (kemh1 - Maths NCERT)
        # 6. gees201 (gees2 - Social Science NCERT)
        # 7. VI Maths EM Final 2025-26 (02-11-2024).pdf (Smaller SSC book)
        # 8. 4th Tel FL 2025-26.pdf (Telugu book)
        # 9. 6th Social EM 2025-26_Errata_FINAL.pdf (Errata/odd file)
        # 10. English - Class VI - Total Book - 08.11.2024.pdf (0-byte/failed file)
        target_codes = [
            "aejm1",
            "aemr1",
            "khat1",
            "kech1",
            "kemh1",
            "gees2",
            "ssc_vi_maths_em_final_2025_26_02_11_2024_",
            "ssc_4th_tel_fl_2025_26",
            "ssc_6th_social_em_2025_26_errata_final",
            "ssc_english_class_vi_total_book_08_11_2024",
        ]
        # Filter available target codes
        books_to_process = [c for c in target_codes if c in catalog_by_code]
        if args.pilot > 0 and len(books_to_process) > args.pilot:
            books_to_process = books_to_process[:args.pilot]
        print(f"  Pilot mode selected {len(books_to_process)} target books.")
    elif args.all:
        print("[WARNING] Running full extraction for all books.")
        books_to_process = list(catalog_by_code.keys())
    else:
        print("Please specify --pilot N, --book CODE, or --all.")
        sys.exit(0)

    if args.dry_run:
        print(f"Dry-run: would process books {books_to_process}")
        return

    print(f"\n[2/5] Processing {len(books_to_process)} books...")
    for idx, bcode in enumerate(books_to_process, 1):
        binfo = catalog_by_code[bcode]
        flist = files_by_book.get(bcode, [])
        print(f"  [{idx}/{len(books_to_process)}] Processing book {bcode} ({binfo['book_title']}) - {len(flist)} file(s)...")

        if binfo["board"] == "ncert":
            b_curriculum = engine.process_ncert_book(binfo, flist, review_queue)
        else:
            entry = flist[0] if flist else {"file": binfo["book_title"] + ".pdf"}
            b_curriculum = engine.process_ssc_book(binfo, entry, review_queue)

        all_books_curriculum.append(b_curriculum)

        # Record file report
        cov = b_curriculum.get("coverage_proof", {})
        for fentry in flist:
            extraction_reports.append({
                "file": fentry["file"],
                "book_code": bcode,
                "board": binfo["board"],
                "class": binfo["class"],
                "subject": binfo["subject"],
                "chapters_found": cov.get("chapters_found", 0),
                "pages_total": cov.get("pages_total", 0),
                "pages_with_text": cov.get("pages_with_text", 0),
                "pages_unassigned": cov.get("pages_unassigned", 0),
                "status": cov.get("status", "unknown"),
                "status_reasons": "; ".join(cov.get("status_reasons", [])),
            })

    # Step G: Write combined outputs
    print("\n[3/5] Writing combined curriculum and reports...")
    CURRICULUM_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMBINED_CURRICULUM_JSON, "w", encoding="utf-8") as f:
        json.dump({"books": all_books_curriculum}, f, indent=2, ensure_ascii=False)
    print(f"  [OK] Combined curriculum written -> {COMBINED_CURRICULUM_JSON}")

    # Write extraction report CSV
    report_cols = [
        "file", "book_code", "board", "class", "subject",
        "chapters_found", "pages_total", "pages_with_text", "pages_unassigned",
        "status", "status_reasons"
    ]
    with open(EXTRACTION_REPORT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=report_cols)
        writer.writeheader()
        for r in extraction_reports:
            writer.writerow(r)
    print(f"  [OK] Extraction report CSV written -> {EXTRACTION_REPORT_CSV}")

    # Write review queue CSV
    rq_cols = ["file", "page", "problem", "found_text", "suggested_action"]
    with open(REVIEW_QUEUE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rq_cols)
        writer.writeheader()
        for r in review_queue:
            writer.writerow(r)
    print(f"  [OK] Review queue CSV written -> {REVIEW_QUEUE_CSV} ({len(review_queue)} issues flagged)")

    # Write coverage summary JSON
    cov_summary = {
        "total_books_processed": len(books_to_process),
        "status_counts": dict(__import__("collections").Counter(r["status"] for r in extraction_reports)),
        "class_breakdown": dict(__import__("collections").Counter(r["class"] for r in extraction_reports)),
        "subject_breakdown": dict(__import__("collections").Counter(r["subject"] for r in extraction_reports)),
    }
    with open(COVERAGE_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(cov_summary, f, indent=2)
    print(f"  [OK] Coverage summary written -> {COVERAGE_SUMMARY_JSON}")

    # Pilot display if requested
    if args.pilot is not None:
        print_pilot_comparison(books_to_process, all_books_curriculum, engine.textbooks_dir, files_by_book)


def print_pilot_comparison(book_codes, books_curriculum, textbooks_dir, files_by_book):
    """Prints per-chapter per-level node counts, full node tree recursively, and 10-book summary table."""
    print("\n" + "=" * 90)
    print("                    PILOT VERIFICATION & CHAPTER BREAKDOWN                    ")
    print("=" * 90)

    pilot_table_rows = []

    def print_node_recursive(nd, depth=1):
        lvl = nd.get("level", "node")
        num = nd.get("official_number") or ""
        otitle = nd.get("official_title", "")
        p1 = nd.get("page_start", "")
        p2 = nd.get("page_end", "")
        method = nd.get("detection_method", "")
        skipped = " [LEVEL-SKIPPED]" if nd.get("level_skipped") else ""
        preview = f" | \"{nd.get('preview')}\"" if nd.get("preview") else ""
        indent = "    " * depth
        label = f"[{lvl.upper()}]{skipped}"
        print(f"{indent}• {label:<16} {num:<8} {otitle[:50]:<52} (pp.{p1}-{p2}) [{method}]{preview}")
        for child in nd.get("nodes", []):
            print_node_recursive(child, depth + 1)

    def count_levels(node, counter):
        lvl = node.get("level")
        if lvl:
            counter[lvl] += 1
        for child in node.get("nodes", []):
            count_levels(child, counter)

    for bdata in books_curriculum:
        bcode = bdata["book_code"]
        title = bdata["book_title"]
        b_class = bdata.get("class", "")
        b_subject = bdata.get("subject", "")
        cov = bdata.get("coverage_proof", {})

        level_counts = __import__("collections").Counter()
        topics_no_children = 0

        print(f"\n==========================================================================================")
        print(f"BOOK: {bcode} | Class: {b_class} | Subject: {b_subject} | Title: {title}")
        print(f"Status: {cov.get('status')} | TOC Match: {cov.get('toc_match_ratio', 0.0)} | Pages: {cov.get('pages_total', 0)}")
        if cov.get("status_reasons"):
            print(f"Status Reasons: {', '.join(cov.get('status_reasons', []))}")
        print("------------------------------------------------------------------------------------------")
        print("Per-Chapter Level Counts:")

        for ch in bdata.get("chapters", []):
            ch_counter = __import__("collections").Counter()
            count_levels(ch, ch_counter)
            count_levels(ch, level_counts)
            ch_num = ch.get("official_number") or "N/A"
            ch_title = ch.get("official_title", "")
            print(f"  • Ch {ch_num} ({ch_title[:35]}): Topics={ch_counter['topic']}, Subtopics={ch_counter['subtopic']}, Activities={ch_counter['activity']}, Subheadings={ch_counter['subheading']}")

            for top in ch.get("nodes", []):
                if top.get("level") == "topic" and len(top.get("nodes", [])) == 0:
                    topics_no_children += 1

        nodes_str = f"Ch:{level_counts['chapter']} Top:{level_counts['topic']} SubT:{level_counts['subtopic']} Act:{level_counts['activity']} SubH:{level_counts['subheading']}"
        first_reason = cov.get("status_reasons", [""])[0] if cov.get("status_reasons") else ""

        pilot_table_rows.append({
            "book_code": bcode,
            "class": b_class,
            "subject": b_subject,
            "status": cov.get("status", "unknown"),
            "toc_match_ratio": cov.get("toc_match_ratio", 0.0),
            "nodes_per_level": nodes_str,
            "topics_no_children": topics_no_children,
            "reason": first_reason,
        })

        print("\nHierarchy Tree:")
        for ch in bdata.get("chapters", []):
            ch_num = ch.get("official_number") or ""
            ch_title = ch.get("official_title")
            p_start = ch.get("page_start")
            p_end = ch.get("page_end")
            wrap = f" [{ch.get('wrapper')}]" if ch.get("wrapper") else ""
            print(f"\n  [CHAPTER {ch_num}]{wrap} {ch_title} (pp.{p_start}-{p_end})")

            for child in ch.get("nodes", []):
                print_node_recursive(child, depth=1)

    # Print Pilot Table summary
    print("\n" + "=" * 120)
    print("                                      PILOT BOOKS SUMMARY TABLE                                       ")
    print("=" * 120)
    hdr = f"{'Book Code / File ID':<36} {'Cls':<4} {'Subject':<14} {'Status':<13} {'TOC Ratio':<10} {'Nodes per Level':<32} {'ZeroTop':<8} {'Reason'}"
    print(hdr)
    print("-" * 120)
    for r in pilot_table_rows:
        print(f"{r['book_code']:<36} {r['class']:<4} {r['subject']:<14} {r['status']:<13} {r['toc_match_ratio']:<10.2f} {r['nodes_per_level']:<32} {r['topics_no_children']:<8} {r['reason'][:25]}")
    print("=" * 120 + "\n")


def cmd_doctor(args: argparse.Namespace):
    """Checks Tesseract installation and language pack readiness."""
    import shutil
    import subprocess

    print("=" * 70)
    print("           EduSim Curriculum Pipeline — Doctor Preflight             ")
    print("=" * 70)

    # 1. Check Tesseract binary
    tess_exe = shutil.which("tesseract")
    if not tess_exe:
        cand_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if cand_path.exists():
            tess_exe = str(cand_path)

    if tess_exe:
        print(f"[OK] Tesseract executable found: {tess_exe}")
        try:
            ver_res = subprocess.run([tess_exe, "--version"], capture_output=True, text=True, check=True)
            first_line = ver_res.stdout.splitlines()[0] if ver_res.stdout else "version unknown"
            print(f"     Version: {first_line}")
        except Exception as e:
            print(f"     [WARNING] Could not get version: {e}")
    else:
        print("[FAIL] Tesseract executable NOT found in PATH or standard directory.")

    # 2. Check installed language packs
    installed_langs = []
    if tess_exe:
        try:
            lang_res = subprocess.run([tess_exe, "--list-langs"], capture_output=True, text=True, check=True)
            lines = [l.strip() for l in lang_res.stdout.splitlines() if l.strip()]
            if lines and "available" in lines[0].lower():
                lines = lines[1:]
            installed_langs = lines
        except Exception:
            pass

    local_tessdata = API_ROOT / "tessdata"
    if local_tessdata.exists():
        for tf in local_tessdata.glob("*.traineddata"):
            lang_name = tf.stem
            if lang_name not in installed_langs:
                installed_langs.append(lang_name)

    required_langs = {
        "eng": "English (Primary)",
        "hin": "Hindi / Devanagari (NCERT/SSC)",
        "tel": "Telugu (SSC state board)",
        "urd": "Urdu (SSC state board)",
    }

    print("\nLanguage Pack Status:")
    all_ok = bool(tess_exe)
    for code, desc in required_langs.items():
        if code in installed_langs:
            print(f"  [OK]   {code:<6} ({desc}) : INSTALLED")
        else:
            print(f"  [FAIL] {code:<6} ({desc}) : MISSING")
            all_ok = False

    if not all_ok:
        print("\n" + "-" * 70)
        print("                 WINDOWS INSTALLATION INSTRUCTIONS                    ")
        print("-" * 70)
        print("To install Tesseract and the required Indian language packs on Windows:")
        print("1. Download the installer from UB-Mannheim:")
        print("   https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. During installation, in the 'Choose Components' screen:")
        print("   Expand 'Additional script data (download)' and check:")
        print("     - Devanagari script")
        print("     - Telugu script")
        print("   Expand 'Additional language data (download)' and check:")
        print("     - Hindi (hin)")
        print("     - Telugu (tel)")
        print("     - Urdu (urd)")
        print("3. Alternatively, download language traineddata directly:")
        print("   https://github.com/tesseract-ocr/tessdata_fast/raw/main/hin.traineddata")
        print("   https://github.com/tesseract-ocr/tessdata_fast/raw/main/tel.traineddata")
        print("   https://github.com/tesseract-ocr/tessdata_fast/raw/main/urd.traineddata")
        print(f"   Place them into: {local_tessdata} or C:\\Program Files\\Tesseract-OCR\\tessdata\\")
        print("4. Add C:\\Program Files\\Tesseract-OCR to your system PATH.")
        print("-" * 70)
    else:
        print("\n[SUCCESS] Doctor check passed! All OCR engines and language packs are ready.")
    print("=" * 70 + "\n")


from curriculum_pipeline.validator import run_validation


def cmd_validate(args: argparse.Namespace):
    """Validates book JSON files against structural hierarchy rules."""
    books_dir = Path(args.input).resolve() if getattr(args, "input", None) else BOOKS_DIR
    if not books_dir.exists():
        print(f"[ERROR] Books directory not found: {books_dir}")
        sys.exit(1)

    report_path = REPORTS_DIR / "validation_errors.json"
    only_file = getattr(args, "only", None)

    print(f"{'='*70}")
    print("  EduSim Curriculum Hierarchy Validator")
    print(f"{'='*70}")
    print(f"  Target directory: {books_dir}")
    if only_file:
        print(f"  Filtering only  : {only_file}")
    print(f"  Report output   : {report_path}")
    print("-" * 70)

    total_errors, total_warnings, report = run_validation(
        books_dir=books_dir,
        only_file=only_file,
        output_report_path=report_path,
    )

    checked = report.get("total_files_checked", 0)
    files_err = report.get("files_with_errors", 0)
    files_warn = report.get("files_with_warnings", 0)

    susp_scores = report.get("suspicion_scores", {})
    all_seen_files = set(list(report.get("issues_by_file", {}).keys()) + list(susp_scores.keys()))
    for fname in sorted(all_seen_files):
        issues = report.get("issues_by_file", {}).get(fname, [])
        errs = [i for i in issues if i["severity"] == "ERROR"]
        warns = [i for i in issues if i["severity"] == "WARNING"]
        s_info = susp_scores.get(fname, {})
        s_score = s_info.get("score", 0.0)
        s_status = s_info.get("status", "ok")
        s_pct = round(s_score * 100.0, 1)

        print(f"\n[{fname}] - {len(errs)} error(s), {len(warns)} warning(s) | Suspicion: {s_pct}% ({s_status})")
        for err in errs:
            print(f"  ❌ [ERROR] {err['rule_id']}: {err['message']}")
        for warn in warns:
            print(f"  ⚠️  [WARNING] {warn['rule_id']}: {warn['message']}")

    print("\n" + "=" * 70)
    print(f"Validation Summary:")
    print(f"  Files checked   : {checked}")
    print(f"  Files with ERR  : {files_err} (total errors: {total_errors})")
    print(f"  Files with WARN : {files_warn} (total warnings: {total_warnings})")
    print(f"  Report written  : {report_path}")
    print("=" * 70)

    if total_errors > 0:
        print(f"\n[FAIL] Validation failed with {total_errors} error(s).")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All checked curriculum files passed validation!")
        sys.exit(0)


def cmd_report(args: argparse.Namespace):
    """Prints coverage and extraction summary."""
    if COVERAGE_SUMMARY_JSON.exists():
        with open(COVERAGE_SUMMARY_JSON, "r", encoding="utf-8") as f:
            summary = json.load(f)
        print("Coverage Summary:")
        print(json.dumps(summary, indent=2))
    else:
        print("Coverage summary not found. Run extract first.")


def cmd_load(args: argparse.Namespace):
    from curriculum_pipeline.loader import run_load_pipeline
    tb_books = Path(args.input).resolve() if getattr(args, "input", None) else None
    results = run_load_pipeline(
        books_dir=tb_books,
        only_book=args.only,
        include_review=args.include_review,
        force=args.force,
        dry_run=args.dry_run,
    )
    if any(r["status"] == "error" for r in results):
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="EduSim Curriculum Extractor CLI (Stage 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # extract command
    p_extract = subparsers.add_parser("extract", help="Extract curriculum hierarchy from textbooks.")
    p_extract.add_argument("--pilot", type=int, nargs="?", const=10, default=None, help="Run pilot on N books (default 10).")
    p_extract.add_argument("--book", type=str, help="Run on a specific book code (e.g. aejm1).")
    p_extract.add_argument("--all", action="store_true", help="Run on all books in catalog.")
    p_extract.add_argument("--input", type=str, help="Override textbooks directory.")
    p_extract.add_argument("--resume", action="store_true", default=True, help="Resume previously extracted files.")
    p_extract.add_argument("--no-resume", action="store_false", dest="resume", help="Force re-extraction of all files.")
    p_extract.add_argument("--workers", type=int, default=2, help="Parallel worker count (default 2).")
    p_extract.add_argument("--dry-run", action="store_true", help="Print plan without running extraction.")
    p_extract.set_defaults(func=cmd_extract)

    # validate command
    p_validate = subparsers.add_parser("validate", help="Validate output JSON files against schemas.")
    p_validate.add_argument("--only", type=str, help="Validate only a specific file (e.g. aejm1.json or aejm101.pdf).")
    p_validate.add_argument("--input", type=str, help="Override books directory.")
    p_validate.set_defaults(func=cmd_validate)

    # load command
    p_load = subparsers.add_parser("load", help="Load validated curriculum JSON into the database.")
    p_load.add_argument("--only", type=str, help="Load only a specific book code (e.g. aejm1).")
    p_load.add_argument("--include-review", action="store_true", help="Include books marked as needs_review.")
    p_load.add_argument("--force", action="store_true", help="Force reload even if sha256 and version are unchanged.")
    p_load.add_argument("--dry-run", action="store_true", help="Simulate load without modifying database.")
    p_load.add_argument("--input", type=str, help="Override books directory.")
    p_load.set_defaults(func=cmd_load)

    # report command
    p_report = subparsers.add_parser("report", help="Print extraction and coverage report.")
    p_report.set_defaults(func=cmd_report)

    # doctor command
    p_doctor = subparsers.add_parser("doctor", help="Check Tesseract and language packs installation.")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
