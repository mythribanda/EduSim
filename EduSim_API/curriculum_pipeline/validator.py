"""
EduSim Curriculum Pipeline — Hierarchy Validator
=================================================
Validates book and chapter curriculum JSON trees against structural rules.

ERRORS:
  - empty or whitespace-only title
  - invalid parent-to-child level nesting (levels may be skipped, but order must never invert)
  - a child's page range falls outside its parent's range
  - a sibling starts on an earlier page than the previous sibling started (page order violated)
  - missing source_file or page numbers on any node
  - duplicate sibling titles at Topic and Subtopic levels only

NOT errors:
  - duplicate sibling titles at Activity and Subheading levels (NCERT repeats e.g. "Let us sing")
  - siblings sharing a boundary page

WARNINGS:
  - title over 100 chars
  - chapter with 0 activities
  - more than 50 subheadings in a chapter
  - ocr_needed pages present
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

HIERARCHY_LEVELS = ["chapter", "topic", "subtopic", "activity", "subheading"]
LEVEL_RANKS: Dict[str, int] = {
    "chapter": 0,
    "topic": 1,
    "subtopic": 2,
    "activity": 3,
    "subheading": 4,
}


@dataclass
class ValidationIssue:
    severity: str  # "ERROR" | "WARNING"
    rule_id: str
    message: str
    node_id: Optional[str] = None
    node_title: Optional[str] = None
    level: Optional[str] = None
    page: Optional[int] = None
    file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NodeSchema(BaseModel):
    id: Optional[str] = None
    parent_id: Optional[str] = None
    level: str
    official_number: Optional[str] = None
    official_title: str
    normalized_title: Optional[str] = None
    page_start: int
    page_end: int
    source_file: str
    ocr_needed: bool = False
    occurrence_index: Optional[int] = None
    identity_key: Optional[str] = None
    nodes: List[Dict[str, Any]] = Field(default_factory=list)


class CurriculumValidator:
    """Validates curriculum nodes and trees against structural and hierarchy rules."""

    def __init__(self):
        self.issues: List[ValidationIssue] = []

    def validate_file(self, file_path: Path) -> List[ValidationIssue]:
        """Validates a book JSON file or chapter JSON file."""
        self.issues = []
        if not file_path.exists():
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="file_not_found",
                    message=f"File not found: {file_path}",
                    file=str(file_path),
                )
            )
            return self.issues

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="invalid_json",
                    message=f"Failed to parse JSON: {e}",
                    file=str(file_path),
                )
            )
            return self.issues

        return self.validate_data(data, source_filename=file_path.name)

    def validate_data(self, data: Dict[str, Any], source_filename: str = "") -> List[ValidationIssue]:
        """Validates book or chapter dictionary."""
        self.issues = []

        # If data is a book curriculum with chapters list
        if "chapters" in data and isinstance(data["chapters"], list):
            for ch in data["chapters"]:
                self._validate_chapter(ch, source_filename)
        elif data.get("level") == "chapter" or "nodes" in data:
            self._validate_chapter(data, source_filename)
        else:
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="unknown_root_format",
                    message="JSON object is neither a book curriculum (missing 'chapters') nor a chapter node",
                    file=source_filename,
                )
            )

        return self.issues

    def _validate_chapter(self, ch: Dict[str, Any], file_ctx: str):
        # 1. Basic node validation on chapter root
        self._validate_single_node(ch, parent=None, file_ctx=file_ctx)

        # 2. Chapter-level warning checks: 0 activities, >50 subheadings
        stats = {"activities": 0, "subheadings": 0}
        self._gather_chapter_stats(ch, stats)

        ch_title = ch.get("official_title", "")
        ch_id = ch.get("id")
        ch_source = ch.get("source_file", file_ctx)

        if stats["activities"] == 0:
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id="chapter_zero_activities",
                    message=f"Chapter '{ch_title}' contains 0 activities",
                    node_id=ch_id,
                    node_title=ch_title,
                    level="chapter",
                    page=ch.get("page_start"),
                    file=ch_source,
                )
            )

        if stats["subheadings"] > 50:
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id="excessive_subheadings",
                    message=f"Chapter '{ch_title}' contains {stats['subheadings']} subheadings (> 50)",
                    node_id=ch_id,
                    node_title=ch_title,
                    level="chapter",
                    page=ch.get("page_start"),
                    file=ch_source,
                )
            )

        # 3. Recursively validate children
        self._validate_children(ch, parent=ch, file_ctx=file_ctx)

    def _gather_chapter_stats(self, node: Dict[str, Any], stats: Dict[str, int]):
        lvl = node.get("level")
        if lvl == "activity":
            stats["activities"] += 1
        elif lvl == "subheading":
            stats["subheadings"] += 1

        for child in node.get("nodes", []):
            self._gather_chapter_stats(child, stats)

    def _validate_single_node(self, node: Dict[str, Any], parent: Optional[Dict[str, Any]], file_ctx: str):
        node_id = node.get("id")
        level = node.get("level")
        raw_title = node.get("official_title")
        source_file = node.get("source_file") or file_ctx
        page_start = node.get("page_start")
        page_end = node.get("page_end")
        ocr_needed = bool(node.get("ocr_needed", False))

        # Rule 1: Empty or whitespace title (ERROR)
        if raw_title is None or not str(raw_title).strip():
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="empty_title",
                    message=f"Node '{node_id}' has an empty or whitespace-only title",
                    node_id=node_id,
                    node_title=str(raw_title),
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )
            title = ""
        else:
            title = str(raw_title).strip()

        # Rule 2: Missing source_file or invalid page numbers (ERROR)
        if not source_file or not str(source_file).strip():
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="missing_source_file",
                    message=f"Node '{node_id}' ('{title}') is missing source_file",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file="",
                )
            )

        if not isinstance(page_start, int) or page_start < 1:
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="invalid_page_start",
                    message=f"Node '{node_id}' ('{title}') has invalid page_start: {page_start}",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )

        if not isinstance(page_end, int) or (isinstance(page_start, int) and page_end < page_start):
            self.issues.append(
                ValidationIssue(
                    severity="ERROR",
                    rule_id="invalid_page_end",
                    message=f"Node '{node_id}' ('{title}') has invalid page_end ({page_end}) < page_start ({page_start})",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )

        # Rule 3: Invalid parent-to-child level nesting (ERROR)
        if parent is not None:
            p_level = parent.get("level", "")
            p_rank = LEVEL_RANKS.get(p_level, -1)
            c_rank = LEVEL_RANKS.get(level, -1)

            if p_rank == -1 or c_rank == -1 or c_rank <= p_rank:
                self.issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        rule_id="invalid_level_nesting",
                        message=(
                            f"Invalid level nesting: child level '{level}' cannot be placed under "
                            f"parent level '{p_level}' in node '{node_id}' ('{title}')"
                        ),
                        node_id=node_id,
                        node_title=title,
                        level=level,
                        page=page_start,
                        file=source_file,
                    )
                )

        # Rule 4: Child page range outside parent range (ERROR)
        if parent is not None:
            p_start = parent.get("page_start")
            p_end = parent.get("page_end")
            if (
                isinstance(p_start, int)
                and isinstance(p_end, int)
                and isinstance(page_start, int)
                and isinstance(page_end, int)
            ):
                if page_start < p_start or page_end > p_end:
                    self.issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            rule_id="child_page_outside_parent",
                            message=(
                                f"Child page range [{page_start}, {page_end}] in node '{node_id}' ('{title}') "
                                f"falls outside parent range [{p_start}, {p_end}] ('{parent.get('official_title')}')"
                            ),
                            node_id=node_id,
                            node_title=title,
                            level=level,
                            page=page_start,
                            file=source_file,
                        )
                    )

        # WARNING: Title over 100 characters
        if len(title) > 100:
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id="title_over_100_chars",
                    message=f"Node '{node_id}' title length ({len(title)}) exceeds 100 characters: '{title[:50]}...'",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )

        # WARNING: OCR needed pages present
        if ocr_needed:
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id="ocr_needed_present",
                    message=f"Node '{node_id}' ('{title}') flagged with ocr_needed=True on page {page_start}",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )

    def _validate_children(self, parent_node: Dict[str, Any], parent: Dict[str, Any], file_ctx: str):
        children = parent_node.get("nodes", [])
        if not children:
            return

        seen_topic_titles: Dict[str, str] = {}
        seen_subtopic_titles: Dict[str, str] = {}
        prev_sibling_start: Optional[int] = None
        prev_sibling_title: Optional[str] = None

        for child in children:
            # Validate individual node properties & parent-child nesting
            self._validate_single_node(child, parent=parent_node, file_ctx=file_ctx)

            c_level = child.get("level")
            c_title = str(child.get("official_title") or "").strip()
            c_id = child.get("id")
            c_source = child.get("source_file", file_ctx)
            c_start = child.get("page_start")
            norm_tit = re.sub(r"\s+", " ", c_title).lower()

            # Rule 5: Sibling page order (ERROR)
            # Sibling cannot start on an earlier page than previous sibling started.
            # (Note: siblings sharing boundary page is NOT an error)
            if isinstance(c_start, int) and prev_sibling_start is not None:
                if c_start < prev_sibling_start:
                    self.issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            rule_id="sibling_page_order_violated",
                            message=(
                                f"Sibling '{c_title}' starts on page {c_start}, earlier than preceding "
                                f"sibling '{prev_sibling_title}' which started on page {prev_sibling_start}"
                            ),
                            node_id=c_id,
                            node_title=c_title,
                            level=c_level,
                            page=c_start,
                            file=c_source,
                        )
                    )

            if isinstance(c_start, int):
                prev_sibling_start = c_start
                prev_sibling_title = c_title

            # Rule 6: Duplicate sibling titles at Topic and Subtopic levels only (ERROR)
            # At Activity and Subheading levels, duplicate titles are NOT errors.
            if c_level == "topic":
                if norm_tit in seen_topic_titles:
                    self.issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            rule_id="duplicate_sibling_title",
                            message=(
                                f"Duplicate sibling title '{c_title}' at Topic level under parent "
                                f"'{parent_node.get('official_title')}'"
                            ),
                            node_id=c_id,
                            node_title=c_title,
                            level=c_level,
                            page=c_start,
                            file=c_source,
                        )
                    )
                else:
                    seen_topic_titles[norm_tit] = c_id
            elif c_level == "subtopic":
                if norm_tit in seen_subtopic_titles:
                    self.issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            rule_id="duplicate_sibling_title",
                            message=(
                                f"Duplicate sibling title '{c_title}' at Subtopic level under parent "
                                f"'{parent_node.get('official_title')}'"
                            ),
                            node_id=c_id,
                            node_title=c_title,
                            level=c_level,
                            page=c_start,
                            file=c_source,
                        )
                    )
                else:
                    seen_subtopic_titles[norm_tit] = c_id

            # Recurse down children
            self._validate_children(child, parent=child, file_ctx=file_ctx)


def run_validation(
    books_dir: Path,
    only_file: Optional[str] = None,
    output_report_path: Optional[Path] = None,
) -> Tuple[int, int, Dict[str, Any]]:
    """
    Runs validation over books in books_dir (optionally filtered by only_file).
    Writes machine-readable error report JSON.
    Returns (total_errors, total_warnings, report_dict).
    """
    validator = CurriculumValidator()
    all_files = sorted(books_dir.glob("*.json"))

    if only_file:
        filter_str = only_file.replace(".json", "").replace(".pdf", "")
        matched = [f for f in all_files if filter_str in f.name]
        if not matched:
            # Maybe a direct path was given
            p = Path(only_file)
            if p.exists() and p.is_file():
                matched = [p]
        target_files = matched
    else:
        target_files = all_files

    report: Dict[str, Any] = {
        "total_files_checked": len(target_files),
        "files_with_errors": 0,
        "files_with_warnings": 0,
        "total_errors": 0,
        "total_warnings": 0,
        "issues_by_file": {},
    }

    total_errors = 0
    total_warnings = 0

    for bf in target_files:
        issues = validator.validate_file(bf)
        errors = [i for i in issues if i.severity == "ERROR"]
        warnings = [i for i in issues if i.severity == "WARNING"]

        total_errors += len(errors)
        total_warnings += len(warnings)

        if errors:
            report["files_with_errors"] += 1
        if warnings:
            report["files_with_warnings"] += 1

        if issues:
            report["issues_by_file"][bf.name] = [i.to_dict() for i in issues]

    report["total_errors"] = total_errors
    report["total_warnings"] = total_warnings

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return total_errors, total_warnings, report
