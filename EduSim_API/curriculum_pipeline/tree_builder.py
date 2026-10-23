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
            if cand_norm == norm_ch_title or (norm_wrapper and cand_norm == norm_wrapper):
                # Never fabricate/duplicate the chapter title as a topic or subtopic!
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
                if not target_parent:
                    target_parent = chapter_node
                    level_skipped = True

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
        if end_matter_page is not None and chapter_page_start <= end_matter_page <= chapter_page_end:
            self._cap_node_page_ends(chapter_node, end_matter_page)

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

        return chapter_node

    def _assign_ordinals_and_identity(self, parent_node: Dict[str, Any]):
        """Assigns stable occurrence_index among same-titled siblings and stable identity_key."""
        children = parent_node.get("nodes", [])
        counts: Dict[Tuple[str, str], int] = {}
        for child in children:
            lvl = child.get("level", "")
            tit = child.get("official_title", "").strip().lower()
            key = (lvl, tit)
            idx = counts.get(key, 0)
            child["occurrence_index"] = idx
            counts[key] = idx + 1
            num_part = f"{child.get('official_number')}:" if child.get("official_number") else ""
            child["identity_key"] = f"{lvl}:{num_part}{tit}:{idx}"
            self._assign_ordinals_and_identity(child)

    def _cap_node_page_ends(self, parent_node: Dict[str, Any], end_page: int):
        """Caps page_end of children so none extend past end_page."""
        for child in parent_node.get("nodes", []):
            if child.get("page_start", 0) <= end_page:
                child["page_end"] = min(child.get("page_end", end_page), end_page)
            self._cap_node_page_ends(child, end_page)

    def _adjust_page_ends(self, parent_node: Dict[str, Any], chapter_max_page: int):
        """Recursively update page_end of children to span until next sibling or parent end."""
        children = parent_node.get("nodes", [])
        for i, child in enumerate(children):
            if i + 1 < len(children):
                next_start = children[i + 1]["page_start"]
                if next_start > child["page_start"]:
                    child["page_end"] = max(child["page_start"], next_start - 1)
                else:
                    child["page_end"] = max(child["page_start"], next_start)
            else:
                child["page_end"] = max(child["page_start"], parent_node.get("page_end", chapter_max_page))

            # Ensure child page range remains strictly inside parent page range
            if "page_end" in parent_node:
                child["page_end"] = min(child["page_end"], parent_node["page_end"])
            if "page_start" in parent_node:
                child["page_start"] = max(child["page_start"], parent_node["page_start"])

            # Recurse
            self._adjust_page_ends(child, chapter_max_page)
