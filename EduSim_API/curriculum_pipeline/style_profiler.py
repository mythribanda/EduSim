"""
EduSim Curriculum Pipeline — Style Profiler
Analyzes spans across a book (or book code files), clusters font size + bold
into ranks (title, H1, H2, H3, body), and saves output/style_profiles/<book>.json.
Never hardcodes font sizes globally.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT

STYLE_PROFILES_DIR = PIPELINE_OUTPUT_ROOT / "style_profiles"


class StyleProfiler:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or STYLE_PROFILES_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_profile_path(self, book_code: str) -> Path:
        return self.output_dir / f"{book_code}.json"

    def profile_book(
        self,
        book_code: str,
        jsonl_files: List[Path],
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Build style profile from page jsonl files.
        Collects font size distributions, bold status, and clusters into semantic ranks.
        """
        out_path = self.get_profile_path(book_code)
        if not force and out_path.exists():
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        font_stats: Counter = Counter()      # (size, is_bold) -> char_count
        size_samples: Dict[Tuple[float, bool], List[str]] = defaultdict(list)

        for j_path in jsonl_files:
            if not j_path.exists():
                continue
            with open(j_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("type") == "metadata":
                        continue
                    for sp in record.get("spans", []):
                        txt = sp.get("text", "").strip()
                        if not txt:
                            continue
                        size = round(float(sp.get("size", 10.0)), 1)
                        bold = bool(sp.get("bold", False))
                        char_len = len(txt)
                        font_stats[(size, bold)] += char_len
                        if len(size_samples[(size, bold)]) < 5:
                            size_samples[(size, bold)].append(txt[:40])

        if not font_stats:
            # Fallback default profile if no text spans
            profile = {
                "book_code": book_code,
                "body_size": 10.0,
                "ranks": {
                    "title": {"min_size": 18.0, "bold": True},
                    "H1": {"min_size": 14.0, "bold": True},
                    "H2": {"min_size": 12.0, "bold": True},
                    "H3": {"min_size": 11.0, "bold": False},
                    "body": {"min_size": 9.0, "bold": False},
                },
                "total_spans_analyzed": 0,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            return profile

        # Body font size is the font size with the overwhelming majority of characters
        body_style, body_chars = font_stats.most_common(1)[0]
        body_size, _ = body_style

        # Look at larger font sizes (potential headings)
        heading_candidates = [
            (style, count) for style, count in font_stats.items()
            if style[0] > body_size or (style[0] == body_size and style[1])
        ]
        heading_candidates.sort(key=lambda x: (x[0][0], x[0][1]), reverse=True)

        # Cluster distinct sizes into Title, H1, H2, H3
        distinct_sizes = sorted(list({c[0][0] for c in heading_candidates}), reverse=True)

        title_size = distinct_sizes[0] if distinct_sizes else body_size + 4.0
        h1_size = distinct_sizes[1] if len(distinct_sizes) > 1 else max(title_size - 2.0, body_size + 2.0)
        h2_size = distinct_sizes[2] if len(distinct_sizes) > 2 else max(h1_size - 1.5, body_size + 1.0)
        h3_size = distinct_sizes[3] if len(distinct_sizes) > 3 else max(h2_size - 1.0, body_size + 0.5)

        profile = {
            "book_code": book_code,
            "body_size": body_size,
            "total_spans_chars": sum(font_stats.values()),
            "ranks": {
                "title": {"min_size": title_size, "bold": True},
                "H1": {"min_size": h1_size, "bold": True},
                "H2": {"min_size": h2_size, "bold": True},
                "H3": {"min_size": h3_size, "bold": False},
                "body": {"min_size": body_size, "bold": False},
            },
            "sample_texts_per_style": {
                f"size_{s}_bold_{b}": samples[:3]
                for (s, b), samples in list(size_samples.items())[:10]
            },
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        return profile
