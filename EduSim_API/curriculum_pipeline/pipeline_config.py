"""
EduSim Curriculum Pipeline — Central Configuration
====================================================
All paths, output locations, and toggles live here so nothing else needs
to be edited when the layout changes.

Override TEXTBOOKS_DIR at runtime with:
  - env var  TEXTBOOKS_DIR
  - CLI flag --input <path>   (honoured by scan_textbooks.py)
"""

import os
from pathlib import Path

# ── Repo root (two levels up from this file: curriculum_pipeline/ → EduSim_API/)
REPO_ROOT: Path = Path(__file__).resolve().parents[2]
API_ROOT: Path  = Path(__file__).resolve().parents[1]   # EduSim_API/

# ── Source textbooks folder (read-only, NEVER written to)
_env_tb = os.getenv("TEXTBOOKS_DIR", "")
TEXTBOOKS_DIR: Path = (
    Path(_env_tb).resolve() if _env_tb
    else (API_ROOT / "textbooks")
)

# ── Pipeline output root  (MUST be outside TEXTBOOKS_DIR)
PIPELINE_OUTPUT_ROOT: Path = API_ROOT / "curriculum_pipeline" / "output"

# Sub-folders
INVENTORY_DIR:       Path = PIPELINE_OUTPUT_ROOT / "inventory"
EXTRACTED_TEXT_DIR:  Path = PIPELINE_OUTPUT_ROOT / "extracted_text"
CURRICULUM_JSON_DIR: Path = PIPELINE_OUTPUT_ROOT / "curriculum_json"
REPORTS_DIR:         Path = PIPELINE_OUTPUT_ROOT / "reports"

# ── File names
INVENTORY_CSV:    str = "textbooks_inventory.csv"
IGNORED_LOG:      str = "ignored_non_pdf.log"
SCAN_REPORT:      str = "scan_report.json"

# ── Load mapping.yaml if present
MAPPING_YAML_PATH: Path = Path(__file__).resolve().parent / "mapping.yaml"

import re
import yaml

_ncert_pat_str = r"^([a-l])([ehu])([a-z]{2})(\d)(\d{2})\.+pdf$"
_class_map = {ch: idx + 1 for idx, ch in enumerate("abcdefghijkl")}
_lang_map = {"e": "en", "h": "hi", "u": "ur"}

if MAPPING_YAML_PATH.exists():
    try:
        with open(MAPPING_YAML_PATH, "r", encoding="utf-8") as _mf:
            _mdata = yaml.safe_load(_mf) or {}
            _ncert_cfg = _mdata.get("ncert", {})
            if "pattern" in _ncert_cfg:
                _ncert_pat_str = _ncert_cfg["pattern"]
            if "classes" in _ncert_cfg:
                _class_map = {str(k): int(v) for k, v in _ncert_cfg["classes"].items()}
            if "languages" in _ncert_cfg:
                _lang_map = {str(k): str(v) for k, v in _ncert_cfg["languages"].items()}
    except Exception:
        pass

# ── NCERT filename regex
NCERT_PATTERN: re.Pattern = re.compile(_ncert_pat_str, re.IGNORECASE)

# ── NCERT class code (a=1 … l=12)
NCERT_CLASS_MAP: dict[str, int] = _class_map

# ── NCERT language code
NCERT_LANG_MAP: dict[str, str] = _lang_map

# ── Ensure all output directories exist on import
for _d in (INVENTORY_DIR, EXTRACTED_TEXT_DIR, CURRICULUM_JSON_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

