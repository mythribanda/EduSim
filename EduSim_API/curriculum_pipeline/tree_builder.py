"""
EduSim Curriculum Pipeline — Tree Builder
Assembles extracted chapter candidates into a strict, validated hierarchical tree:
Class -> Subject -> Book -> Chapter -> Topic -> Subtopic -> Activity -> Subheading.
Enforces:
  - Strict nesting: Chapter > Topic > Subtopic > Activity > Subheading.
  - Flags 'level_skipped: true' if a node skips an intervening level.
  - Page ranges: page_start = page where heading appears, page_end = page before next sibling-or-higher.
  - Flags topics spanning > 8 pages with 0 children as 'possible_missed_headings'.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class CurriculumTreeBuilder:
    def __init__(self, book_code: str):
        self.book_code = book_code
        self._node_counter = 0
        self.used_ids = set()

    def _next_id(self, prefix: str) -> str:
        while True:
            self._node_counter += 1
            nid = f"{self.book_code}_{prefix}_{self._node_counter}"
            if nid not in self.used_ids:
                self.used_ids.add(nid)
                return nid

    def build_chapter_tree(
        self,
        chapter_info: Dict[str, Any],
        raw_candidates: List[Dict[str, Any]],
        chapter_page_start: int,
        chapter_page_end: int,
        review_queue: Optional[List[Dict[str, Any]]] = None,
        file_id: str = "",
        end_matter_page: Optional[int] = None,
        end_matter_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds the Chapter node and nests Topic -> Subtopic -> Activity -> Subheading.
        Never invents missing nodes; handles level skipping transparently.
        """
        ch_id = chapter_info.get("id") or self._next_id("ch")
        self.used_ids.add(ch_id)
        official_title = chapter_info.get("official_title", "Chapter")
        norm_title = re.sub(r"\s+", " ", official_title).strip()

        chapter_node: Dict[str, Any] = {
            "id": ch_id,
            "parent_id": None,
            "level": "chapter",
            "wrapper": chapter_info.get("wrapper"),
            "official_number": str(chapter_info.get("official_number", "")) or None,
            "official_title": official_title,
            "normalized_title": norm_title,
            "page_start": chapter_page_start,
            "page_end": chapter_page_end,
            "extraction_type": "explicit",
            "evidence": chapter_info.get("evidence", official_title),
            "confidence": chapter_info.get("confidence", 1.0),
            "detection_method": "numbered",
            "rule_id": chapter_info.get("rule_id", "rule_chapter_official"),
            "structure_unresolved": False,
            "source_file": file_id,
            "ocr_needed": bool(chapter_info.get("ocr_needed", False)),
            "annotations": [],
            "nodes": [],
        }

        if not raw_candidates:
            chapter_node["structure_unresolved"] = True
            self._assign_source_pages(chapter_node, chapter_page_start)
            return chapter_node

        # Filter out candidates that start strictly after end_matter_page
        effective_candidates = raw_candidates
        if end_matter_page is not None:
            effective_candidates = [c for c in raw_candidates if c.get("page", 0) <= end_matter_page]

        # Suppress any candidates that duplicate chapter title or wrapper
        norm_ch_title = re.sub(r"[^\w]", "", official_title).lower()
        norm_wrapper = re.sub(r"[^\w]", "", str(chapter_info.get("wrapper") or "")).lower()

        # Maintain pointers to the active hierarchy
        current_topic: Optional[Dict[str, Any]] = None
        current_subtopic: Optional[Dict[str, Any]] = None
        current_activity: Optional[Dict[str, Any]] = None

        for cand in effective_candidates:
            level = cand["level"]
            page = cand["page"]
            title = cand["official_title"]
            norm_t = cand["normalized_title"]
            num = cand.get("official_number")
            conf = cand.get("confidence", 0.8)
            rule = cand.get("rule_id", "rule_extracted")
            method = cand.get("detection_method", "style")
            evidence = cand.get("evidence", title)
            kind = cand.get("kind")
            cand_ocr = bool(cand.get("ocr_needed", False))

            cand_norm = re.sub(r"[^\w]", "", title).lower()
            if re.match(r"^UNIT(\s*[-–—]\s*\d+|\s+\d+)?$", title.strip(), re.I):
                if not chapter_node.get("wrapper"):
                    chapter_node["wrapper"] = title.strip()
                continue
            if not num:
                if cand_norm == norm_ch_title or (norm_wrapper and cand_norm == norm_wrapper):
                    # Never fabricate/duplicate the unnumbered chapter title as a topic or subtopic!
                    continue

            # On chapter start page, suppress candidates that are fragments of chapter title or wrapper or chapter labels
            if page == chapter_page_start:
                if not num:
                    if cand_norm and (cand_norm in norm_ch_title or norm_ch_title in cand_norm):
                        continue
                    if norm_wrapper and (cand_norm in norm_wrapper or norm_wrapper in cand_norm):
                        continue
                if re.match(r"^chapter\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\b", title.strip(), re.I):
                    continue


            if level == "topic":
                # Check if this topic already exists under this chapter (multi-page continuation, repeated banner, or matching official_number)
                norm_lower = norm_t.strip().lower()
                existing_topic = next(
                    (
                        n for n in chapter_node["nodes"]
                        if n.get("level") == "topic"
                        and (
                            (num and n.get("official_number") and n.get("official_number") == num)
                            or (not num and not n.get("official_number") and n.get("normalized_title", "").strip().lower() == norm_lower)
                        )
                    ),
                    None
                )
                if existing_topic:
                    # If existing topic was a TOC-box entry on chapter start page and this is the full section heading on page > chapter_page_start:
                    if (
                        existing_topic.get("page_start") == chapter_page_start
                        and page > chapter_page_start
                        and existing_topic.get("normalized_title", "").strip().lower() == norm_t.strip().lower()
                    ):
                        existing_topic["page_start"] = page
                        existing_topic["official_title"] = title
                        existing_topic["normalized_title"] = norm_t
                        existing_topic["evidence"] = evidence
                        existing_topic["confidence"] = conf
                        existing_topic["rule_id"] = rule
                    existing_topic["page_end"] = max(existing_topic["page_end"], page)
                    current_topic = existing_topic
                    current_subtopic = None
                    current_activity = None
                    continue

                node_id = self._next_id("top")
                node = {
                    "id": node_id,
                    "parent_id": ch_id,
                    "level": "topic",
                    "official_number": num,
                    "official_title": title,
                    "normalized_title": norm_t,
                    "page_start": page,
                    "page_end": page,
                    "extraction_type": "explicit",
                    "evidence": evidence,
                    "confidence": conf,
                    "detection_method": method,
                    "rule_id": rule,
                    "level_skipped": False,
                    "source_file": file_id,
                    "ocr_needed": cand_ocr,
                    "annotations": [],
                    "nodes": [],
                }
                chapter_node["nodes"].append(node)
                current_topic = node
                current_subtopic = None
                current_activity = None

            elif level == "subtopic":
                target_parent = current_topic
                level_skipped = False
                # If candidate has official_number (e.g. "10.1.2"), verify if parent topic matches prefix (e.g. "10.1")
                if num and "." in str(num):
                    parent_num = str(num).rsplit(".", 1)[0]
                    matching_top = next(
                        (n for n in chapter_node["nodes"] if n.get("level") == "topic" and n.get("official_number") == parent_num),
                        None
                    )
                    if matching_top:
                        target_parent = matching_top
                        current_topic = matching_top
                        level_skipped = False

                if not target_parent:
                    target_parent = chapter_node
                    level_skipped = True

                # Check if this subtopic already exists under target_parent
                norm_lower = norm_t.strip().lower()
                existing_subtopic = next(
                    (
                        n for n in target_parent["nodes"]
                        if n.get("level") == "subtopic"
                        and (
                            (num and n.get("official_number") and n.get("official_number") == num)
                            or (not num and not n.get("official_number") and n.get("normalized_title", "").strip().lower() == norm_lower)
                        )
                    ),
                    None
                )
                if existing_subtopic:
                    if (
                        existing_subtopic.get("page_start") == chapter_page_start
                        and page > chapter_page_start
                        and existing_subtopic.get("normalized_title", "").strip().lower() == norm_t.strip().lower()
                    ):
                        existing_subtopic["page_start"] = page
                        existing_subtopic["official_title"] = title
                        existing_subtopic["normalized_title"] = norm_t
                    existing_subtopic["page_end"] = max(existing_subtopic["page_end"], page)
                    current_subtopic = existing_subtopic
                    current_activity = None
                    continue

                node_id = self._next_id("subtop")
                node = {
                    "id": node_id,
                    "parent_id": target_parent["id"],
                    "level": "subtopic",
                    "official_number": num,
                    "official_title": title,
                    "normalized_title": norm_t,
                    "page_start": page,
                    "page_end": page,
                    "extraction_type": "explicit",
                    "evidence": evidence,
                    "confidence": conf,
                    "detection_method": method,
                    "rule_id": rule,
                    "level_skipped": level_skipped,
                    "source_file": file_id,
                    "ocr_needed": cand_ocr,
                    "annotations": [],
                    "nodes": [],
                }
                target_parent["nodes"].append(node)
                current_subtopic = node
                current_activity = None

            elif level == "activity":
                target_parent = current_subtopic or current_topic
                level_skipped = False
                if not current_subtopic:
                    level_skipped = True
                if not target_parent:
                    target_parent = chapter_node
                    level_skipped = True

                clean_kind = re.sub(r"[^\w]", "_", str(kind or "activity")).lower()
                clean_num = re.sub(r"[^\w\.]", "_", str(num)).strip("_") if num else ""
                if clean_num:
                    base_id = f"{target_parent['id']}_act_{clean_kind}_{clean_num}"
                else:
                    base_id = f"{target_parent['id']}_act_{clean_kind}_{self._node_counter + 1}"

                if base_id in self.used_ids:
                    idx = 2
                    while f"{base_id}_{idx}" in self.used_ids:
                        idx += 1
                    node_id = f"{base_id}_{idx}"
                else:
                    node_id = base_id
                self.used_ids.add(node_id)

                node = {
                    "id": node_id,
                    "parent_id": target_parent["id"],
                    "level": "activity",
                    "kind": kind or "activity",
                    "official_number": num,
                    "official_title": title,
                    "preview": cand.get("preview"),
                    "normalized_title": norm_t,
                    "page_start": page,
                    "page_end": page,
                    "extraction_type": "explicit",
                    "evidence": evidence,
                    "confidence": conf,
                    "detection_method": method,
                    "rule_id": rule,
                    "level_skipped": level_skipped,
                    "source_file": file_id,
                    "ocr_needed": cand_ocr,
                    "annotations": [],
                    "nodes": [],
                }
                target_parent["nodes"].append(node)
                current_activity = node

            elif level == "subheading":
                target_parent = current_activity or current_subtopic or current_topic
                level_skipped = False
                if not current_activity:
                    level_skipped = True
                if not target_parent:
                    target_parent = chapter_node
                    level_skipped = True

                node_id = self._next_id("subh")
                node = {
                    "id": node_id,
                    "parent_id": target_parent["id"],
                    "level": "subheading",
                    "official_number": num,
                    "official_title": title,
                    "normalized_title": norm_t,
                    "page_start": page,
                    "page_end": page,
                    "extraction_type": "explicit",
                    "evidence": evidence,
                    "confidence": conf,
                    "detection_method": method,
                    "rule_id": rule,
                    "level_skipped": level_skipped,
                    "source_file": file_id,
                    "ocr_needed": cand_ocr,
                    "annotations": [],
                    "nodes": [],
                }
                target_parent["nodes"].append(node)

        # Fix end pages across nodes sequentially
        self._adjust_page_ends(chapter_node, chapter_page_end)

        # Handle Summary/Exercises boundary (cap node page ends, do not fabricate nodes)
        chapter_node["unstructured_ranges"] = []
        if end_matter_page is not None and chapter_page_start <= end_matter_page <= chapter_page_end:
            self._cap_node_page_ends(chapter_node, end_matter_page)

        # Determine uncovered trailing pages (Summary/Exercises/Back Matter)
        def _get_max_page_end(n: Dict[str, Any]) -> int:
            mp = n.get("page_end", 0)
            for child in n.get("nodes", []):
                mp = max(mp, _get_max_page_end(child))
            return mp

        max_node_page = 0
        if chapter_node.get("nodes"):
            max_node_page = max(_get_max_page_end(c) for c in chapter_node["nodes"])

        if max_node_page > 0 and max_node_page < chapter_page_end:
            raw_label = (end_matter_label or "SUMMARY").strip().upper()
            # Collapse letter-spaced words e.g. 'S U M M A R Y' -> 'SUMMARY'
            if re.search(r"\b[A-Z]\s+[A-Z]\b", raw_label):
                norm_label = re.sub(r"(?<=[A-Z])\s+(?=[A-Z])", "", raw_label)
            else:
                norm_label = raw_label
            clean_token = re.sub(r"[^\w]", "", norm_label)
            if "SUMMARY" in clean_token:
                norm_label = "SUMMARY"
            elif "EXERCISE" in clean_token:
                norm_label = "EXERCISES"
            elif "SOLUTION" in clean_token:
                norm_label = "SOLUTIONS"
            elif "ANSWER" in clean_token:
                norm_label = "ANSWERS"
            elif clean_token.startswith("WHATYOUHAVELEARN"):
                norm_label = "WHAT YOU HAVE LEARNT"
            elif clean_token.startswith("POINTSTOPONDER"):
                norm_label = "POINTS TO PONDER"

            chapter_node["unstructured_ranges"].append({
                "page_start": max_node_page + 1,
                "page_end": chapter_page_end,
                "reason": norm_label,
            })

        # Assign stable occurrence ordinals and identity keys to all sibling nodes
        self._assign_ordinals_and_identity(chapter_node)


        # Flag any topic spanning > 8 pages with 0 children, or topic with > 40 subheadings
        def _count_subheadings(n: Dict[str, Any]) -> int:
            cnt = 1 if n.get("level") == "subheading" else 0
            for child in n.get("nodes", []):
                cnt += _count_subheadings(child)
            return cnt

        for top_node in chapter_node.get("nodes", []):
            if top_node.get("level") == "topic":
                p_span = top_node["page_end"] - top_node["page_start"] + 1
                child_count = len(top_node.get("nodes", []))
                if p_span > 8 and child_count == 0:
                    top_node["possible_missed_headings"] = True
                    if review_queue is not None:
                        review_queue.append({
                            "file": file_id,
                            "page": top_node["page_start"],
                            "problem": "possible_missed_headings",
                            "found_text": f"Topic '{top_node['official_title']}' spans {p_span} pages with 0 sub-nodes",
                            "suggested_action": "Check page spans for missed unnumbered subtopics",
                        })

                sh_cnt = _count_subheadings(top_node)
                if sh_cnt > 40:
                    top_node["subheading_noise"] = True
                    if review_queue is not None:
                        review_queue.append({
                            "file": file_id,
                            "page": top_node["page_start"],
                            "problem": "subheading_noise",
                            "found_text": f"Topic '{top_node['official_title']}' has {sh_cnt} subheadings (> 40)",
                            "suggested_action": "Audit subheadings; check for body text promotion",
                        })

        # Assign source_page_start and source_page_end (local pages within file)
        self._assign_source_pages(chapter_node, chapter_page_start)

        return chapter_node

    def _assign_ordinals_and_identity(self, parent_node: Dict[str, Any]):
        """Assigns stable occurrence_index among same-titled siblings and stable identity_key."""
        children = parent_node.get("nodes", [])
        counts: Dict[Tuple[str, str], int] = {}
        for child in children:
            lvl = child.get("level", "")
            norm_t = re.sub(r"\s+", " ", child.get("normalized_title") or child.get("official_title", "")).strip().lower()
            key = (lvl, norm_t)
            idx = counts.get(key, 0)
            child["occurrence_index"] = idx
            counts[key] = idx + 1
            num_part = f"{child.get('official_number')}:" if child.get("official_number") else ""
            child["identity_key"] = f"{lvl}:{num_part}{norm_t}:{idx}"
            self._assign_ordinals_and_identity(child)

    def _cap_node_page_ends(self, parent_node: Dict[str, Any], end_page: int):
        """Caps page_end of children so none extend into or past end_page."""
        for child in parent_node.get("nodes", []):
            self._cap_node_page_ends(child, end_page)
            if child.get("page_start", 0) < end_page:
                child["page_end"] = min(child.get("page_end", end_page - 1), end_page - 1)
                child["page_end"] = max(child["page_start"], child["page_end"])
            # Child must encompass all of its own sub-nodes
            sub_nodes = child.get("nodes", [])
            if sub_nodes:
                child["page_end"] = max(child["page_end"], max(sn["page_end"] for sn in sub_nodes))
                child["page_start"] = min(child["page_start"], min(sn["page_start"] for sn in sub_nodes))

        # Parent must encompass all its children
        children = parent_node.get("nodes", [])
        if children:
            parent_node["page_end"] = max(parent_node.get("page_end", 0), max(c["page_end"] for c in children))
            parent_node["page_start"] = min(parent_node.get("page_start", 1), min(c["page_start"] for c in children))

    def _adjust_page_ends(self, parent_node: Dict[str, Any], chapter_max_page: int):
        """Recursively update page_end of children to span until next sibling or parent end."""
        children = parent_node.get("nodes", [])
        if not children:
            return

        # 1. Recurse down so child subtrees are adjusted first
        for child in children:
            self._adjust_page_ends(child, chapter_max_page)
            # Child must encompass all of its own sub-nodes
            sub_nodes = child.get("nodes", [])
            if sub_nodes:
                child["page_end"] = max(child["page_end"], max(sn["page_end"] for sn in sub_nodes))
                child["page_start"] = min(child["page_start"], min(sn["page_start"] for sn in sub_nodes))

        # 2. Sequential sibling adjustment
        for i, child in enumerate(children):
            if child.get("level") == "activity" and (self.book_code.startswith("ssc_") or child.get("single_page")):
                child["page_end"] = child.get("page_start", 1)
                continue
            if i + 1 < len(children):
                next_start = children[i + 1]["page_start"]
                if next_start > child["page_end"]:
                    child["page_end"] = max(child["page_end"], next_start - 1)
                elif next_start == child["page_end"]:
                    child["page_end"] = next_start
                else:
                    child["page_end"] = max(child["page_end"], next_start)
            else:
                child["page_end"] = max(child["page_end"], parent_node.get("page_end", chapter_max_page))

        # 3. Parent must encompass all its children
        if children:
            parent_node["page_end"] = max(parent_node.get("page_end", chapter_max_page), max(c["page_end"] for c in children))
            parent_node["page_start"] = min(parent_node.get("page_start", 1), min(c["page_start"] for c in children))

        # 4. Final clamp to guarantee child is strictly within parent
        for child in children:
            if child.get("level") == "activity" and (self.book_code.startswith("ssc_") or child.get("single_page")):
                child["page_end"] = child.get("page_start", 1)
            elif "page_end" in parent_node:
                child["page_end"] = min(child["page_end"], parent_node["page_end"])
            if "page_start" in parent_node:
                child["page_start"] = max(child["page_start"], parent_node["page_start"])

    def _assign_source_pages(self, node: Dict[str, Any], chapter_start: int):
        """Assigns 1-based source_page_start and source_page_end within the node's source file."""
        is_ssc = self.book_code.startswith("ssc_")
        if is_ssc:
            node["source_page_start"] = node.get("page_start", 1)
            node["source_page_end"] = node.get("page_end", 1)
        else:
            p_s = node.get("page_start", chapter_start)
            p_e = node.get("page_end", chapter_start)
            node["source_page_start"] = max(1, p_s - chapter_start + 1)
            node["source_page_end"] = max(node["source_page_start"], p_e - chapter_start + 1)

        for child in node.get("nodes", []):
            self._assign_source_pages(child, chapter_start)
