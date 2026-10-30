"""
EduSim Curriculum Pipeline — Chunker
===================================
Transforms extracted curriculum JSON and raw page text into RAG-ready chunks
with rich metadata.

Hierarchy: Class > Subject > Book > Chapter > Topic > Subtopic > Activity > Subheading.
Missing hierarchy levels are legitimately absent and are never invented.

Chunks target 150-400 tokens, never split mid-sentence, merge small adjacent
sections, and split long ones on paragraph/sentence boundaries with ~10% overlap.

Every chunk carries metadata:
  - board (NCERT/SSC)
  - class (int)
  - subject (str)
  - book_code (str)
  - book_title (str)
  - chapter_number (str)
  - chapter_title (str)
  - topic_subtopic_path (nullable str)
  - node_id (matching curriculum_nodes where loaded)
  - page_start (int)
  - page_end (int)
  - source_pdf (str)
  - chunk_id (str)
  - text (str)
  - token_count (int)

Output: curriculum_pipeline/output/chunks/{book_code}.jsonl
Idempotent: skips books whose chunk JSONL is newer than the book JSON.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


from curriculum_pipeline.pipeline_config import (
    API_ROOT,
    PIPELINE_OUTPUT_ROOT,
)

logger = logging.getLogger("EduSim.chunker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CHUNKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "chunks"
BOOKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "curriculum" / "books"
PAGES_DIR: Path = PIPELINE_OUTPUT_ROOT / "pages"
INVENTORY_CSV: Path = PIPELINE_OUTPUT_ROOT / "inventory" / "textbooks_inventory.csv"
DB_PATH: Path = API_ROOT / "edusim.db"

# Abbreviations to protect during sentence splitting
ABBREVIATIONS = [
    r"e\.g\.", r"i\.e\.", r"etc\.", r"vs\.", r"Fig\.", r"figs\.", r"Dr\.", r"Mr\.", r"Mrs\.",
    r"Prof\.", r"approx\.", r"viz\.", r"vol\.", r"no\.", r"nos\.", r"p\.", r"pp\.", r"ch\.",
    r"sec\.", r"al\.", r"Eq\.", r"eq\.", r"Ref\.", r"Govt\."
]

# Explicit Skip Regexes
FRONT_MATTER_TOP_REGEX = re.compile(
    r"^\s*(\d+\s+)?(FOREWORD|PREFACE|A\s+NOTE\s+FOR\s+THE\s+TEACHER|PREAMBLE|THE\s+CONSTITUTION\s+OF\s+INDIA|"
    r"FUNDAMENTAL\s+DUTIES|NATIONAL\s+ANTHEM|PLEDGE|CONTENTS|TABLE\s+OF\s+CONTENTS|DIKSHA|QR\s+CODE|"
    r"ABOUT\s+THE\s+TEXTBOOK)\b",
    re.I
)

COPYRIGHT_REGEX = re.compile(
    r"(\bISBN\s+[\d\-X]+|\bALL\s+RIGHTS\s+RESERVED|\bFirst\s+Edition|\bReprint\s+Edition|"
    r"\bPublished\s+by\s*:?|\bChief\s+Advisor\b|\bTextbook\s+Development\s+Team|\bPublication\s+Team|"
    r"\bPrinted\s+in\s+India|\bAdvisors\b|\bMy\s+name\s+is\s*\.{3,})",
    re.I
)

BACK_MATTER_TOP_REGEX = re.compile(
    r"^\s*(\d+\s+)?(Answers\s+to\s+Selected\s+Questions|Answers/Hints|Answers\s+to\s+Exercises|"
    r"Logarithmic\s+Tables|Table\s+of\s+Logarithms|Trigonometric\s+Tables|Bibliography|"
    r"List\s+of\s+Reference\s+Books|Index\s+of\s+Terms)\b",
    re.I
)


import hashlib

def compute_content_hash(
    text: str,
    board: str,
    class_num: Any,
    subject: str,
    book_code: str,
    chapter_number: str,
    page_start: int,
    page_end: int,
) -> str:
    """Computes a SHA256 content hash of normalized text and key metadata."""
    norm_text = re.sub(r"\s+", " ", text or "").strip()
    norm_board = str(board or "").strip().upper()
    norm_class = str(class_num if class_num is not None else "").strip()
    norm_subj = str(subject or "").strip().lower()
    norm_bcode = str(book_code or "").strip().lower()
    norm_chnum = str(chapter_number or "").strip()
    norm_pstart = str(page_start)
    norm_pend = str(page_end)
    payload = f"{norm_text}|{norm_board}|{norm_class}|{norm_subj}|{norm_bcode}|{norm_chnum}|{norm_pstart}|{norm_pend}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Estimates tokens safely across English, Devanagari, and Telugu text."""
    words = text.split()
    if not words:
        return 0
    # Average 1.33 tokens per word for Latin scripts, ~4 chars per token fallback
    return max(int(len(words) * 1.33), int(len(text) / 4), 1)


