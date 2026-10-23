"""
EduSim Curriculum Pipeline — Specialized Subject Adapters
Adapters for:
  - Maths: sections, Example/Exercise/Theorem/Proposition blocks as activity nodes, unnumbered subtopics
  - Science: experiment/activity boxes, bold side headings as subtopics, numbered sections
  - Language: Prose/Poem genre wrappers, "Let us..." activities, stanza/section titles
  - Social Science: Themes, Case studies, "Let's Recall", "Let's Explore", Sources
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from curriculum_pipeline.adapters.base_adapter import BaseSubjectAdapter


class MathsAdapter(BaseSubjectAdapter):
    adapter_name = "maths"

    def is_activity_heading(self, line: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
        res = super().is_activity_heading(line)
        if res[0]:
            return res

        line_clean = line.strip()
        # Maths specific: Solved Problems, Try These
        m_try = re.match(r"^(Try\s+These|Solved\s+Problems)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_try:
            lbl = m_try.group(1).strip()
            rest = m_try.group(2).strip()
            return True, "activity", None, lbl, rest[:80] if rest else None
        return False, None, None, None, None


class ScienceAdapter(BaseSubjectAdapter):
    adapter_name = "science"

    def is_activity_heading(self, line: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
        res = super().is_activity_heading(line)
        if res[0]:
            return res

        line_clean = line.strip()
        # Science specific: Lab Activity, Investigation, Experiment
        m_sci = re.match(r"^(Lab\s+Activity|Investigation|Experiment)\s*([0-9\.]+)?\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_sci:
            lbl = m_sci.group(1).strip()
            num = m_sci.group(2)
            rest = m_sci.group(3).strip()
            title = f"{lbl} {num}" if num else lbl
            return True, "activity", num, title, rest[:80] if rest else None
        return False, None, None, None, None


class LanguageAdapter(BaseSubjectAdapter):
    adapter_name = "language"

    def extract_nodes_from_lines(
        self,
        page_no: int,
        lines_with_spans: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        nodes = super().extract_nodes_from_lines(page_no, lines_with_spans)
        # Additional language specific: Prose / Poem / Section markers as subtopics
        for line_info in lines_with_spans:
            line = line_info.get("text", "").strip()
            if re.match(r"^(Prose|Poem|Poetry|Story|Short\s+Story|कविता|कहानी|गद्य|पद्य|పాఠం)\b", line, re.I):
                nodes.append({
                    "level": "subtopic",
                    "kind": "genre",
                    "official_number": None,
                    "official_title": line,
                    "normalized_title": re.sub(r"\s+", " ", line).strip(),
                    "page": page_no,
                    "evidence": line,
                    "confidence": 0.90,
                    "detection_method": "lexicon",
                    "rule_id": "rule_language_genre_subtopic",
                })
        return nodes


class SocialScienceAdapter(BaseSubjectAdapter):
    adapter_name = "social_science"

    def is_activity_heading(self, line: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
        res = super().is_activity_heading(line)
        if res[0]:
            return res

        line_clean = line.strip()
        m_soc = re.match(r"^(Case\s+Study|Source|Let\'s\s+Recall|Let\'s\s+Explore|Map\s+Reading)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_soc:
            lbl = m_soc.group(1).strip()
            rest = m_soc.group(2).strip()
            return True, "activity", None, lbl, rest[:80] if rest else None
        return False, None, None, None, None


def get_adapter_for_subject(
    subject: str,
    style_profile: Dict[str, Any],
    language: str = "en",
) -> BaseSubjectAdapter:
    subj = (subject or "").lower()
    if "math" in subj:
        return MathsAdapter(style_profile, language=language)
    elif any(k in subj for k in ["science", "physics", "chemistry", "biology"]):
        return ScienceAdapter(style_profile, language=language)
    elif any(k in subj for k in ["english", "hindi", "telugu", "sanskrit", "urdu"]):
        return LanguageAdapter(style_profile, language=language)
    elif any(k in subj for k in ["social", "history", "geography", "political", "civics", "economics", "evs"]):
        return SocialScienceAdapter(style_profile, language=language)
    return BaseSubjectAdapter(style_profile, language=language)
