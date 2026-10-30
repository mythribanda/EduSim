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

PLAUSIBILITY_RULES = {
    "title_starts_lowercase",
    "title_ends_comma",
    "unbalanced_quotes",
    "title_contains_sentence_boundary",
    "title_word_count_exceeded",
    "bare_unit_token",
    "dangling_function_word",
}

DANGLING_FUNCTION_WORDS_REGEX = re.compile(
    r"\b(and|of|the|for|in|to|a|an|with|or|on|by|from|between|laws?\s+of)\s*$",
    re.I,
)


def check_title_plausibility(title: str, level: str = "") -> Optional[Tuple[str, str]]:
    t = str(title or "").strip()
    if not t:
        return ("empty_title", "Title is empty or whitespace-only")

    # 1. Title starting with lowercase letter (ASCII alphabetic)
    if t[0].isascii() and t[0].isalpha() and t[0].islower():
        return ("title_starts_lowercase", f"Title '{t}' starts with a lowercase letter")

    # 2. Title ending in a comma
    if t.rstrip().endswith(","):
        return ("title_ends_comma", f"Title '{t}' ends in a comma")

    # 3. Unbalanced quotes
    # Strip word-internal apostrophes (straight or curly) e.g. Dalton's, don't, Gauss's, Dalton’s
    s = re.sub(r"[a-zA-Z][\x27\u2019][a-zA-Z]?", "", t)
    if s.count('"') % 2 != 0:
        return ("unbalanced_quotes", f"Title '{t}' contains unbalanced double quotes")
    if s.count('“') != s.count('”'):
        return ("unbalanced_quotes", f"Title '{t}' contains unbalanced curly double quotes")
    if s.count('‘') != s.count('’'):
        return ("unbalanced_quotes", f"Title '{t}' contains unbalanced curly single quotes")
    if s.count("'") % 2 != 0:
        return ("unbalanced_quotes", f"Title '{t}' contains unbalanced single quotes")

    # 4. Title containing a sentence boundary (". " followed by a letter)
    if re.search(r"\.\s+[A-Za-z]", t):
        return ("title_contains_sentence_boundary", f"Title '{t}' contains a sentence boundary")

    # 5. Titles of more than 12 words at the Subtopic and Subheading levels
    if level in ["subtopic", "subheading"] and len(t.split()) > 12:
        return (
            "title_word_count_exceeded",
            f"Title '{t}' exceeds 12 words at level '{level}' ({len(t.split())} words)",
        )

    # 6. Bare "UNIT" / "Unit N" token as heading
    if re.match(r"^UNIT(\s*[-–—]\s*\d+|\s+\d+)?$", t, re.I):
        return ("bare_unit_token", f"Title '{t}' is a bare UNIT token")

    return None


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
    source_file: Optional[str] = None
    ocr_needed: bool = False
    occurrence_index: Optional[int] = None
    identity_key: Optional[str] = None
    nodes: List[Dict[str, Any]] = Field(default_factory=list)