def split_into_sentences(text: str) -> List[str]:
    """
    Splits text into sentences cleanly.
    Never splits mid-sentence: handles abbreviations, decimals, and multiline wraps.
    For overly long unpunctuated blocks, splits on secondary boundaries (e.g. semicolons or linebreaks).
    """
    paragraphs = re.split(r"\n\s*\n+", text)
    sentences: List[str] = []

    for p in paragraphs:
        p_clean = re.sub(r"[ \t]+", " ", p.strip())
        if not p_clean:
            continue

        temp = p_clean
        replacements: Dict[str, str] = {}
        for idx, abbr in enumerate(ABBREVIATIONS):
            matches = list(re.finditer(abbr, temp, re.I))
            for m in reversed(matches):
                key = f"__ABBR_{idx}_{m.start()}__"
                replacements[key] = m.group(0)
                temp = temp[:m.start()] + key + temp[m.end():]

        # Protect decimal numbers (e.g. 1.2, 3.14)
        dec_matches = list(re.finditer(r"\b\d+\.\d+\b", temp))
        for m in reversed(dec_matches):
            key = f"__DEC_{m.start()}__"
            replacements[key] = m.group(0)
            temp = temp[:m.start()] + key + temp[m.end():]

        # Split on sentence terminals: . ? ! । followed by whitespace or end
        parts = re.split(r"(?<=[.?!।])\s+", temp)

        for part in parts:
            part_restored = part
            for key, val in replacements.items():
                part_restored = part_restored.replace(key, val)
            part_restored = part_restored.strip()
            if not part_restored:
                continue

            # If part is exceptionally long (> 400 tokens) due to missing punctuation,
            # split on linebreaks or semicolons without breaking words
            if estimate_tokens(part_restored) > 400:
                sub_parts = re.split(r"(?<=[;\n])\s+", part_restored)
                for sp in sub_parts:
                    sp_s = sp.strip()
                    if sp_s:
                        sentences.append(sp_s)
            else:
                sentences.append(part_restored)

    return sentences


