# EduSim Curriculum Pipeline

> **Read-only contract**: this pipeline **never modifies, moves, renames or
> deletes** anything inside `EduSim_API/textbooks/`. All generated files land
> exclusively in `EduSim_API/curriculum_pipeline/output/`.

---

## Folder Layout

```
EduSim_API/
├── textbooks/                  ← READ-ONLY source; never written to
│   ├── ncert books/            │   NCERT chapter PDFs (e.g. leph101.pdf)
│   └── Text Books/             │   State-board whole-book PDFs
│
└── curriculum_pipeline/        ← Pipeline source code (committed to git)
    ├── pipeline_config.py      │   Central config: paths, patterns, constants
    ├── scan_textbooks.py       │   Main scanner (CLI entry-point)
    ├── __init__.py             │
    ├── README.md               │   (this file)
    └── output/                 ← Generated artefacts (git-ignored)
        ├── inventory/
        │   ├── textbooks_inventory.csv
        │   └── ignored_non_pdf.log
        ├── reports/
        │   └── scan_report.json
        ├── extracted_text/     │   (future: per-chapter text dumps)
        └── curriculum_json/    │   (future: structured curriculum JSON)
```

---

## Configuration

The textbooks path is configurable in three ways (precedence order):

| Priority | Method | Example |
|----------|--------|---------|
| 1 (highest) | CLI `--input` | `python -m curriculum_pipeline.scan_textbooks --input /data/books` |
| 2 | Env var `TEXTBOOKS_DIR` | `TEXTBOOKS_DIR=/data/books python -m curriculum_pipeline.scan_textbooks` |
| 3 (default) | Compiled default | `EduSim_API/textbooks` (relative to repo root) |

---

## Quick Start

```bash
# From the EduSim_API/ directory, with the venv active:

# Activate venv (Windows)
venv\Scripts\activate

# Dry-run — classify every PDF, print summary, write nothing
python -m curriculum_pipeline.scan_textbooks --dry-run

# Full scan — write inventory CSV + ignored log + JSON report
python -m curriculum_pipeline.scan_textbooks

# Custom source
python -m curriculum_pipeline.scan_textbooks --input "C:\path\to\books"

# Custom output directory
python -m curriculum_pipeline.scan_textbooks --out-dir "C:\path\to\out"
```

---

## Outputs

### `output/inventory/textbooks_inventory.csv`

One row per PDF. Key columns:

| Column | Description |
|--------|-------------|
| `file` | Filename |
| `rel_path` | Path relative to textbooks root |
| `source_type` | `ncert_chapter` or `state_board_book` |
| `board` | `ncert` or `ssc` |
| `class` | Grade number |
| `subject` | Resolved subject (e.g. `physics`, `mathematics`) |
| `language` | `en`, `hi`, `ur` |
| `part` | NCERT part number |
| `chapter_no` | Chapter within part |
| `book_chapter_no` | Continuous chapter across parts |
| `pages` | Page count |
| `sha256` | File hash (duplicate detection) |
| `duplicate_of` | Set if file is a duplicate |
| `needs_ocr` | `True` if text extraction was poor |
| `scan_note` | `ok` or reason for exclusion/review |

### `output/inventory/ignored_non_pdf.log`

Tab-separated list of every non-PDF file found in the textbooks tree.
Format: `<extension>\t<relative_path>`

### `output/reports/scan_report.json`

Machine-readable summary with counts by board, subject, and class.

---

## Classification Rules

### NCERT Chapter Files
Filename matches: `^([a-l])([ehu])([a-z]{2})(\d)(\d{2})\.+pdf$`

- Character 1: class (a=1 … l=12)
- Character 2: language (e=English, h=Hindi, u=Urdu)
- Characters 3–4: subject code (ph=Physics, mh=Mathematics, etc.)
- Character 5: part number
- Characters 6–7: chapter number within part

### State-Board Whole Books
Everything else that is a `.pdf`. Classification uses:
1. Filename subject keywords (Physics, Maths, Biology, etc.)
2. Cover page text (first 3 pages) — overrides filename

---

## RAG Ingestion Safety

The existing RAG system (`legacy_rag/vector_store.py`) reads from `TEXTBOOKS_DIR`
(env var default: `EduSim_API/textbooks`). The `loader.py` uses `os.listdir()` —
**flat scan, not recursive** — so `ncert books/` and `Text Books/` subfolders are
already **not** ingested by the current RAG loader.

Pipeline output (`curriculum_pipeline/output/`) is in a completely separate tree
and is also git-ignored, so it will never accidentally be treated as a textbook.

> **If you change `TEXTBOOKS_DIR`** to point at a different folder, make sure
> it does not overlap with `curriculum_pipeline/output/`.

---

## Git Status

- `EduSim_API/textbooks/` → git-ignored (PDFs never committed)
- `EduSim_API/curriculum_pipeline/output/` → git-ignored (generated files)
- `EduSim_API/curriculum_pipeline/*.py` → **committed** (pipeline source)

No PDFs were found to be tracked by git (`git ls-files EduSim_API/textbooks/`
returned empty). The folder itself is not tracked.
