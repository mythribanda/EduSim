"""
EduSim Curriculum Pipeline — Catalog Builder
Loads empirical NCERT and SSC book mappings from mapping.yaml,
validates that all files are mapped (failing loudly and logging to unmapped_files.csv if not),
and generates books_catalog.csv.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
import yaml

from curriculum_pipeline.pipeline_config import (
    API_ROOT,
    MAPPING_YAML_PATH,
    NCERT_CLASS_MAP,
    NCERT_LANG_MAP,
    NCERT_PATTERN,
    PIPELINE_OUTPUT_ROOT,
    TEXTBOOKS_DIR,
    get_ssc_book_code,
)

CATALOG_CSV_PATH = PIPELINE_OUTPUT_ROOT / "catalog" / "books_catalog.csv"
UNMAPPED_REPORT_PATH = PIPELINE_OUTPUT_ROOT / "reports" / "unmapped_files.csv"


def load_mapping_config(yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads mapping configuration from mapping.yaml."""
    path = yaml_path or MAPPING_YAML_PATH
    if not path.exists():
        raise FileNotFoundError(f"Mapping configuration file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_MAPPING = load_mapping_config()
_NCERT_SUBJECTS_CFG = _MAPPING.get("ncert", {}).get("subjects", {})
_SSC_BOOKS_CFG = _MAPPING.get("ssc", {}).get("books", {})

# Backwards compatible NCERT_KNOWN_SUBJECTS dict
NCERT_KNOWN_SUBJECTS: Dict[str, Tuple[str, str]] = {
    code: (data.get("subject", "general"), data.get("title", "Textbook"))
    for code, data in _NCERT_SUBJECTS_CFG.items()
}


def extract_title_from_doc(doc: fitz.Document) -> str:
    """Extract candidate book/chapter title from the first 2 pages."""
    if len(doc) == 0:
        return ""
    lines: List[str] = []
    for pno in range(min(2, len(doc))):
        page_text = doc[pno].get_text()
        for line in page_text.splitlines():
            line = line.strip()
            if len(line) > 3 and not re.match(r"^(Reprint|Chapter|Unit|CHAPTER|UNIT|\d+|Class)\b", line, re.I):
                lines.append(line)
    return lines[0] if lines else ""


def build_books_catalog(
    inventory_csv_path: Optional[Path] = None,
    textbooks_dir: Optional[Path] = None,
    output_catalog_path: Optional[Path] = None,
    mapping_yaml_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    inv_path = inventory_csv_path or (PIPELINE_OUTPUT_ROOT / "inventory" / "textbooks_inventory.csv")
    tb_dir = textbooks_dir or TEXTBOOKS_DIR
    out_path = output_catalog_path or CATALOG_CSV_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    UNMAPPED_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not inv_path.exists():
        raise FileNotFoundError(f"Inventory CSV not found at {inv_path}")

    mapping_cfg = load_mapping_config(mapping_yaml_path)
    ncert_subjects = mapping_cfg.get("ncert", {}).get("subjects", {})
    ncert_classes = mapping_cfg.get("ncert", {}).get("classes", NCERT_CLASS_MAP)
    ncert_langs = mapping_cfg.get("ncert", {}).get("languages", NCERT_LANG_MAP)
    ssc_books = mapping_cfg.get("ssc", {}).get("books", {})

    with open(inv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    ncert_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ssc_files: List[Dict[str, Any]] = []
    unmapped_files: List[Dict[str, str]] = []

    for r in rows:
        fn = r["file"]
        m = NCERT_PATTERN.match(fn)
        if m:
            c, lang, code, part, ch = m.groups()
            bcode = f"{c.lower()}{lang.lower()}{code.lower()}{part}"
            if code.lower() not in ncert_subjects:
                unmapped_files.append({
                    "file": fn,
                    "board": "ncert",
                    "reason": f"Unknown NCERT subject code '{code.lower()}'"
                })
            else:
                ncert_groups[bcode].append(r)
        else:
            if fn not in ssc_books:
                unmapped_files.append({
                    "file": fn,
                    "board": "ssc",
                    "reason": "Filename not mapped in mapping.yaml ssc.books"
                })
            else:
                ssc_files.append(r)

    # If unmapped files exist, record and fail loudly!
    if unmapped_files:
        with open(UNMAPPED_REPORT_PATH, "w", encoding="utf-8-sig", newline="") as uf:
            writer = csv.DictWriter(uf, fieldnames=["file", "board", "reason"])
            writer.writeheader()
            for u in unmapped_files:
                writer.writerow(u)
        raise ValueError(
            f"Found {len(unmapped_files)} unmapped file(s). Written to {UNMAPPED_REPORT_PATH}. "
            f"Add them to {MAPPING_YAML_PATH}."
        )

    # If all mapped, write empty unmapped report if needed
    if UNMAPPED_REPORT_PATH.exists():
        UNMAPPED_REPORT_PATH.unlink()

    catalog_rows: List[Dict[str, Any]] = []

    # 1. Process NCERT books
    for bcode, flist in sorted(ncert_groups.items()):
        c_letter = bcode[0]
        lang_letter = bcode[1]
        code = bcode[2:4]
        part = int(bcode[4:])

        cls = ncert_classes.get(c_letter, 0)
        medium = ncert_langs.get(lang_letter, "en")

        subj_info = ncert_subjects.get(code, {})
        subj = subj_info.get("subject", "unknown")
        base_title = f"{subj_info.get('title', 'Textbook')} Class {cls} Part {part}"

        # Sample the first file to confirm / refine title
        sample_file = tb_dir / "ncert books" / flist[0]["file"]
        first_title = ""
        if sample_file.exists():
            try:
                doc = fitz.open(sample_file)
                first_title = extract_title_from_doc(doc)
            except Exception:
                pass

        final_title = f"{base_title} ({first_title})" if first_title else base_title

        catalog_rows.append({
            "book_code": bcode,
            "board": "ncert",
            "class": cls,
            "medium": medium,
            "subject": subj,
            "book_title": final_title,
            "source_files_count": len(flist),
            "status": "proposed",
        })

    # 2. Process SSC books
    for r in ssc_files:
        fn = r["file"]
        book_meta = ssc_books[fn]
        cls = book_meta["class"]
        subj = book_meta["subject"]
        medium = book_meta.get("medium", "en")
        title = book_meta.get("title", Path(fn).stem)

        bcode = get_ssc_book_code(fn)

        catalog_rows.append({
            "book_code": bcode,
            "board": "ssc",
            "class": cls,
            "medium": medium,
            "subject": subj,
            "book_title": title,
            "source_files_count": 1,
            "status": "proposed",
        })

    # Write books_catalog.csv
    cols = ["book_code", "board", "class", "medium", "subject", "book_title", "source_files_count", "status"]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for row in catalog_rows:
            writer.writerow(row)

    return catalog_rows