class CurriculumChunker:
    def __init__(
        self,
        books_dir: Optional[Path] = None,
        pages_dir: Optional[Path] = None,
        chunks_dir: Optional[Path] = None,
        inventory_csv: Optional[Path] = None,
        db_path: Optional[Path] = None,
        target_min_tokens: int = 150,
        target_max_tokens: int = 400,
        overlap_tokens: int = 35,
    ):
        self.books_dir = books_dir or BOOKS_DIR
        self.pages_dir = pages_dir or PAGES_DIR
        self.chunks_dir = chunks_dir or CHUNKS_DIR
        self.inventory_csv = inventory_csv or INVENTORY_CSV
        self.db_path = db_path or DB_PATH
        self.target_min_tokens = target_min_tokens
        self.target_max_tokens = target_max_tokens
        self.overlap_tokens = overlap_tokens

        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.sha_to_file = self._load_inventory_sha_map()
        self.db_node_map = self._load_db_node_map()

    def _load_inventory_sha_map(self) -> Dict[str, str]:
        """Loads sha256 -> filename mapping from textbooks_inventory.csv for fallbacks."""
        mapping = {}
        if not self.inventory_csv.exists():
            return mapping
        try:
            with open(self.inventory_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sha = row.get("sha256")
                    fname = row.get("file")
                    if sha and fname:
                        mapping[sha] = fname
        except Exception as e:
            logger.warning(f"Could not load inventory CSV: {e}")
        return mapping

    def _load_db_node_map(self) -> Dict[Any, str]:
        """Loads DB node id lookup from curriculum_nodes table in edusim.db."""
        node_map = {}
        if not self.db_path.exists():
            return node_map
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                SELECT b.code, n.id, n.identity_key, n.chapter_number, n.level, n.normalized_title
                FROM curriculum_nodes n
                JOIN books b ON n.book_id = b.id
            """)
            for code, nid, ident, ch_num, lvl, norm_title in c.fetchall():
                if ident:
                    node_map[(code, "ident", ident)] = nid
                if norm_title:
                    node_map[(code, "attr", str(ch_num), lvl, norm_title.strip().lower())] = nid
            conn.close()
        except Exception as e:
            logger.warning(f"Could not load edusim.db nodes: {e}")
        return node_map

    def get_page_path(self, file_id: str) -> Path:
        clean_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", file_id)
        return self.pages_dir / f"{clean_id}.jsonl"

    def classify_page_skip(
        self,
        text: str,
        page_no: int,
        is_whole_book: bool,
        first_ch_start: int,
        ch_title: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """
        Explicit rules to skip front/back matter and non-teaching pages.
        Logged with explicit reason code.
        """
        # Rule 2: Explicit front matter chapter
        if re.search(r"\b(front\s+pages|preliminary|preface|table\s+of\s+contents)\b", ch_title, re.I):
            return True, "rule_2_front_matter_chapter"

        # Rule 1: Whole-book pre-chapter pages
        if is_whole_book and first_ch_start > 1 and page_no < first_ch_start:
            return True, "rule_1_whole_book_pre_chapter"

        clean_text = text.strip()
        # Rule 5: Empty / insufficient text
        stripped = re.sub(r"^\s*\d+\s*$", "", clean_text, flags=re.M).strip()
        if len(stripped) < 25:
            return True, "rule_5_insufficient_text"

        # Rule 3: Copyright / ISBN / Publishing details
        if COPYRIGHT_REGEX.search(clean_text[:600]):
            return True, "rule_3_copyright_isbn"

        # Rule 3: Top heading is Foreword / Contents / Preamble
        first_3_lines = "\n".join([l.strip() for l in clean_text.split("\n") if l.strip()][:3])
        if FRONT_MATTER_TOP_REGEX.search(first_3_lines):
            return True, "rule_3_front_matter_heading"

        # Rule 4: Back matter heading
        if BACK_MATTER_TOP_REGEX.search(first_3_lines):
            return True, "rule_4_back_matter_heading"

        return False, None

    def _resolve_db_node_id(
        self,
        book_code: str,
        ch_num: str,
        level: str,
        normalized_title: str,
        identity_key: Optional[str],
        fallback_id: Optional[str],
    ) -> Optional[str]:
        """Resolves node_id to matching curriculum_nodes in edusim.db if loaded, else fallback."""
        if identity_key and (book_code, "ident", identity_key) in self.db_node_map:
            return self.db_node_map[(book_code, "ident", identity_key)]

        attr_key = (book_code, "attr", str(ch_num), level, normalized_title.strip().lower())
        if attr_key in self.db_node_map:
            return self.db_node_map[attr_key]

        return fallback_id

    def flatten_chapter_nodes(
        self,
        book_code: str,
        ch_num: str,
        nodes: List[Dict[str, Any]],
        parent_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recursively flattens chapter nodes preserving hierarchy:
        Class > Subject > Book > Chapter > Topic > Subtopic > Activity > Subheading.
        Computes accurate topic/subtopic path and resolves DB node_id.
        """
        flat = []
        for n in nodes:
            lvl = n.get("level") or "topic"
            title = n.get("official_title") or n.get("normalized_title") or ""
            norm_t = (n.get("normalized_title") or title).strip().lower()
            ident_key = n.get("identity_key")

            if lvl == "topic":
                cur_path = title
            elif lvl == "subtopic":
                cur_path = f"{parent_path} > {title}" if parent_path else title
            else:
                cur_path = parent_path if parent_path else None

            db_nid = self._resolve_db_node_id(
                book_code, ch_num, lvl, norm_t, ident_key, n.get("id")
            )

            flat.append({
                "node_id": db_nid,
                "raw_id": n.get("id"),
                "level": lvl,
                "title": title,
                "normalized_title": norm_t,
                "path": cur_path,
                "src_start": n.get("source_page_start", n.get("page_start", 1)),
                "src_end": n.get("source_page_end", n.get("page_end", 1)),
                "official_number": n.get("official_number"),
            })

            if n.get("nodes"):
                flat.extend(
                    self.flatten_chapter_nodes(
                        book_code,
                        ch_num,
                        n["nodes"],
                        cur_path if lvl in ("topic", "subtopic") else parent_path,
                    )
                )
        return flat

    def pack_units_into_chunks(
        self,
        units: List[Dict[str, Any]],
        base_meta: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Packs sentence units into coherent chunks of 150-400 tokens.
        Never splits mid-sentence. Merges small sections, applies ~10% overlap on split.
        """
        chunks: List[Dict[str, Any]] = []
        cur_units: List[Dict[str, Any]] = []
        cur_tokens = 0
        chunk_counter = 0

        def _emit_chunk(unit_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            nonlocal chunk_counter
            if not unit_list:
                return None
            chunk_counter += 1
            text = " ".join([u["text"] for u in unit_list])
            p_starts = [u["page"] for u in unit_list if u.get("page")]
            p_ends = [u["page"] for u in unit_list if u.get("page")]
            page_start = min(p_starts) if p_starts else base_meta.get("page_start", 1)
            page_end = max(p_ends) if p_ends else page_start

            paths = [u.get("path") for u in unit_list if u.get("path")]
            node_ids = [u.get("node_id") for u in unit_list if u.get("node_id")]
            path = paths[-1] if paths else None
            node_id = node_ids[-1] if node_ids else base_meta.get("chapter_node_id")

            cid = f"{base_meta['book_code']}_c{base_meta['chapter_number']}_{chunk_counter:04d}"

            chunk = {
                "chunk_id": cid,
                "board": base_meta["board"],
                "class": base_meta["class"],
                "subject": base_meta["subject"],
                "book_code": base_meta["book_code"],
                "book_title": base_meta["book_title"],
                "chapter_number": str(base_meta["chapter_number"]),
                "chapter_title": base_meta["chapter_title"],
                "topic_subtopic_path": path,
                "node_id": node_id,
                "page_start": page_start,
                "page_end": page_end,
                "source_pdf": base_meta["source_pdf"],
                "text": text,
                "token_count": estimate_tokens(text),
                "content_hash": compute_content_hash(
                    text=text,
                    board=base_meta["board"],
                    class_num=base_meta["class"],
                    subject=base_meta["subject"],
                    book_code=base_meta["book_code"],
                    chapter_number=str(base_meta["chapter_number"]),
                    page_start=page_start,
                    page_end=page_end,
                ),
            }
            return chunk

        for u in units:
            u_toks = estimate_tokens(u["text"])
            if cur_tokens + u_toks <= self.target_max_tokens:
                cur_units.append(u)
                cur_tokens += u_toks
            else:
                if cur_tokens >= self.target_min_tokens or not cur_units:
                    chk = _emit_chunk(cur_units)
                    if chk:
                        chunks.append(chk)

                    # Overlap: pick sentences from tail up to overlap_tokens
                    overlap_units: List[Dict[str, Any]] = []
                    acc_toks = 0
                    for prev_u in reversed(cur_units):
                        p_tok = estimate_tokens(prev_u["text"])
                        if acc_toks + p_tok <= self.overlap_tokens:
                            overlap_units.insert(0, prev_u)
                            acc_toks += p_tok
                        else:
                            break

                    cur_units = overlap_units + [u]
                    cur_tokens = sum(estimate_tokens(x["text"]) for x in cur_units)
                else:
                    # Small section: merge adjacent section even if slightly exceeds target_min
                    cur_units.append(u)
                    cur_tokens += u_toks

        if cur_units:
            tail_toks = sum(estimate_tokens(x["text"]) for x in cur_units)
            if tail_toks < 80 and chunks and (chunks[-1]["token_count"] + tail_toks <= self.target_max_tokens + 50):
                # Merge tiny tail into preceding chunk
                last = chunks[-1]
                last["text"] = last["text"] + " " + " ".join([u["text"] for u in cur_units])
                last["token_count"] = estimate_tokens(last["text"])
                p_ends = [u["page"] for u in cur_units if u.get("page")]
                if p_ends:
                    last["page_end"] = max(last["page_end"], max(p_ends))
                last["content_hash"] = compute_content_hash(
                    text=last["text"],
                    board=last["board"],
                    class_num=last["class"],
                    subject=last["subject"],
                    book_code=last["book_code"],
                    chapter_number=str(last["chapter_number"]),
                    page_start=last["page_start"],
                    page_end=last["page_end"],
                )
            else:
                chk = _emit_chunk(cur_units)
                if chk:
                    chunks.append(chk)

        return chunks

    def process_book(self, book_file: Path, force: bool = False) -> Dict[str, Any]:
        """
        Chunks one book from its JSON and page files.
        Idempotent: skips if output is newer than book_file unless force=True.
        """
        with open(book_file, "r", encoding="utf-8") as f:
            bdata = json.load(f)

        book_code = str(bdata.get("book_code") or book_file.stem).strip()
        out_file = self.chunks_dir / f"{book_code}.jsonl"
        stats_file = self.chunks_dir / f"{book_code}.stats.json"

        # Enforce needs_review policy: needs_review books must not be chunked or indexed
        extraction_status = str(bdata.get("extraction_status") or "ok").strip()
        if extraction_status == "needs_review":
            logger.info(f"Skipping book '{book_code}': extraction_status is 'needs_review'. Needs review books must not be chunked.")
            if out_file.exists():
                out_file.unlink()
            if stats_file.exists():
                stats_file.unlink()
            return {
                "book_code": book_code,
                "status": "skipped_needs_review",
                "chunks_count": 0,
                "avg_tokens": 0.0,
                "min_tokens": 0,
                "max_tokens": 0,
                "skipped_pages": 0,
                "skip_reasons": {},
                "missing_metadata": 0,
                "oversize_chunks": 0,
            }

        # Check idempotency
        if not force and out_file.exists() and out_file.stat().st_mtime >= book_file.stat().st_mtime:
            if stats_file.exists():
                try:
                    with open(stats_file, "r", encoding="utf-8") as sf:
                        cached_stats = json.load(sf)
                    cached_stats["status"] = "cached"
                    return cached_stats
                except Exception:
                    pass

            existing_chunks = []
            with open(out_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        existing_chunks.append(json.loads(line))
            tok_counts = [c["token_count"] for c in existing_chunks]
            missing_req = sum(
                1 for c in existing_chunks
                if not (c.get("board") and c.get("class") is not None and c.get("subject") and c.get("book_code"))
            )
            oversize = sum(1 for t in tok_counts if t > self.target_max_tokens)
            return {
                "book_code": book_code,
                "status": "cached",
                "chunks_count": len(existing_chunks),
                "avg_tokens": round(sum(tok_counts) / len(tok_counts), 1) if tok_counts else 0,
                "min_tokens": min(tok_counts) if tok_counts else 0,
                "max_tokens": max(tok_counts) if tok_counts else 0,
                "skipped_pages": bdata.get("skipped_pages_count", 0),
                "skip_reasons": {},
                "missing_metadata": missing_req,
                "oversize_chunks": oversize,
            }

        board = (bdata.get("board") or "").upper().strip()
        cls_num = bdata.get("class")
        if cls_num is not None:
            try:
                cls_num = int(cls_num)
            except ValueError:
                pass
        subject = str(bdata.get("subject") or "").strip().lower()
        book_title = str(bdata.get("book_title") or bdata.get("title") or book_code).strip()

        src_files = bdata.get("source_files") or []
        fallback_file = src_files[0] if src_files else self.sha_to_file.get(bdata.get("source_sha256"))

        chapters = bdata.get("chapters") or []
        is_whole_book = len(src_files) <= 1 and board == "SSC"
        first_ch_start = chapters[0].get("page_start", 1) if chapters else 1

        all_chunks: List[Dict[str, Any]] = []
        skipped_pages_count = 0
        skip_reasons: Dict[str, int] = {}

        for ch_idx, ch in enumerate(chapters):
            ch_num = str(ch.get("official_number") or (ch_idx + 1)).strip()
            ch_title = str(ch.get("official_title") or ch.get("normalized_title") or "").strip()
            ch_src_file = ch.get("source_file") or fallback_file

            if not ch_src_file:
                logger.warning(f"[{book_code}] Ch {ch_num} has no source file! Skipping.")
                continue

            ppath = self.get_page_path(ch_src_file)
            if not ppath.exists():
                logger.warning(f"[{book_code}] Ch {ch_num} page file {ppath.name} missing! Skipping.")
                continue

            p_start = ch.get("source_page_start", ch.get("page_start", 1))
            p_end = ch.get("source_page_end", ch.get("page_end", 1))
            book_page_offset = ch.get("page_start", 1) - p_start

            # Flatten chapter nodes
            ch_nodes = self.flatten_chapter_nodes(book_code, ch_num, ch.get("nodes") or [])
            ch_db_nid = self._resolve_db_node_id(
                book_code, ch_num, "chapter", (ch.get("normalized_title") or ch_title).strip().lower(),
                ch.get("identity_key"), ch.get("id")
            )

            # Node heading matcher for page text
            def match_heading(line_text: str, p_no: int) -> Optional[Dict[str, Any]]:
                line_clean = line_text.strip()
                if not line_clean or len(line_clean) < 3:
                    return None
                for n in ch_nodes:
                    if n["src_start"] <= p_no <= n["src_end"]:
                        t = n["title"].strip()
                        if line_clean.lower() == t.lower():
                            return n
                        if n.get("official_number") and (
                            line_clean.lower().startswith(f"{n['official_number']} ".lower())
                            or line_clean.lower().startswith(f"activity {n['official_number']}".lower())
                        ):
                            return n
                        if line_clean.lower().startswith(t.lower()) and len(t) >= 5:
                            if len(t.split()) >= 2 or len(t) >= 8:
                                return n
                return None

            units: List[Dict[str, Any]] = []
            current_node: Dict[str, Any] = {
                "node_id": ch_db_nid,
                "path": None,
                "title": ch_title,
            }

            with open(ppath, "r", encoding="utf-8") as pf:
                for line in pf:
                    prec = json.loads(line)
                    if prec.get("type") == "metadata":
                        continue
                    p_no = prec.get("page_no")
                    if not (p_start <= p_no <= p_end):
                        continue

                    # Check skip rules
                    should_skip, reason = self.classify_page_skip(
                        prec.get("text", ""),
                        p_no,
                        is_whole_book,
                        first_ch_start,
                        ch_title,
                    )
                    if should_skip:
                        skipped_pages_count += 1
                        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                        continue

                    raw_text = prec.get("text", "").strip()
                    book_p_no = p_no + book_page_offset

                    lines = raw_text.split("\n")
                    block_lines: List[str] = []

                    for l in lines:
                        h_node = match_heading(l, p_no)
                        if h_node:
                            if block_lines:
                                block_text = "\n".join(block_lines).strip()
                                for s in split_into_sentences(block_text):
                                    units.append({
                                        "text": s,
                                        "page": book_p_no,
                                        "node_id": current_node.get("node_id"),
                                        "path": current_node.get("path"),
                                    })
                                block_lines = []
                            current_node = h_node
                        else:
                            block_lines.append(l)

                    if block_lines:
                        block_text = "\n".join(block_lines).strip()
                        for s in split_into_sentences(block_text):
                            units.append({
                                "text": s,
                                "page": book_p_no,
                                "node_id": current_node.get("node_id"),
                                "path": current_node.get("path"),
                            })

            base_meta = {
                "board": board,
                "class": cls_num,
                "subject": subject,
                "book_code": book_code,
                "book_title": book_title,
                "chapter_number": ch_num,
                "chapter_title": ch_title,
                "source_pdf": ch_src_file,
                "chapter_node_id": ch_db_nid,
                "page_start": ch.get("page_start", 1),
                "page_end": ch.get("page_end", 1),
            }

            ch_chunks = self.pack_units_into_chunks(units, base_meta)
            all_chunks.extend(ch_chunks)

        if len(all_chunks) == 0:
            logger.warning(
                f"Book '{book_code}' yielded 0 chunks (extraction_status='{extraction_status}', text_quality='{bdata.get('text_quality')}')."
            )
            if out_file.exists():
                out_file.unlink()
            if stats_file.exists():
                stats_file.unlink()
            return {
                "book_code": book_code,
                "status": "skipped_empty",
                "chunks_count": 0,
                "avg_tokens": 0.0,
                "min_tokens": 0,
                "max_tokens": 0,
                "skipped_pages": skipped_pages_count,
                "skip_reasons": skip_reasons,
                "missing_metadata": 0,
                "oversize_chunks": 0,
            }

        # Write output JSONL
        with open(out_file, "w", encoding="utf-8") as out_f:
            for chk in all_chunks:
                out_f.write(json.dumps(chk, ensure_ascii=False) + "\n")

        # Validate mandatory fields
        missing_req = 0
        for chk in all_chunks:
            if not (chk.get("board") and chk.get("class") is not None and chk.get("subject") and chk.get("book_code")):
                missing_req += 1

        tok_counts = [c["token_count"] for c in all_chunks]
        oversize = sum(1 for t in tok_counts if t > self.target_max_tokens)
        stats_data = {
            "book_code": book_code,
            "status": "generated",
            "chunks_count": len(all_chunks),
            "avg_tokens": round(sum(tok_counts) / len(tok_counts), 1) if tok_counts else 0,
            "min_tokens": min(tok_counts) if tok_counts else 0,
            "max_tokens": max(tok_counts) if tok_counts else 0,
            "skipped_pages": skipped_pages_count,
            "skip_reasons": skip_reasons,
            "missing_metadata": missing_req,
            "oversize_chunks": oversize,
        }
        with open(stats_file, "w", encoding="utf-8") as sf:
            json.dump(stats_data, sf, indent=2, ensure_ascii=False)

        return stats_data

    def run_all(self, force: bool = False, book_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Processes books in curriculum/books/*.json."""
        if book_codes:
            book_files = [self.books_dir / f"{bc}.json" for bc in book_codes if (self.books_dir / f"{bc}.json").exists()]
        else:
            book_files = sorted(list(self.books_dir.glob("*.json")))
        results = []
        for bf in book_files:
            res = self.process_book(bf, force=force)
            results.append(res)
        return results


INITIAL_36_BOOKS = [
    "aejm1", "aejm1_demo", "aemr1", "bejm1", "bemr1", "ceev1", "cemm1", "deev1", "demm1",
    "eeev1", "eemm1", "fecu1", "fegp1", "gees1", "gees2", "hecu1", "hepr1", "iemh1",
    "iesc1", "jemh1", "jesc1", "jewe2", "kebo1", "kech1", "kemh1", "khat1", "lebo1",
    "leph1", "ssc_1eng", "ssc_1st_class_english_2025_26", "ssc_4th_tel_fl_2025_26",
    "ssc_english_class_x_total_book_08_11_2024", "ssc_i_fl_hindi_2025_26",
    "ssc_vi_maths_em_final_2025_26_02_11_2024_", "ssc_x_biology_em_2025_26",
    "ssc_x_mathematics_em_2025_26_02_11_2024_"
]


def print_report_table(results: List[Dict[str, Any]]):
    """Prints a structured ASCII per-book report."""
    headers = ["Book Code", "Chunks", "Avg Tok", "Min", "Max", "Skip Pgs", "Oversize", "Missing Meta", "Status"]
    col_widths = [42, 8, 9, 6, 6, 9, 9, 13, 12]

    fmt_row = " | ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "-+-".join("-" * w for w in col_widths)

    print("\n" + "=" * len(separator))
    print("CURRICULUM CHUNKER REPORT")
    print("=" * len(separator))
    print(fmt_row.format(*headers))
    print(separator)

    total_chunks = 0
    total_skipped = 0
    total_oversize = 0
    total_missing = 0

    for r in results:
        total_chunks += r.get("chunks_count", 0)
        total_skipped += r.get("skipped_pages", 0)
        total_oversize += r.get("oversize_chunks", 0)
        total_missing += r.get("missing_metadata", 0)

        row_vals = [
            r["book_code"][:col_widths[0]],
            str(r.get("chunks_count", 0)),
            f"{r.get('avg_tokens', 0.0):.1f}",
            str(r.get("min_tokens", 0)),
            str(r.get("max_tokens", 0)),
            str(r.get("skipped_pages", 0)),
            str(r.get("oversize_chunks", 0)),
            str(r.get("missing_metadata", 0)),
            r.get("status", "unknown"),
        ]
        print(fmt_row.format(*row_vals))

    print(separator)
    summary_vals = [
        f"TOTAL ({len(results)} books)",
        str(total_chunks),
        "-",
        "-",
        "-",
        str(total_skipped),
        str(total_oversize),
        str(total_missing),
        "DONE",
    ]
    print(fmt_row.format(*summary_vals))
    print("=" * len(separator) + "\n")


def verify_chunks_and_sample(chunks_dir: Path, num_samples: int = 5, book_codes: Optional[List[str]] = None):
    """
    Selects random chunks across specified JSONL files, prints them,
    and asserts mandatory metadata fields.
    """
    if book_codes:
        all_chunk_files = [chunks_dir / f"{bc}.jsonl" for bc in book_codes if (chunks_dir / f"{bc}.jsonl").exists()]
    else:
        all_chunk_files = sorted(list(chunks_dir.glob("*.jsonl")))

    collected_chunks: List[Dict[str, Any]] = []

    for cf in all_chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if line.strip():
                    chunk = json.loads(line)
                    # Check mandatory metadata
                    for req_field in ["board", "class", "subject", "book_code", "content_hash"]:
                        val = chunk.get(req_field)
                        if val is None or (isinstance(val, str) and not val.strip()):
                            raise AssertionError(
                                f"FATAL: Missing mandatory field '{req_field}' in {cf.name} line {line_no}!\n{chunk}"
                            )
                    collected_chunks.append(chunk)

    print(f"VERIFICATION: Verified {len(collected_chunks)} chunks across {len(all_chunk_files)} books.")
    print("ALL chunks passed mandatory metadata assertion (board, class, subject, book_code, content_hash).\n")

    if collected_chunks:
        sample_size = min(num_samples, len(collected_chunks))
        random.seed(42)  # Deterministic seed for reproducible verification
        samples = random.sample(collected_chunks, sample_size)
        print("=" * 80)
        print(f"5 RANDOMLY CHOSEN CHUNKS WITH FULL METADATA:")
        print("=" * 80)
        for idx, sample in enumerate(samples, 1):
            print(f"\n--- SAMPLE CHUNK {idx} ---")
            print(json.dumps(sample, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="EduSim Curriculum Chunker")
    parser.add_argument("--force", action="store_true", help="Force rechunking even if output is newer than book JSON")
    parser.add_argument("--book", type=str, default=None, help="Process single book code")
    parser.add_argument("--initial-36", action="store_true", help="Process only the initial 36 extracted books")
    args = parser.parse_args()

    chunker = CurriculumChunker()
    if args.book:
        target_file = chunker.books_dir / f"{args.book}.json"
        if not target_file.exists():
            print(f"Error: {target_file} not found.", file=sys.stderr)
            sys.exit(1)
        res = chunker.process_book(target_file, force=args.force)
        print_report_table([res])
        if res.get("chunks_count", 0) == 0:
            print(f"\n[ERROR] Book '{args.book}' yielded 0 chunks (status: {res.get('status')}).", file=sys.stderr)
            sys.exit(1)
    elif args.initial_36:
        results = chunker.run_all(force=args.force, book_codes=INITIAL_36_BOOKS)
        print_report_table(results)
        verify_chunks_and_sample(chunker.chunks_dir, book_codes=INITIAL_36_BOOKS)
    else:
        results = chunker.run_all(force=args.force)
        print_report_table(results)
        verify_chunks_and_sample(chunker.chunks_dir)


if __name__ == "__main__":
    main()