class CurriculumValidator:
    """Validates curriculum nodes and trees against structural and hierarchy rules."""

    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.total_nodes_count: int = 0
        self.suspicious_node_ids: set = set()
        self.seen_node_ids: Dict[str, str] = {}
        self.seen_identity_keys: Dict[str, str] = {}

    def get_suspicion_metrics(self, is_ssc: bool = False) -> Tuple[float, str]:
        """Returns (suspicion_score, extraction_status)."""
        score = len(self.suspicious_node_ids) / max(1, self.total_nodes_count)
        status = "needs_review" if (score > 0.10 or is_ssc) else "ok"
        return round(score, 4), status

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
        self.total_nodes_count = 0
        self.suspicious_node_ids = set()
        self.seen_node_ids = {}
        self.seen_identity_keys = {}

        # If data is a book curriculum with chapters list
        if "chapters" in data and isinstance(data["chapters"], list):
            seen_chapter_keys: Dict[str, str] = {}
            for ch in data["chapters"]:
                ch_key = ch.get("identity_key")
                if ch_key is not None:
                    k_str = str(ch_key).strip()
                    if k_str:
                        if k_str in seen_chapter_keys:
                            self.issues.append(
                                ValidationIssue(
                                    severity="ERROR",
                                    rule_id="duplicate_node_id",
                                    message=f"Duplicate identity_key '{k_str}' found in tree (already seen in '{seen_chapter_keys[k_str]}')",
                                    node_id=str(ch.get("id")) if ch.get("id") is not None else None,
                                    node_title=str(ch.get("official_title", "")).strip() or None,
                                    level="chapter",
                                    page=ch.get("page_start") if isinstance(ch.get("page_start"), int) else None,
                                    file=ch.get("source_file", source_filename),
                                )
                            )
                        else:
                            seen_chapter_keys[k_str] = str(ch.get("official_title", "")).strip() or k_str
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

        # WARNING: Chapter with no unstructured_ranges whose last node ends on the chapter's final page
        unstruct = ch.get("unstructured_ranges", [])
        ch_end = ch.get("page_end", 0)

        def _get_max_child_end(n: Dict[str, Any]) -> int:
            m = n.get("page_end", 0)
            for c in n.get("nodes", []):
                m = max(m, _get_max_child_end(c))
            return m

        ch_nodes = ch.get("nodes", [])
        max_node_end = max((_get_max_child_end(n) for n in ch_nodes), default=0)
        if len(unstruct) == 0 and max_node_end == ch_end and len(ch_nodes) > 0:
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id="chapter_missing_end_matter",
                    message=f"Chapter '{ch_title}' has no unstructured_ranges and its last node ends on chapter end (page {ch_end})",
                    node_id=ch_id,
                    node_title=ch_title,
                    level="chapter",
                    page=ch_end,
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

        # 0. Pydantic schema validation (ERROR)
        node_to_validate = dict(node)
        if not node_to_validate.get("source_file") and file_ctx:
            node_to_validate["source_file"] = file_ctx

        try:
            NodeSchema.model_validate(node_to_validate)
        except ValidationError as e:
            for err in e.errors():
                loc = err.get("loc", ())
                field = str(loc[-1]) if loc else "node"
                msg = err.get("msg", "Schema validation failed")
                self.issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        rule_id="schema_validation_error",
                        message=f"Node '{node_id}' failed schema validation on '{field}': {msg}",
                        node_id=str(node_id) if node_id is not None else None,
                        node_title=str(raw_title) if raw_title is not None else None,
                        level=str(level) if level is not None else None,
                        page=page_start if isinstance(page_start, int) else None,
                        file=source_file,
                    )
                )

        # Duplicate node id check within tree (ERROR)
        if node_id is not None:
            nid_str = str(node_id).strip()
            if nid_str:
                if nid_str in self.seen_node_ids:
                    self.issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            rule_id="duplicate_node_id",
                            message=f"Duplicate node id '{nid_str}' found in tree (already seen in '{self.seen_node_ids[nid_str]}')",
                            node_id=nid_str,
                            node_title=str(raw_title).strip() if raw_title else None,
                            level=str(level) if level else None,
                            page=page_start if isinstance(page_start, int) else None,
                            file=source_file,
                        )
                    )
                else:
                    self.seen_node_ids[nid_str] = str(raw_title).strip() if raw_title else nid_str

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

        # WARNING: Node spans many pages (> 12 pages for topic or subtopic)
        if level in ["topic", "subtopic"]:
            p_span = page_end - page_start + 1
            if p_span > 12:
                self.issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        rule_id="node_spans_many_pages",
                        message=f"{level.capitalize()} '{title}' spans {p_span} pages (> 12 pages, {page_start}-{page_end})",
                        node_id=node_id,
                        node_title=title,
                        level=level,
                        page=page_start,
                        file=source_file,
                    )
                )

        # WARNING: Numbered subtopic X.Y.Z whose parent topic is not X.Y
        if parent is not None and level == "subtopic":
            c_num = node.get("official_number")
            if c_num and isinstance(c_num, str):
                parts = c_num.split(".")
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    expected_topic_num = f"{parts[0]}.{parts[1]}"
                    p_num = str(parent.get("official_number") or "").strip()
                    if p_num and p_num != expected_topic_num:
                        self.issues.append(
                            ValidationIssue(
                                severity="WARNING",
                                rule_id="subtopic_parent_number_mismatch",
                                message=(
                                    f"Numbered subtopic '{title}' ({c_num}) has parent topic "
                                    f"'{parent.get('official_title')}' ({p_num}), expected '{expected_topic_num}'"
                                ),
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

        self.total_nodes_count += 1

        # WARNING: Numbered heading ending with dangling function word
        c_num = node.get("official_number")
        if c_num and isinstance(c_num, str):
            if DANGLING_FUNCTION_WORDS_REGEX.search(title.strip()):
                self.issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        rule_id="dangling_function_word",
                        message=f"Numbered heading '{title}' ({c_num}) ends with a dangling function word",
                        node_id=node_id,
                        node_title=title,
                        level=level,
                        page=page_start,
                        file=source_file,
                    )
                )
                if node_id:
                    self.suspicious_node_ids.add(node_id)

        # WARNING: Plausibility checks on title
        p_res = check_title_plausibility(title, level)
        if p_res:
            p_rule, p_msg = p_res
            self.issues.append(
                ValidationIssue(
                    severity="WARNING",
                    rule_id=p_rule,
                    message=f"Node '{node_id}' ({level}) '{title}' failed plausibility: {p_msg}",
                    node_id=node_id,
                    node_title=title,
                    level=level,
                    page=page_start,
                    file=source_file,
                )
            )
            if node_id:
                self.suspicious_node_ids.add(node_id)

    def _validate_children(self, parent_node: Dict[str, Any], parent: Dict[str, Any], file_ctx: str):
        children = parent_node.get("nodes", [])
        if not children:
            return

        seen_topic_titles: Dict[str, str] = {}
        seen_subtopic_titles: Dict[str, str] = {}
        seen_sibling_identity_keys: Dict[str, str] = {}
        prev_sibling_start: Optional[int] = None
        prev_sibling_title: Optional[str] = None
        prev_num_by_level: Dict[str, Tuple[Tuple[int, ...], str, str]] = {}

        for child in children:
            # Validate individual node properties & parent-child nesting
            self._validate_single_node(child, parent=parent_node, file_ctx=file_ctx)

            c_level = child.get("level")
            c_title = str(child.get("official_title") or "").strip()
            c_id = child.get("id")
            c_source = child.get("source_file", file_ctx)
            c_start = child.get("page_start")
            c_num = child.get("official_number")
            c_key = child.get("identity_key")
            norm_tit = re.sub(r"\s+", " ", c_title).lower()

            # Duplicate sibling identity_key check (ERROR)
            if c_key is not None:
                k_str = str(c_key).strip()
                if k_str:
                    if k_str in seen_sibling_identity_keys:
                        self.issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                rule_id="duplicate_node_id",
                                message=f"Duplicate identity_key '{k_str}' found in tree (already seen in '{seen_sibling_identity_keys[k_str]}')",
                                node_id=str(c_id) if c_id is not None else None,
                                node_title=c_title or None,
                                level=c_level,
                                page=c_start if isinstance(c_start, int) else None,
                                file=c_source,
                            )
                        )
                    else:
                        seen_sibling_identity_keys[k_str] = c_title or k_str

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

        # WARNING: Sibling order by number (evaluated per level)
            num_tuple = None
            if c_num and isinstance(c_num, str):
                try:
                    num_tuple = tuple(int(p) for p in re.findall(r"\d+", c_num))
                except Exception:
                    num_tuple = None

            if num_tuple and c_level in prev_num_by_level:
                prev_tuple, prev_str, prev_title = prev_num_by_level[c_level]
                if len(num_tuple) == len(prev_tuple) and num_tuple < prev_tuple:
                    self.issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            rule_id="sibling_order_by_number",
                            message=(
                                f"Numbered sibling '{c_title}' ({c_num}) appears out of numeric order "
                                f"after '{prev_title}' ({prev_str}) at level '{c_level}'"
                            ),
                            node_id=c_id,
                            node_title=c_title,
                            level=c_level,
                            page=c_start,
                            file=c_source,
                        )
                    )

            if num_tuple:
                prev_num_by_level[c_level] = (num_tuple, c_num, c_title)

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
        "suspicion_scores": {},
    }

    total_errors = 0
    total_warnings = 0

    for bf in target_files:
        issues = validator.validate_file(bf)
        errors = [i for i in issues if i.severity == "ERROR"]
        warnings = [i for i in issues if i.severity == "WARNING"]

        total_errors += len(errors)
        total_warnings += len(warnings)

        score, status = validator.get_suspicion_metrics(is_ssc="ssc" in bf.name.lower())
        report["suspicion_scores"][bf.name] = {
            "score": score,
            "suspicious_nodes": len(validator.suspicious_node_ids),
            "total_nodes": validator.total_nodes_count,
            "status": status,
        }

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
