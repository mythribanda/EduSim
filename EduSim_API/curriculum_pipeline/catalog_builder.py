"""
EduSim Curriculum Pipeline — Catalog Builder
Loads empirical NCERT and SSC book mappings from mapping.yaml,
validates that all files are mapped (logging to unmapped_files.csv if not),
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
    MAPPING_YAML_PATH,
    NCERT_CLASS_MAP,
    NCERT_LANG_MAP,
    PIPELINE_OUTPUT_ROOT,
    TEXTBOOKS_DIR,
    get_ncert_book_code,
    get_ssc_book_code,
    is_ncert_filename,
    parse_ncert_filename,
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
        board = r.get("board", "").lower()
        source_type = r.get("source_type", "").lower()

        # Check if NCERT
        if board == "ncert" or "ncert" in source_type or is_ncert_filename(fn):
            parsed = parse_ncert_filename(fn)
            if not parsed:
                # Check stem
                stem = Path(fn).stem.lower()
                if len(stem) == 4 and stem[0] in ncert_classes and stem[1] in ncert_langs:
                    bcode = stem
                    code = stem[2:4]
                else:
                    unmapped_files.append({
                        "file": fn,
                        "board": "ncert",
                        "reason": f"Unparseable NCERT filename '{fn}'",
                    })
                    continue
            else:
                bcode = get_ncert_book_code(fn)
                code = parsed["subject_code"]

            if code not in ncert_subjects:
                unmapped_files.append({
                    "file": fn,
                    "board": "ncert",
                    "reason": f"Unknown NCERT subject code '{code}'",
                })
            else:
                ncert_groups[bcode].append(r)
        else:
            # SSC
            if fn not in ssc_books:
                unmapped_files.append({
                    "file": fn,
                    "board": "ssc",
                    "reason": "Filename not mapped in mapping.yaml ssc.books",
                })
            else:
                ssc_files.append(r)

    # If unmapped files exist, record and report
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

    # If all mapped, remove stale unmapped report if present
    if UNMAPPED_REPORT_PATH.exists():
        UNMAPPED_REPORT_PATH.unlink()

    catalog_rows: List[Dict[str, Any]] = []

    # 1. Process NCERT books
    for bcode, flist in sorted(ncert_groups.items()):
        c_letter = bcode[0]
        lang_letter = bcode[1]
        code = bcode[2:4]
        part_str = bcode[4:] if len(bcode) > 4 else ""

        cls = ncert_classes.get(c_letter, 0)
        medium = ncert_langs.get(lang_letter, "en")

        subj_info = ncert_subjects.get(code, {})
        subj = subj_info.get("subject", "unknown")
        title_base = subj_info.get("title", "Textbook")
        
        # Use verified mapping.yaml metadata as the primary title source
        if part_str:
            final_title = f"{title_base} Part {part_str}"
        else:
            final_title = title_base

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
