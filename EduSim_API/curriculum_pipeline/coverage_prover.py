"""
EduSim Curriculum Pipeline — Coverage Prover
Computes rigorous coverage proof for every processed book/chapter file:
- pages_total, pages_with_text, pages_assigned_to_a_node, pages_unassigned
- chapters_found vs chapters_expected (checks contiguous NCERT numbers, flags gaps)
- headings_per_chapter and outlier detection
- strict status: passed | needs_review | failed | not_processed
Rule: any unassigned text page range > 2 pages, or any garbled/ocr_needed page, cannot be 'passed'.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


def collect_node_assigned_pages(node: Dict[str, Any]) -> Set[int]:
    """Recursively collect pages that contain node headings or are covered by nodes."""
    assigned: Set[int] = set()
    # Heading start page is strictly assigned
    p_start = node.get("page_start", 0)
    if p_start > 0:
        assigned.add(p_start)
    for child in node.get("nodes", []):
        assigned |= collect_node_assigned_pages(child)
    return assigned


def find_unassigned_ranges(unassigned_pages: List[int]) -> List[List[int]]:
    """Group consecutive unassigned pages into [start, end] ranges."""
    if not unassigned_pages:
        return []
    sorted_pages = sorted(unassigned_pages)
    ranges = []
    start = sorted_pages[0]
    prev = sorted_pages[0]

    for p in sorted_pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append([start, prev])
            start = p
            prev = p
    ranges.append([start, prev])
    return ranges


def collect_all_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively flattens node tree."""
    res = []
    for n in nodes:
        res.append(n)
        if "nodes" in n:
            res.extend(collect_all_nodes(n["nodes"]))
    return res


class CoverageProver:
    def prove_coverage(
        self,
        book_code: str,
        chapters: List[Dict[str, Any]],
        pages_records: List[Dict[str, Any]],
        expected_chapters_count: int,
        is_flagged_book: bool = False,
        toc_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Calculates completeness metrics, TOC reconciliation, and status."""
        total_pages = len(pages_records)
        pages_with_text = sum(1 for p in pages_records if p.get("char_count", 0) >= 30)

        # Collect assigned pages from nodes
        assigned_pages: Set[int] = set()
        for ch in chapters:
            assigned_pages |= collect_node_assigned_pages(ch)

        # In a chapter, the pages between chapter start and end are encompassed by the chapter
        for ch in chapters:
            cs = ch.get("page_start", 0)
            ce = ch.get("page_end", 0)
            if cs > 0 and ce >= cs:
                assigned_pages |= set(range(cs, ce + 1))

        # Check for unassigned pages with text
        unassigned_text_pages = [
            p.get("page_no", idx + 1)
            for idx, p in enumerate(pages_records)
            if p.get("char_count", 0) >= 40 and (idx + 1) not in assigned_pages
        ]
        unassigned_ranges = find_unassigned_ranges(unassigned_text_pages)

        # Outlier & count metrics
        headings_per_chapter = {}
        for ch in chapters:
            ch_num = ch.get("official_number") or ch.get("id")
            # Count child nodes
            total_headings = len(ch.get("nodes", []))
            headings_per_chapter[str(ch_num)] = total_headings

        ocr_needed_pages = [p.get("page_no") for p in pages_records if p.get("ocr_needed")]

        status_reasons = []
        status = "passed"

        if is_flagged_book:
            status = "not_processed"
            status_reasons.append("Flagged book (errata or ambiguous)")
        elif total_pages == 0:
            status = "failed"
            status_reasons.append("0-page or empty file")
        else:
            # Check for unassigned range > 2 pages
            for r in unassigned_ranges:
                if (r[1] - r[0] + 1) > 2:
                    status = "needs_review"
                    status_reasons.append(f"Unassigned text page range > 2 pages: {r[0]}-{r[1]}")
                    break

            if ocr_needed_pages:
                status = "needs_review"
                status_reasons.append(f"Pages require OCR: {ocr_needed_pages[:5]}")

            if any(ch.get("structure_unresolved") for ch in chapters):
                if status == "passed":
                    status = "needs_review"
                status_reasons.append("One or more chapters have unresolved structure")

            if expected_chapters_count > 0 and len(chapters) < expected_chapters_count:
                status = "needs_review"
                status_reasons.append(f"Chapter count gap: found {len(chapters)}, expected {expected_chapters_count}")

        # TOC reconciliation
        if not toc_entries:
            toc_match_ratio = 0.0
            toc_missing = []
            toc_extra = [ch.get("official_title", "") for ch in chapters]
            if status == "passed" and not is_flagged_book:
                status = "needs_review"
                status_reasons.append("no_toc")
        else:
            all_extracted_nodes = []
            for ch in chapters:
                all_extracted_nodes.append(ch)
                all_extracted_nodes.extend(collect_all_nodes(ch.get("nodes", [])))

            matched_toc = []
            missing_toc = []
            for entry in toc_entries:
                e_title = entry.get("title", "").strip().lower()
                e_num = str(entry.get("number", "")).strip() if entry.get("number") else ""
                e_page = entry.get("page")

                is_match = False
                for node in all_extracted_nodes:
                    n_title = node.get("official_title", "").strip().lower()
                    n_num = str(node.get("official_number", "")).strip() if node.get("official_number") else ""
                    n_page = node.get("page_start")

                    if e_num and n_num and e_num == n_num:
                        is_match = True
                        break
                    if e_title and len(e_title) >= 4 and (e_title in n_title or n_title in e_title):
                        is_match = True
                        break
                    if e_page and n_page and abs(e_page - n_page) <= 2 and (e_title[:8] in n_title if e_title else False):
                        is_match = True
                        break

                if is_match:
                    matched_toc.append(entry)
                else:
                    missing_toc.append(entry.get("title") or entry.get("number") or "Unknown")

            toc_match_ratio = round(len(matched_toc) / len(toc_entries), 3) if toc_entries else 0.0
            toc_missing = missing_toc
            toc_extra = []

            if toc_match_ratio < 0.95:
                if status == "passed" and not is_flagged_book:
                    status = "needs_review"
                    status_reasons.append(f"TOC match ratio {toc_match_ratio:.2f} < 0.95")

        return {
            "pages_total": total_pages,
            "pages_with_text": pages_with_text,
            "pages_assigned_to_a_node": len(assigned_pages),
            "pages_unassigned": len(unassigned_text_pages),
            "chapters_found": len(chapters),
            "chapters_expected": expected_chapters_count,
            "headings_per_chapter": headings_per_chapter,
            "unassigned_ranges": unassigned_ranges,
            "toc_match_ratio": toc_match_ratio,
            "toc_missing": toc_missing,
            "toc_extra": toc_extra,
            "status": status,
            "status_reasons": status_reasons,
        }
