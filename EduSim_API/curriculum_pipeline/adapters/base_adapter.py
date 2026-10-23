"""
EduSim Curriculum Pipeline — Base Subject Adapter
Provides robust multi-level heading detection, numbered extraction, run-in bold extraction,
activity classification, and tree node generation across all levels:
Chapter -> Topic -> Subtopic -> Activity -> Subheading.
"""

from __future__ import annotations

import re
from collections import Counter
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from curriculum_pipeline.pipeline_config import API_ROOT

KEYWORDS_FILE = API_ROOT / "curriculum_pipeline" / "config" / "activity_keywords.yaml"


class BaseSubjectAdapter:
    adapter_name: str = "base"

    def __init__(self, style_profile: Dict[str, Any], language: str = "en"):
        self.profile = style_profile
        self.language = language or "en"
        self.ranks = style_profile.get("ranks", {})
        self.body_size = style_profile.get("body_size", 10.0)
        self.activity_keywords = self._load_activity_keywords()
        self.end_of_chapter_reached = False
        self.end_matter_page = None
        self.end_matter_label = None
        self.last_topic_tuple = None
        self.current_chapter_number: Optional[str] = None

    def reset_chapter_state(self, chapter_number: Optional[Any] = None):
        self.current_chapter_number = str(chapter_number) if chapter_number is not None else None
        self.end_of_chapter_reached = False
        self.end_matter_page = None
        self.end_matter_label = None
        self.last_topic_tuple = None

    def _load_activity_keywords(self) -> List[str]:
        if not KEYWORDS_FILE.exists():
            return ["Activity", "Let us do", "Exercise", "Project", "Experiment", "Example"]
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            kws = list(data.get(self.language, []))
            if self.language != "en":
                kws.extend(data.get("en", []))
            return [k.strip() for k in kws if k.strip()]
        except Exception:
            return ["Activity", "Let us do", "Exercise", "Project", "Experiment", "Example"]

    def is_activity_heading(self, line: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Checks if line is an activity heading.
        Returns (is_activity, kind, official_number, title, preview).
        Separates official_number from title (e.g. number='1.1', title='Activity 1.1').
        Rejects lowercase or caption words (e.g. 'observe', 'example', 'source').
        """
        line_clean = line.strip()
        if not line_clean or line_clean[0].islower():
            return False, None, None, None, None

        # 1. Example
        m_ex = re.match(r"^(Example|उदाहरण|ఉదాహరణ|مثال)\s*([0-9]+(?:\.[0-9]+)*[a-zA-Z]?)\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_ex:
            lbl = m_ex.group(1).capitalize()
            num = m_ex.group(2)
            rest = m_ex.group(3).strip()
            if num:
                title = f"{lbl} {num}"
                preview = rest[:80] if rest else None
                return True, "example", num, title, preview
            elif rest and (":" in line_clean or len(rest.split()) <= 10):
                # Unnumbered illustrative example with subtitle e.g. "Example: What happens..."
                title = f"{lbl}: {rest[:80]}".strip()
                return True, "example", None, title, rest[:80]
            elif ":" in line_clean:
                title = lbl
                return True, "example", None, title, rest[:80] if rest else None
            return False, None, None, None, None

        # 2. Exercise
        m_exercise = re.match(r"^(Exercise|Miscellaneous\s+Exercise|अभ्यास|అభ్యాసం|مشق)\s*([0-9\.]+)?\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_exercise:
            lbl = m_exercise.group(1).strip()
            num = m_exercise.group(2)
            rest = m_exercise.group(3).strip()
            title = f"{lbl} {num}" if num else lbl
            preview = rest[:80] if rest else None
            return True, "exercise", num, title, preview

        # 3. Theorem
        m_thm = re.match(r"^(Theorem|Proposition|Corollary|प्रमेय|సిద్ధాంతం)\s*([0-9\.]+)?\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_thm:
            lbl = m_thm.group(1).capitalize()
            num = m_thm.group(2)
            rest = m_thm.group(3).strip()
            title = f"{lbl} {num}" if num else lbl
            preview = rest[:80] if rest else None
            return True, "theorem", num, title, preview

        # 4. Definition
        m_def = re.match(r"^(Definition|परिभाषा|నిర్వచనం)\s*([0-9\.]+)?\b(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
        if m_def:
            lbl = m_def.group(1).capitalize()
            num = m_def.group(2)
            rest = m_def.group(3).strip()
            title = f"{lbl} {num}" if num else lbl
            preview = rest[:80] if rest else None
            return True, "definition", num, title, preview

        # 5. Configurable keywords
        for kw in self.activity_keywords:
            if re.match(rf"^\s*{re.escape(kw)}\b", line_clean, re.I):
                m_act = re.match(rf"^\s*({re.escape(kw)})(?:\s+([0-9]+(?:\.[0-9]+)*[a-zA-Z]?))?(?:\s*[:\.\-–—]\s*|\s*)(.*)$", line_clean, re.I)
                if m_act:
                    lbl = m_act.group(1).strip()
                    num = m_act.group(2)
                    rest = m_act.group(3).strip()
                    # Reject lowercase/caption words or lone generic words without numbers or colons
                    if lbl.lower() in ["observe", "source", "discuss", "explore", "example"] and not num and ":" not in line_clean:
                        continue
                    if len(line_clean.split()) > 12 and line_clean.endswith("."):
                        continue
                    if num:
                        title = f"{lbl} {num}"
                    elif rest and ":" in line_clean:
                        title = f"{lbl}: {rest[:80]}".strip()
                    else:
                        title = lbl
                    preview = rest[:80] if rest else None
                    return True, "activity", num, title, preview

        return False, None, None, None, None

    def is_noise_or_annotation(self, line: str) -> Tuple[bool, Optional[str]]:
        """
        Detects if line is page number, figure caption, reprint, single letters,
        math equations, measurement lines, table cells, or 'Do you know?' box.
        """
        line_s = line.strip()

        # Page numbers (e.g. 1 to 999)
        if re.match(r"^\d+$", line_s):
            return True, "page_number"

        # Reject lines < 3 chars
        if len(line_s) < 3:
            return True, "too_short"

        # Reject lines ending in comma
        if line_s.endswith(","):
            return True, "ends_in_comma"

        # Lone section numbers e.g. '1.1' or '2.4'
        if re.match(r"^\d+(\.\d+){1,3}$", line_s):
            return True, "lone_section_number"

        # Reprint / copyright
        if re.search(r"\b(Reprint\s+\d+|Rationalised|ISBN|Published by)\b", line_s, re.I):
            return True, "copyright"

        # Figure / Table caption or table cells
        if re.match(r"^(Fig\.|Figure|Table|Box|Chart|Graph)\s*\d+(\.\d+)?", line_s, re.I):
            return True, "figure_or_table_caption"
        # Question or answer labels in exercises
        if re.match(r"^(Ans\.|Ans\b|Answer\b|Q\.\d+|Question\s*\d+)", line_s, re.I):
            return True, "exercise_question_or_answer"
        if " | " in line_s or line_s.startswith("|") or "\t\t" in line:
            return True, "table_cell"

        if "\t" in line:
            if not re.match(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s*", line_s):
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                if len(parts) >= 2 and all(len(p) <= 15 for p in parts):
                    return True, "table_cell"

        # 'Do you know?' or 'Did you know?' box
        if re.search(r"\b(Do you know|Did you know|Fascinating Fact|Note for the teacher)\b", line_s, re.I):
            return True, "did_you_know_box"

        # Math expression, equation lines, or digits-only/units
        if re.match(r"^[\d\s\.\,\+\-\*\/\=\(\)\%\:\;\—\–\±\<\>\≤\≥\×\÷\^\_\{\}\[\]\|\~]+$", line_s):
            return True, "digits_or_operators_only"
        if re.match(r"^\d+(\.\d+)?\s*(g|kg|mol|m|cm|mm|L|mL|M|ns|pm|s|K|°C|\+|-|×|/|=)\b", line_s):
            return True, "math_or_measurement_line"
        if re.match(r"^(\d+\.?\d*|\w)\s*=\s*", line_s) or "× 10" in line_s or "+ (" in line_s:
            return True, "math_equation_line"
        if re.match(r"^(\d+\.?\d*)\s+(has|have|times|mol|molar)\b", line_s):
            return True, "math_statement_line"

        return False, None

    def parse_numbered_heading(self, line: str) -> Optional[Tuple[str, str, str]]:
        """
        Matches strictly formatted numbered section headings:
        e.g. '1.1 Title', '1.1.1 Title', '1.1.1.1 Title'.
        Rejects decimal numbers, math expressions, trailing periods, and exercise questions.
        """
        if self.end_of_chapter_reached:
            return None

        line_s = line.strip()
        m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+([A-Za-z\u0900-\u097F\u0C00-\u0C7F].+)$", line_s)
        if not m:
            return None

        num = m.group(1)
        title = m.group(2).strip()

        # Reject 0.x section numbers (chapters are 1+)
        if num.startswith("0."):
            return None

        # Enforce chapter prefix matching for numbered sections in chapter C
        if self.current_chapter_number and self.current_chapter_number.isdigit():
            ch_prefix = num.split(".")[0]
            if ch_prefix != self.current_chapter_number:
                return None

        # Extract heading phrase if followed by multiple spaces or run-in sentence
        if "  " in title:
            first_chunk = title.split("  ")[0].strip()
            if len(first_chunk.split()) <= 10 and not first_chunk.endswith((".", "?", ":")):
                title = first_chunk

        # Reject if title ends with punctuation (allow ? for inquiry questions <= 10 words)
        if title.endswith((".", ":", ";")) or (title.endswith("?") and len(title.split()) > 10) or len(title.split()) > 15:
            return None

        first_word = title.split()[0].lower()
        if first_word in [
            "g", "kg", "mol", "m", "cm", "mm", "l", "ml", "ns", "pm", "s", "k", "°c",
            "has", "in", "times", "is", "was", "are", "were",
            "calculate", "determine", "find", "show", "prove",
            "match", "express", "round", "convert", "if", "pressure", "use",
            "chlorine", "calcium", "dinitrogen"
        ]:
            return None

        dots = num.count(".")
        if dots == 1:
            level = "topic"
            try:
                parts = tuple(int(x) for x in num.split("."))
                # Allow minor backward step within 2 (handles 2-column layout reading order like 1.8 & 1.9)
                if self.last_topic_tuple is not None and (self.last_topic_tuple[1] - parts[1]) > 2:
                    return None  # Large backward jump (exercise question numbers)
                self.last_topic_tuple = max(self.last_topic_tuple, parts) if self.last_topic_tuple else parts
            except (ValueError, IndexError):
                pass
        elif dots == 2:
            level = "subtopic"
        else:
            level = "subheading"
        return level, num, title

    def detect_run_in_bold(self, line_text: str, spans: List[Dict[str, Any]]) -> Optional[str]:
        """
        Detects run-in bold headings where the first span is bold followed by body text:
        e.g. 'Intersection of sets. The intersection of...' -> returns 'Intersection of sets'
        Suppresses dialogue speakers (e.g. 'Nitin: ...') and inline bold vocabulary in running sentences (e.g. 'bottom of my jar.').
        """
        if not spans or len(spans) < 2:
            return None

        line_s = line_text.strip()

        # (a) Suppress dialogue speaker labels like "Nitin: What is this?"
        if re.match(r"^[A-Z][a-zA-Z\s]{0,20}\s*:\s*", line_s):
            return None

        sp0 = spans[0]
        t0 = sp0.get("text", "").strip()
        is_bold0 = bool(sp0.get("flags", 0) & 2 or "bold" in sp0.get("font", "").lower())

        if not is_bold0:
            return None

        # Check subsequent spans are non-bold body text
        sp_rest = spans[1:]
        non_bold_count = sum(1 for s in sp_rest if not (s.get("flags", 0) & 2 or "bold" in s.get("font", "").lower()))
        if non_bold_count < 1:
            return None

        # (b) Suppress inline bold vocabulary words inside running sentences:
        # A true run-in heading is set apart from the body text by punctuation (period, colon, or em-dash).
        # Sentences like "bottom of my jar." or "near the board and under the table." have NO heading punctuation
        # after the bold word and continue running grammatically.
        has_heading_punct = bool(re.search(r"[\.:–—]$", t0))
        rest_text = "".join(s.get("text", "") for s in sp_rest).strip()
        starts_with_delimiter = bool(re.match(r"^[\.:–—]", rest_text))

        if not (has_heading_punct or starts_with_delimiter):
            return None

        clean_t0 = t0.rstrip(".:-–— ").strip()

        # Subheadings must start with a capital letter or non-ASCII script
        if not clean_t0:
            return None
        if clean_t0[0].isascii() and not clean_t0[0].isupper():
            return None

        # Length check: between 3 chars and 8 words
        if len(clean_t0) < 3 or len(clean_t0.split()) > 8:
            return None

        # Reject figures, tables, notes, captions
        if re.match(r"^(Fig|Figure|Table|Note|Reprint|Exercise|\d+)\b", clean_t0, re.I):
            return None

        # If line ends with a question mark or dialogue quote, it's not a heading
        if line_s.endswith(("?", '"', '”', '’')):
            return None

        return clean_t0


    @staticmethod
    def check_plausibility(title: str, level: str = "") -> Optional[Tuple[str, str]]:
        """
        Validates title plausibility.
        Returns (rule_id, error_message) if invalid, or None if valid.
        """
        t = title.strip()
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
            return ("title_word_count_exceeded", f"Title '{t}' exceeds 12 words at level '{level}' ({len(t.split())} words)")

        # 6. Bare "UNIT" / "Unit N" token as heading
        if re.match(r"^UNIT(\s*[-–—]\s*\d+|\s+\d+)?$", t, re.I):
            return ("bare_unit_token", f"Title '{t}' is a bare UNIT token")

        return None

    def classify_line_style(self, line_text: str, spans: List[Dict[str, Any]]) -> Optional[str]:
        """Classify line as H1, H2, H3, or bold-body based on style profile."""
        if not spans:
            return None
        avg_size = sum(s.get("size", 10.0) for s in spans) / len(spans)
        has_bold = any(s.get("bold", False) for s in spans)

        # Determine heading size thresholds from profile ranks or relative to body_size
        h1_min = self.ranks.get("H1", {}).get("min_size") or (self.body_size + 6.0)
        h2_min = self.ranks.get("H2", {}).get("min_size") or (self.body_size + 3.0)
        h3_min = self.ranks.get("H3", {}).get("min_size") or (self.body_size + 1.0)

        # In books where covers or banners skew H1/H2 ranks above body_size * 2.2:
        if h1_min > self.body_size * 2.2 and h1_min > 24.0:
            h1_min = max(self.body_size + 6.0, 22.0)
        if h2_min > self.body_size * 2.0 and h2_min > 20.0:
            h2_min = max(self.body_size + 3.0, 18.0)
        if h3_min > self.body_size * 1.8 and h3_min > 16.0:
            h3_min = max(self.body_size + 1.0, 14.0)

        if avg_size >= h1_min and (has_bold or avg_size >= h1_min + 1.5):
            return "H1"
        elif avg_size >= h2_min and (has_bold or avg_size >= h2_min + 1.0):
            return "H2"
        elif avg_size >= h3_min and (has_bold or avg_size > self.body_size + 0.5):
            return "H3"
        elif has_bold and avg_size >= self.body_size - 0.5:
            return "bold-body"
        return None

    def _sort_lines_reading_order(self, lines_with_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort lines in human reading order.
        Handles both single-column and multi-column (2-column) page layouts,
        ensuring left-column flows completely before right-column, while
        preserving top/bottom full-width section bands.
        """
        valid_lines = [l for l in lines_with_spans if l.get("bbox") and len(l.get("text", "").strip()) >= 3]
        if not valid_lines:
            return lines_with_spans

        min_x0 = min(l["bbox"][0] for l in valid_lines)
        max_x1 = max(l["bbox"][2] for l in valid_lines)
        page_w = max_x1 - min_x0
        mid_x = min_x0 + page_w / 2.0

        left_lines = [l for l in valid_lines if l["bbox"][2] <= mid_x + 30 and l["bbox"][0] < mid_x - 30]
        right_lines = [l for l in valid_lines if l["bbox"][0] >= mid_x - 30 and l["bbox"][2] > mid_x + 30]

        if len(left_lines) < 3 or len(right_lines) < 3:
            # Single-column page: sort purely top-to-bottom, left-to-right
            return sorted(
                lines_with_spans,
                key=lambda l: (
                    round(l.get("bbox", [0, 0, 0, 0])[1] if l.get("bbox") else 0.0, 1),
                    round(l.get("bbox", [0, 0, 0, 0])[0] if l.get("bbox") else 0.0, 1),
                ),
            )

        # 2-column page: detect full-width elements that cut horizontally across the page
        full_width_y_cuts = []
        for l in valid_lines:
            b = l["bbox"]
            if b[0] < mid_x - 50 and b[2] > mid_x + 50 and (b[2] - b[0]) > 0.55 * page_w:
                full_width_y_cuts.append((b[1], b[3]))

        full_width_y_cuts.sort(key=lambda x: x[0])
        merged_cuts = []
        for cut in full_width_y_cuts:
            if not merged_cuts:
                merged_cuts.append(cut)
            else:
                prev = merged_cuts[-1]
                if cut[0] <= prev[1] + 10.0:
                    merged_cuts[-1] = (prev[0], max(prev[1], cut[1]))
                else:
                    merged_cuts.append(cut)

        def line_sort_key(l):
            b = l.get("bbox", [0, 0, 0, 0]) if l.get("bbox") else [0, 0, 0, 0]
            y0, y1, x0, x1 = b[1], b[3], b[0], b[2]

            band_idx = 0
            is_cut = False
            for i, (cut_top, cut_bot) in enumerate(merged_cuts):
                if y1 <= cut_top:
                    band_idx = 2 * i
                    break
                elif y0 <= cut_bot:
                    band_idx = 2 * i + 1
                    is_cut = True
                    break
            else:
                band_idx = 2 * len(merged_cuts)

            col = 0 if is_cut else (1 if x0 >= mid_x - 15 else 0)
            return (band_idx, col, round(y0, 1), round(x0, 1))

        return sorted(lines_with_spans, key=line_sort_key)

    def extract_nodes_from_lines(
        self,
        page_no: int,
        lines_with_spans: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extracts candidate headings (numbered, unnumbered, activity, run-in bold)
        from lines with their spans and vertical geometry.
        """
        candidates = []
        prev_y1 = None
        consumed_indices = set()

        # Sort lines strictly in reading order (single-column or 2-column aware)
        lines_with_spans = self._sort_lines_reading_order(lines_with_spans)
        page_line_counts = Counter(l.get("text", "").strip() for l in lines_with_spans if l.get("text"))

        for idx, line_info in enumerate(lines_with_spans):
            if idx in consumed_indices:
                continue

            line = line_info.get("text", "").strip()
            spans = line_info.get("spans", [])
            bbox = line_info.get("bbox", [0, 0, 0, 0])
            y0 = bbox[1] if bbox else 0.0

            w = (bbox[2] - bbox[0]) if bbox else 0.0
            h = (bbox[3] - bbox[1]) if bbox else 0.0
            if len(line) > 2 and h > 1.3 * w:
                prev_y1 = bbox[3] if bbox else prev_y1
                continue

            if len(line) < 3 or len(line) > 160:
                prev_y1 = bbox[3] if bbox else prev_y1
                continue

            is_noise, annot = self.is_noise_or_annotation(line)
            if is_noise:
                prev_y1 = bbox[3] if bbox else prev_y1
                continue

            spacing_above = round(y0 - prev_y1, 2) if prev_y1 is not None and y0 >= prev_y1 else 0.0
            prev_y1 = bbox[3] if bbox else prev_y1

            # Check for exercise/summary section boundaries (end of chapter)
            clean_lower = re.sub(r"[^\w]", "", line.strip().lower())
            is_end_section = (
                clean_lower in [
                    "summary", "exercises", "exercises.", "whatyouhavelearnt",
                    "whatyouhavelearned", "pointstoponder", "आपनेक्यासीखा",
                    "सारांश", "అభ్యాసం", "మనంఏంచర్చించాం", "solutions", "answers"
                ]
                or clean_lower.startswith("whatyouhavelearnt")
                or clean_lower.startswith("whatyouhavelearned")
                or clean_lower.startswith("pointstoponder")
                or re.search(r"^(chapter\s*\d+\s*[-–—]?\s*)?(solutions|answers)$", line.strip(), re.I)
                or (("solutions" in clean_lower or "answers" in clean_lower) and "chapter" in clean_lower and not re.search(r"\d+\.\d+", line))
            )
            if is_end_section:
                self.end_of_chapter_reached = True
                norm_lbl = line.strip().upper()
                if "SOLUTION" in norm_lbl:
                    norm_lbl = "SOLUTIONS"
                elif "ANSWER" in norm_lbl:
                    norm_lbl = "ANSWERS"
                elif "SUMMARY" in re.sub(r"[^\w]", "", norm_lbl):
                    norm_lbl = "SUMMARY"
                elif "EXERCISE" in re.sub(r"[^\w]", "", norm_lbl):
                    norm_lbl = "EXERCISES"
                self.end_matter_label = norm_lbl
                if self.end_matter_page is None or page_no < self.end_matter_page:
                    self.end_matter_page = page_no
                continue


            # 1. Activity detection (Example, Exercise, Theorem, Activity)
            is_act, act_kind, act_num, act_title, act_preview = self.is_activity_heading(line)
            if is_act:
                first_span = spans[0] if spans else {}
                span_size = first_span.get("size", 10.0)
                span_font = first_span.get("font", "").lower()
                span_bold = bool(first_span.get("flags", 0) & 2 or "bold" in span_font or "demi" in span_font or "heavy" in span_font or "black" in span_font)
                # Reject caption or small font words (must be >= body size or bold)
                if span_size < self.body_size - 0.5 and not span_bold:
                    continue

                # Chapter-level exercise without section number (e.g. "EXERCISES") marks end of chapter
                if act_kind == "exercise" and (not act_num or "." not in str(act_num)):
                    self.end_of_chapter_reached = True
                    self.end_matter_label = line.strip().upper()
                    if self.end_matter_page is None or page_no < self.end_matter_page:
                        self.end_matter_page = page_no
                candidates.append({
                    "level": "activity",
                    "kind": act_kind,
                    "official_number": act_num,
                    "official_title": act_title,
                    "preview": act_preview,
                    "normalized_title": re.sub(r"\s+", " ", act_title).strip(),
                    "page": page_no,
                    "evidence": line[:80],
                    "confidence": 0.95,
                    "detection_method": "lexicon",
                    "rule_id": f"rule_activity_{act_kind}",
                    "font_size": span_size,
                    "bold": span_bold,
                })
                continue

            # 2. Numbered heading detection (1.1, 1.1.1, 1.1.1.1)
            # Reconstruct full line if adjacent fragments share the exact baseline (NCERT drop shadow / kerning splits)
            full_line_text = line
            last_x1 = bbox[2] if bbox else 0.0
            k = idx + 1
            while k < len(lines_with_spans):
                next_l = lines_with_spans[k]
                next_bbox = next_l.get("bbox", [0, 0, 0, 0])
                if abs(next_bbox[1] - bbox[1]) <= 2.0:
                    next_txt = next_l.get("text", "").strip()
                    if next_txt:
                        s1, s2 = full_line_text.strip(), next_txt.strip()
                        merged = None
                        for m_len in range(min(len(s1), len(s2)), 0, -1):
                            if s1[-m_len:] == s2[:m_len]:
                                merged = s1 + s2[m_len:]
                                break
                        if merged:
                            full_line_text = merged
                            last_x1 = max(last_x1, next_bbox[2])
                            k += 1
                        elif 0 <= next_bbox[0] - last_x1 <= 20.0:
                            if next_bbox[0] - last_x1 <= 2.5:
                                full_line_text = s1 + s2
                            else:
                                full_line_text = s1 + " " + s2
                            last_x1 = max(last_x1, next_bbox[2])
                            k += 1
                        else:
                            break
                else:
                    break

            # Clean duplicate section numbers produced by vector drop-shadow layers e.g. "1.3 1.3" -> "1.3"
            while re.search(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\s+\1\b", full_line_text):
                full_line_text = re.sub(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\s+\1\b", r"\1", full_line_text)

            num_match = self.parse_numbered_heading(full_line_text)
            if num_match:
                for c_idx in range(idx + 1, k):
                    consumed_indices.add(c_idx)
                level, num, title = num_match
                first_span = spans[0] if spans else {}
                h_size = first_span.get("size", 10.0)
                h_font = first_span.get("font", "").lower()
                h_bold = bool(first_span.get("flags", 0) & 2 or "bold" in h_font or "demi" in h_font)

                # Check for vertically adjacent continuation lines of the heading
                sub_k = k
                last_y1 = bbox[3] if bbox else 0.0
                while sub_k < len(lines_with_spans):
                    nxt = lines_with_spans[sub_k]
                    nxt_txt = nxt.get("text", "").strip()
                    nxt_spans = nxt.get("spans", [])
                    nxt_bbox = nxt.get("bbox", [0, 0, 0, 0])
                    if not nxt_txt or not nxt_spans:
                        break
                    y_diff = nxt_bbox[1] - last_y1
                    if y_diff < -4.0 or y_diff > 22.0:
                        break
                    nxt_s0 = nxt_spans[0]
                    nxt_size = nxt_s0.get("size", 10.0)
                    if h_bold:
                        nxt_bold = all(
                            bool(s.get("flags", 0) & 2 or "bold" in s.get("font", "").lower() or "demi" in s.get("font", "").lower())
                            for s in nxt_spans
                        )
                    else:
                        nxt_font = nxt_s0.get("font", "").lower()
                        nxt_bold = bool(nxt_s0.get("flags", 0) & 2 or "bold" in nxt_font or "demi" in nxt_font)
                    size_matches = abs(nxt_size - h_size) <= 0.6
                    bold_matches = (nxt_bold == h_bold)
                    is_heading_weight = h_bold or (h_size > self.body_size + 0.5)
                    if size_matches and bold_matches and is_heading_weight:
                        if self.parse_numbered_heading(nxt_txt) or self.is_activity_heading(nxt_txt)[0]:
                            break
                        if nxt_txt.endswith((".", ":", ";")):
                            title = f"{title} {nxt_txt.rstrip('.:;')}".strip()
                            full_line_text = f"{full_line_text} {nxt_txt}"
                            consumed_indices.add(sub_k)
                            last_y1 = nxt_bbox[3]
                            break
                        title = f"{title} {nxt_txt}".strip()
                        full_line_text = f"{full_line_text} {nxt_txt}"
                        consumed_indices.add(sub_k)
                        last_y1 = nxt_bbox[3]
                        sub_k += 1
                    else:
                        break

                candidates.append({
                    "level": level,
                    "official_number": num,
                    "official_title": title,
                    "normalized_title": re.sub(r"\s+", " ", title).strip(),
                    "page": page_no,
                    "evidence": full_line_text,
                    "confidence": 0.98,
                    "detection_method": "numbered",
                    "rule_id": "rule_numbered_heading",
                    "font_size": first_span.get("size"),
                    "bold": bool(first_span.get("flags", 0) & 2 or "bold" in first_span.get("font", "").lower()),
                })
                continue


            # 3. Run-in bold heading detection (e.g. "Intersection of sets. The ...")
            run_in_title = self.detect_run_in_bold(line, spans)
            if run_in_title and len(run_in_title.split()) <= 8:
                if self.check_plausibility(run_in_title, "subheading") is not None:
                    continue
                first_span = spans[0] if spans else {}
                candidates.append({
                    "level": "subheading",
                    "official_number": None,
                    "official_title": run_in_title,
                    "normalized_title": re.sub(r"\s+", " ", run_in_title).strip(),
                    "page": page_no,
                    "evidence": line[:60],
                    "confidence": 0.85,
                    "detection_method": "run_in",
                    "rule_id": "rule_run_in_bold",
                    "font_size": first_span.get("size"),
                    "bold": True,
                })
                continue

            # 4. Unnumbered standalone heading detection by style rank strictly above body
            # Must be standalone (<= 12 words, no terminal period, style rank H1, H2, or H3)
            words = line.split()
            if len(words) <= 12 and not line.endswith((".", "?", "!", ":", ";", ",", '"', "”")):
                if page_line_counts.get(line, 1) > 1:
                    continue
                if re.match(r"^[A-Z][a-zA-Z\s]{0,20}\s*:", line):
                    continue
                # Skip lone alphabet tracing/phonics pairs e.g. "E e", "A a", "B b"
                if re.match(r"^[A-Z]\s+[a-z]$", line.strip()):
                    continue
                style_rank = self.classify_line_style(line, spans)

                if style_rank in ["H1", "H2", "H3"]:
                    lvl = "topic" if style_rank == "H1" else ("subtopic" if style_rank == "H2" else "subheading")
                    if self.check_plausibility(line, lvl) is not None:
                        continue
                    first_span = spans[0] if spans else {}
                    candidates.append({
                        "level": lvl,
                        "official_number": None,
                        "official_title": line,
                        "normalized_title": re.sub(r"\s+", " ", line).strip(),
                        "page": page_no,
                        "evidence": line,
                        "confidence": 0.82,
                        "detection_method": "style",
                        "rule_id": f"rule_style_{style_rank.lower()}",
                        "font_size": first_span.get("size"),
                        "bold": any(bool(s.get("flags", 0) & 2 or "bold" in s.get("font", "").lower()) for s in spans),
                    })

        # Deduplicate consecutive/subpixel candidates (drop shadows / faux-bold / stroke outlines)
        deduped = []
        for c in candidates:
            if not deduped:
                deduped.append(c)
                continue
            prev = deduped[-1]
            same_page = c.get("page") == prev.get("page")
            same_num = c.get("official_number") and c.get("official_number") == prev.get("official_number")
            same_title = c.get("normalized_title") == prev.get("normalized_title")
            num_match = same_num and (
                c.get("official_title", "") in prev.get("official_title", "")
                or prev.get("official_title", "") in c.get("official_title", "")
            )

            if same_page and (same_title or same_num or num_match):
                # Keep the candidate with longer/more complete title
                if len(c.get("official_title", "")) > len(prev.get("official_title", "")):
                    deduped[-1] = c
            else:
                deduped.append(c)

        return deduped

