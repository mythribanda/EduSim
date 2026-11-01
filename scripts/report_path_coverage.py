"""
EduSim Curriculum Pipeline — Topic/Subtopic Path Coverage Reporter
=================================================================
Analyzes path coverage per subject, book, and chapter.
Lists chapters with 0% path coverage vs partial coverage,
along with sample chunk headings/previews.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
METADATA_JSON = API_DIR / "faiss_index_v2" / "metadata.json"
REPORT_OUTPUT = API_DIR / "curriculum_pipeline" / "output" / "reports" / "path_coverage_report.json"


def get_first_heading_or_line(text: str) -> str:
    """Extracts first line or sentence as representative chunk heading."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        return lines[0][:80]
    return text[:80].strip()


def generate_coverage_report(metadata_path: Path = METADATA_JSON) -> Dict[str, Any]:
    with open(metadata_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    total_chunks = len(chunks)
    chunks_with_path = sum(1 for c in chunks if c.get("topic_subtopic_path"))
    chunks_without_path = total_chunks - chunks_with_path

    # Group by subject -> book_code -> chapter_number
    by_subject_book_ch = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for c in chunks:
        s = c.get("subject") or "unknown"
        b = c.get("book_code") or "unknown"
        ch = str(c.get("chapter_number") or "0")
        by_subject_book_ch[s][b][ch].append(c)

    subject_summaries = {}
    detailed_report = {}

    for subj, books in sorted(by_subject_book_ch.items()):
        subj_total = 0
        subj_with_path = 0
        zero_cov_chapters = []
        partial_cov_chapters = []
        full_cov_chapters = []

        detailed_report[subj] = {}

        for b_code, chapters in sorted(books.items()):
            detailed_report[subj][b_code] = {"zero": [], "partial": [], "full": []}

            for ch_num, ch_chunks in sorted(
                chapters.items(),
                key=lambda x: int(x[0]) if x[0].isdigit() else 999,
            ):
                tot = len(ch_chunks)
                with_p = sum(1 for c in ch_chunks if c.get("topic_subtopic_path"))
                cov = with_p / tot if tot else 0.0

                subj_total += tot
                subj_with_path += with_p

                # Sample 5 chunk headings
                sample_headings = []
                for c in ch_chunks[:5]:
                    p = c.get("topic_subtopic_path")
                    h = p if p else f"[No Path] {get_first_heading_or_line(c.get('text', ''))}"
                    sample_headings.append(h)

                ch_info = {
                    "book_code": b_code,
                    "chapter_number": ch_num,
                    "chapter_title": ch_chunks[0].get("chapter_title", ""),
                    "total_chunks": tot,
                    "with_path": with_p,
                    "coverage": round(cov, 4),
                    "sample_headings": sample_headings,
                }

                if cov == 0.0:
                    zero_cov_chapters.append(ch_info)
                    detailed_report[subj][b_code]["zero"].append(ch_info)
                elif cov < 1.0:
                    partial_cov_chapters.append(ch_info)
                    detailed_report[subj][b_code]["partial"].append(ch_info)
                else:
                    full_cov_chapters.append(ch_info)
                    detailed_report[subj][b_code]["full"].append(ch_info)

        subject_summaries[subj] = {
            "total_chunks": subj_total,
            "with_path": subj_with_path,
            "missing_path": subj_total - subj_with_path,
            "coverage_pct": round(subj_with_path / subj_total * 100, 1) if subj_total else 0.0,
            "zero_coverage_chapters_count": len(zero_cov_chapters),
            "partial_coverage_chapters_count": len(partial_cov_chapters),
            "full_coverage_chapters_count": len(full_cov_chapters),
            "total_chapters": len(zero_cov_chapters) + len(partial_cov_chapters) + len(full_cov_chapters),
        }

    report = {
        "total_chunks": total_chunks,
        "with_path": chunks_with_path,
        "missing_path": chunks_without_path,
        "overall_coverage_pct": round(chunks_with_path / total_chunks * 100, 1) if total_chunks else 0.0,
        "subject_summaries": subject_summaries,
        "detailed_report": detailed_report,
    }

    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def print_coverage_report(report: Dict[str, Any], verbose_samples: bool = False):
    print("=" * 100)
    print("TOPIC_SUBTOPIC_PATH COVERAGE REPORT")
    print("=" * 100)
    print(f"Total Chunks: {report['total_chunks']:,}")
    print(f"With Path:    {report['with_path']:,} ({report['overall_coverage_pct']}%)")
    print(f"Missing Path: {report['missing_path']:,} ({100 - report['overall_coverage_pct']:.1f}%)")
    print("-" * 100)
    print(f"{'Subject':<18} | {'Total':<6} | {'With Path':<10} | {'Missing':<8} | {'Cov%':<6} | {'Zero Ch':<8} | {'Part Ch':<8} | {'Full Ch'}")
    print("-" * 100)
    for subj, s in sorted(report["subject_summaries"].items(), key=lambda x: x[1]["missing_path"], reverse=True):
        print(
            f"{subj:<18} | {s['total_chunks']:<6} | {s['with_path']:<10} | "
            f"{s['missing_path']:<8} | {s['coverage_pct']:>5.1f}% | "
            f"{s['zero_coverage_chapters_count']:<8} | {s['partial_coverage_chapters_count']:<8} | "
            f"{s['full_coverage_chapters_count']}"
        )
    print("=" * 100)

    # Print sample chapters with 0% and partial coverage for key gap subjects
    gap_subjects = ["social-science", "english", "mathematics", "hindi", "chemistry", "history", "business-studies", "sociology"]
    print("\nSAMPLE CHAPTER DETAILS FOR TOP GAP SUBJECTS:")
    for subj in gap_subjects:
        if subj not in report["detailed_report"]:
            continue
        print(f"\n--- {subj.upper()} ---")
        books = report["detailed_report"][subj]
        printed_count = 0
        for b_code, categories in books.items():
            for ch in categories["zero"][:2]:
                print(f"  [0% Coverage] Book: {b_code} | Ch {ch['chapter_number']}: \"{ch['chapter_title'][:35]}\" ({ch['with_path']}/{ch['total_chunks']} chunks)")
                for idx, h in enumerate(ch["sample_headings"], 1):
                    print(f"      {idx}. {h}")
                printed_count += 1
            for ch in categories["partial"][:1]:
                print(f"  [Partial Coverage ({ch['coverage']*100:.0f}%)] Book: {b_code} | Ch {ch['chapter_number']}: \"{ch['chapter_title'][:35]}\" ({ch['with_path']}/{ch['total_chunks']} chunks)")
                for idx, h in enumerate(ch["sample_headings"], 1):
                    print(f"      {idx}. {h}")
                printed_count += 1
            if printed_count >= 5:
                break


if __name__ == "__main__":
    rep = generate_coverage_report()
    print_coverage_report(rep)
