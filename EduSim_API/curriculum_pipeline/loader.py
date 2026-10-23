"""
EduSim Curriculum Database Loader
=================================
Resumable, transactional loader that imports validated curriculum JSON trees
into the database (`books` and `curriculum_nodes` tables).

Key features:
- Runs CurriculumValidator first; refuses any book with validation errors.
- Refuses books with extraction_status='needs_review' unless --include-review is passed.
- Resumable: skips books whose sha256 and pipeline_version match the database unless --force.
- Identity key upsert: hash of (chapter_number, parent identity key, level, normalized_title, occurrence_index).
- Rename detection: pairs unmatched existing active and incoming nodes with the same parent,
  level, and non-null unique official_number, updating title in-place while retaining primary key.
- Soft-deactivation: missing nodes receive is_active=False (never hard-deleted).
  Reappearing nodes are reactivated.
- Supports --dry-run to simulate and report changes without committing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.src.config.database import SessionLocal
from app.src.models.curriculum_pipeline_models import Book, CurriculumNode
from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT, PIPELINE_VERSION
from curriculum_pipeline.validator import CurriculumValidator

logger = logging.getLogger("EduSim.curriculum_loader_v2")


def compute_node_identity_key(
    chapter_number: str,
    parent_identity_key: str,
    level: str,
    normalized_title: str,
    occurrence_index: int,
) -> str:
    """Computes a deterministic 32-character identity key for a curriculum node."""
    norm_t = re.sub(r"\s+", " ", normalized_title or "").strip().lower()
    raw = f"{chapter_number}|{parent_identity_key}|{level}|{norm_t}|{occurrence_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class CurriculumDatabaseLoader:
    def __init__(self, validator: Optional[CurriculumValidator] = None):
        self.validator = validator or CurriculumValidator()

    def flatten_tree_nodes(
        self,
        chapters: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Flattens the nested chapter/topic/subtopic/activity/subheading tree
        and assigns parent identity keys and deterministic node identity keys.
        """
        flat_nodes: List[Dict[str, Any]] = []
        sibling_counts: Dict[Tuple[str, str, str], int] = {}

        def _traverse(node: Dict[str, Any], chapter_num: str, parent_ident: str, order_idx: int):
            lvl = node.get("level", "chapter")
            norm_t = re.sub(r"\s+", " ", node.get("normalized_title") or node.get("official_title", "")).strip().lower()
            key = (parent_ident, lvl, norm_t)
            occ_idx = sibling_counts.get(key, 0)
            sibling_counts[key] = occ_idx + 1
            ident_key = compute_node_identity_key(chapter_num, parent_ident, lvl, norm_t, occ_idx)

            # Metadata contains unstructured_ranges, wrapper, preview, kind, warnings
            meta = dict(node.get("metadata_json") or {})
            if node.get("wrapper"):
                meta["wrapper"] = node["wrapper"]
            if node.get("kind"):
                meta["kind"] = node["kind"]
            if node.get("preview"):
                meta["preview"] = node["preview"]
            if node.get("unstructured_ranges"):
                meta["unstructured_ranges"] = node["unstructured_ranges"]
            if node.get("evidence"):
                meta["evidence"] = node["evidence"]

            flat_rec = {
                "chapter_number": chapter_num,
                "level": lvl,
                "parent_identity_key": parent_ident,
                "identity_key": ident_key,
                "order_index": order_idx,
                "official_number": node.get("official_number"),
                "title": node.get("official_title", ""),
                "normalized_title": norm_t,
                "occurrence_index": occ_idx,
                "page_start": node.get("page_start", 0),
                "page_end": node.get("page_end", 0),
                "source_file": node.get("source_file"),
                "ocr_needed": bool(node.get("ocr_needed", False)),
                "metadata_json": meta,
            }
            flat_nodes.append(flat_rec)

            for child_idx, child in enumerate(node.get("nodes", [])):
                _traverse(child, chapter_num, ident_key, child_idx)

        for ch_idx, ch in enumerate(chapters):
            ch_num = str(ch.get("official_number", ch_idx + 1))
            _traverse(ch, ch_num, "root", ch_idx)

        return flat_nodes

    def load_book(
        self,
        book_file: Path,
        db: Session,
        run_id: str,
        force: bool = False,
        include_review: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Loads a single book JSON into the database within an isolated transaction."""
        book_code = book_file.stem
        stats = {
            "book_code": book_code,
            "status": "skipped",
            "reason": "",
            "inserted": 0,
            "updated": 0,
            "renamed": 0,
            "reactivated": 0,
            "deactivated": 0,
            "unchanged": 0,
            "total_nodes": 0,
            "level_counts": {"chapter": 0, "topic": 0, "subtopic": 0, "activity": 0, "subheading": 0},
        }

        # 1. Validator preflight
        issues = self.validator.validate_file(book_file)
        errors = [i for i in issues if i.severity == "ERROR"]
        if errors:
            stats["status"] = "refused"
            stats["reason"] = f"Validation failed with {len(errors)} error(s): {errors[0].message}"
            return stats

        with open(book_file, "r", encoding="utf-8") as f:
            book_data = json.load(f)

        status = book_data.get("extraction_status", "ok")
        is_ssc = book_data.get("board") == "ssc" or book_code.startswith("ssc_")
        if (status == "needs_review" or is_ssc) and not include_review:
            stats["status"] = "refused"
            stats["reason"] = "Book extraction_status is 'needs_review' or board is 'ssc' (use --include-review to load)"
            return stats

        # 2. Resumable SHA-256 and version check
        existing_book = db.query(Book).filter(Book.code == book_code).first()
        incoming_sha = book_data.get("source_sha256", "")
        if (
            existing_book
            and not force
            and existing_book.sha256 == incoming_sha
            and existing_book.pipeline_version == PIPELINE_VERSION
            and existing_book.extraction_status == status
        ):
            stats["status"] = "skipped"
            stats["reason"] = "Unchanged sha256 and pipeline_version (use --force to reload)"
            return stats

        # 3. Flatten incoming nodes
        chapters = book_data.get("chapters", [])
        incoming_flat = self.flatten_tree_nodes(chapters)
        stats["total_nodes"] = len(incoming_flat)

        for rec in incoming_flat:
            lvl = rec["level"]
            if lvl in stats["level_counts"]:
                stats["level_counts"][lvl] += 1

        if dry_run:
            # Simulate match / rename / insert / deactivate
            self._simulate_load(existing_book, incoming_flat, stats)
            stats["status"] = "dry_run"
            stats["reason"] = "Simulated run (no database changes committed)"
            return stats

        # 4. Upsert Book record
        if not existing_book:
            existing_book = Book(
                id=uuid.uuid4(),
                code=book_code,
                title=book_data.get("title") or book_data.get("book_title", book_code),
                board=book_data.get("board", "ncert"),
                class_num=int(book_data.get("class", 0)),
                subject=book_data.get("subject", "unknown"),
                language=book_data.get("medium", "en"),
                part=book_data.get("part"),
                total_pages=int(book_data.get("total_pages", 0)),
                sha256=incoming_sha,
                extraction_status=status,
                pipeline_version=PIPELINE_VERSION,
                source_files=book_data.get("source_files", []),
            )
            db.add(existing_book)
            db.flush()
        else:
            existing_book.title = book_data.get("title") or book_data.get("book_title", existing_book.title)
            existing_book.total_pages = int(book_data.get("total_pages", existing_book.total_pages))
            existing_book.sha256 = incoming_sha
            existing_book.extraction_status = status
            existing_book.pipeline_version = PIPELINE_VERSION
            existing_book.source_files = book_data.get("source_files", existing_book.source_files)
            db.flush()

        # 5. Fetch existing nodes for book
        existing_nodes = (
            db.query(CurriculumNode)
            .filter(CurriculumNode.book_id == existing_book.id)
            .all()
        )
        existing_by_key: Dict[str, CurriculumNode] = {n.identity_key: n for n in existing_nodes}
        existing_by_id: Dict[uuid.UUID, CurriculumNode] = {n.id: n for n in existing_nodes}

        matched_incoming_keys: Set[str] = set()
        matched_existing_ids: Set[uuid.UUID] = set()

        # Node map: incoming identity_key -> DB CurriculumNode (for parenting)
        key_to_db_node: Dict[str, CurriculumNode] = {}

        # Pass 1: Exact Identity Key match
        for inc in incoming_flat:
            ikey = inc["identity_key"]
            if ikey in existing_by_key:
                ex_node = existing_by_key[ikey]
                matched_incoming_keys.add(ikey)
                matched_existing_ids.add(ex_node.id)
                key_to_db_node[ikey] = ex_node

                was_inactive = not ex_node.is_active
                if was_inactive:
                    ex_node.is_active = True
                    stats["reactivated"] += 1

                # Check if fields changed
                changed = (
                    ex_node.title != inc["title"]
                    or ex_node.page_start != inc["page_start"]
                    or ex_node.page_end != inc["page_end"]
                    or ex_node.official_number != inc["official_number"]
                    or ex_node.order_index != inc["order_index"]
                    or ex_node.source_file != inc["source_file"]
                    or ex_node.ocr_needed != inc["ocr_needed"]
                    or ex_node.metadata_json != inc["metadata_json"]
                )

                if changed:
                    ex_node.title = inc["title"]
                    ex_node.normalized_title = inc["normalized_title"]
                    ex_node.page_start = inc["page_start"]
                    ex_node.page_end = inc["page_end"]
                    ex_node.official_number = inc["official_number"]
                    ex_node.order_index = inc["order_index"]
                    ex_node.source_file = inc["source_file"]
                    ex_node.ocr_needed = inc["ocr_needed"]
                    ex_node.metadata_json = inc["metadata_json"]
                    stats["updated"] += 1
                elif not was_inactive:
                    stats["unchanged"] += 1

                ex_node.last_seen_run_id = run_id

        # Pass 2: Rename detection among unmatched active existing and unmatched incoming
        unmatched_incoming = [inc for inc in incoming_flat if inc["identity_key"] not in matched_incoming_keys]
        unmatched_active_existing = [
            ex for ex in existing_nodes if ex.id not in matched_existing_ids and ex.is_active
        ]

        # Group by (parent_identity_key, level)
        # Note: for existing nodes, determine their parent identity key from existing_by_id
        inc_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for inc in unmatched_incoming:
            key = (inc["parent_identity_key"], inc["level"])
            inc_groups.setdefault(key, []).append(inc)

        ex_groups: Dict[Tuple[str, str], List[CurriculumNode]] = {}
        for ex in unmatched_active_existing:
            parent_key = "root"
            if ex.parent_id and ex.parent_id in existing_by_id:
                parent_key = existing_by_id[ex.parent_id].identity_key
            key = (parent_key, ex.level)
            ex_groups.setdefault(key, []).append(ex)

        # Pair within groups by unique, non-null official_number
        for group_key, inc_list in inc_groups.items():
            if group_key not in ex_groups:
                continue
            ex_list = ex_groups[group_key]

            # Collect official_number frequencies
            inc_by_num: Dict[str, List[Dict[str, Any]]] = {}
            for inc in inc_list:
                if inc.get("official_number"):
                    inc_by_num.setdefault(str(inc["official_number"]), []).append(inc)

            ex_by_num: Dict[str, List[CurriculumNode]] = {}
            for ex in ex_list:
                if ex.official_number:
                    ex_by_num.setdefault(str(ex.official_number), []).append(ex)

            for num, inc_candidates in inc_by_num.items():
                if len(inc_candidates) == 1 and num in ex_by_num and len(ex_by_num[num]) == 1:
                    inc_item = inc_candidates[0]
                    ex_item = ex_by_num[num][0]

                    # Perform rename in-place
                    ex_item.title = inc_item["title"]
                    ex_item.normalized_title = inc_item["normalized_title"]
                    ex_item.identity_key = inc_item["identity_key"]
                    ex_item.page_start = inc_item["page_start"]
                    ex_item.page_end = inc_item["page_end"]
                    ex_item.order_index = inc_item["order_index"]
                    ex_item.source_file = inc_item["source_file"]
                    ex_item.ocr_needed = inc_item["ocr_needed"]
                    ex_item.metadata_json = inc_item["metadata_json"]
                    ex_item.last_seen_run_id = run_id
                    ex_item.is_active = True

                    matched_incoming_keys.add(inc_item["identity_key"])
                    matched_existing_ids.add(ex_item.id)
                    key_to_db_node[inc_item["identity_key"]] = ex_item
                    stats["renamed"] += 1

        # Pass 3: Insert remaining unmatched incoming nodes
        new_incoming = [inc for inc in incoming_flat if inc["identity_key"] not in matched_incoming_keys]
        for inc in new_incoming:
            new_node = CurriculumNode(
                id=uuid.uuid4(),
                book_id=existing_book.id,
                chapter_number=inc["chapter_number"],
                level=inc["level"],
                order_index=inc["order_index"],
                official_number=inc["official_number"],
                title=inc["title"],
                normalized_title=inc["normalized_title"],
                occurrence_index=inc["occurrence_index"],
                page_start=inc["page_start"],
                page_end=inc["page_end"],
                source_file=inc["source_file"],
                ocr_needed=inc["ocr_needed"],
                metadata_json=inc["metadata_json"],
                identity_key=inc["identity_key"],
                is_active=True,
                last_seen_run_id=run_id,
            )
            db.add(new_node)
            key_to_db_node[inc["identity_key"]] = new_node
            stats["inserted"] += 1

        db.flush()

        # Pass 4: Link parent_id for all incoming nodes
        for inc in incoming_flat:
            curr_db_node = key_to_db_node.get(inc["identity_key"])
            parent_key = inc["parent_identity_key"]
            if parent_key == "root":
                curr_db_node.parent_id = None
            else:
                parent_db_node = key_to_db_node.get(parent_key)
                if parent_db_node:
                    curr_db_node.parent_id = parent_db_node.id

        # Pass 5: Soft-deactivate remaining unmatched existing active nodes
        for ex in existing_nodes:
            if ex.id not in matched_existing_ids and ex.is_active:
                ex.is_active = False
                stats["deactivated"] += 1

        stats["status"] = "loaded"
        stats["reason"] = "Successfully loaded into database"
        return stats

    def _simulate_load(
        self,
        existing_book: Optional[Book],
        incoming_flat: List[Dict[str, Any]],
        stats: Dict[str, Any],
    ):
        """Calculates dry-run statistics without modifying the database."""
        if not existing_book:
            stats["inserted"] = len(incoming_flat)
            return

        db_nodes = existing_book.nodes
        ex_by_key = {n.identity_key: n for n in db_nodes}
        ex_ids = {n.id for n in db_nodes}

        matched_keys = set()
        matched_ids = set()

        for inc in incoming_flat:
            ikey = inc["identity_key"]
            if ikey in ex_by_key:
                ex = ex_by_key[ikey]
                matched_keys.add(ikey)
                matched_ids.add(ex.id)
                if not ex.is_active:
                    stats["reactivated"] += 1
                elif ex.title != inc["title"] or ex.page_start != inc["page_start"] or ex.page_end != inc["page_end"]:
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

        unmatched_inc = [inc for inc in incoming_flat if inc["identity_key"] not in matched_keys]
        unmatched_ex = [ex for ex in db_nodes if ex.id not in matched_ids and ex.is_active]

        # Check renames
        paired_nums = set()
        for inc in unmatched_inc:
            num = inc.get("official_number")
            if num and any(ex.official_number == num for ex in unmatched_ex) and num not in paired_nums:
                stats["renamed"] += 1
                paired_nums.add(num)

        stats["inserted"] = max(0, len(unmatched_inc) - len(paired_nums))
        stats["deactivated"] = max(0, len(unmatched_ex) - len(paired_nums))


def run_load_pipeline(
    books_dir: Optional[Path] = None,
    only_book: Optional[str] = None,
    include_review: bool = False,
    force: bool = False,
    dry_run: bool = False,
    session_factory: Callable[[], Session] = SessionLocal,
) -> List[Dict[str, Any]]:
    """CLI execution function: iterates through book JSON files and runs the loader."""
    target_dir = books_dir or (PIPELINE_OUTPUT_ROOT / "curriculum" / "books")
    if not target_dir.exists():
        print(f"[ERROR] Books directory not found: {target_dir}")
        return []

    book_files = sorted(list(target_dir.glob("*.json")))
    if only_book:
        target_name = only_book if only_book.endswith(".json") else f"{only_book}.json"
        book_files = [f for f in book_files if f.name == target_name]
        if not book_files:
            print(f"[ERROR] No book found matching --only '{only_book}' in {target_dir}")
            return []

    print("=" * 80)
    print("  EduSim Curriculum Database Loader")
    print("=" * 80)
    print(f"  Target directory: {target_dir}")
    print(f"  Books to inspect: {len(book_files)}")
    print(f"  Include review  : {include_review}")
    print(f"  Force reload    : {force}")
    print(f"  Dry-run mode    : {dry_run}")
    print("-" * 80)

    loader = CurriculumDatabaseLoader()
    run_id = str(uuid.uuid4())
    results: List[Dict[str, Any]] = []

    for idx, bfile in enumerate(book_files, 1):
        bcode = bfile.stem
        with session_factory() as db:
            try:
                res = loader.load_book(
                    book_file=bfile,
                    db=db,
                    run_id=run_id,
                    force=force,
                    include_review=include_review,
                    dry_run=dry_run,
                )
                if not dry_run and res["status"] == "loaded":
                    db.commit()
                elif not dry_run:
                    db.rollback()
            except Exception as e:
                db.rollback()
                res = {
                    "book_code": bcode,
                    "status": "error",
                    "reason": f"Database error: {str(e)}",
                    "inserted": 0,
                    "updated": 0,
                    "renamed": 0,
                    "reactivated": 0,
                    "deactivated": 0,
                    "unchanged": 0,
                    "total_nodes": 0,
                    "level_counts": {},
                }
            results.append(res)

        # Print per-book summary
        st = res["status"].upper()
        if st in ["LOADED", "DRY_RUN"]:
            lc = res["level_counts"]
            lc_str = ", ".join(f"{k}: {v}" for k, v in lc.items() if v > 0)
            print(
                f"[{idx:2d}/{len(book_files):2d}] {bcode:15s} -> [{st}] "
                f"Ins:{res['inserted']:3d} | Upd:{res['updated']:3d} | Ren:{res['renamed']:2d} | "
                f"Rea:{res['reactivated']:2d} | Dea:{res['deactivated']:2d} | Levels: [{lc_str}]"
            )
        else:
            print(f"[{idx:2d}/{len(book_files):2d}] {bcode:15s} -> [{st}] Skipped: {res['reason']}")

    print("=" * 80)
    print("Loader Summary:")
    loaded_cnt = sum(1 for r in results if r["status"] in ["loaded", "dry_run"])
    skipped_cnt = sum(1 for r in results if r["status"] == "skipped")
    refused_cnt = sum(1 for r in results if r["status"] == "refused")
    error_cnt = sum(1 for r in results if r["status"] == "error")

    total_ins = sum(r["inserted"] for r in results)
    total_upd = sum(r["updated"] for r in results)
    total_ren = sum(r["renamed"] for r in results)
    total_rea = sum(r["reactivated"] for r in results)
    total_dea = sum(r["deactivated"] for r in results)

    print(f"  Books processed : {len(results)}")
    print(f"  Loaded/Simulated: {loaded_cnt}")
    print(f"  Skipped (cached): {skipped_cnt}")
    print(f"  Refused         : {refused_cnt}")
    print(f"  Errors          : {error_cnt}")
    print(
        f"  Total Nodes     : Ins: {total_ins} | Upd: {total_upd} | Ren: {total_ren} | "
        f"Rea: {total_rea} | Dea: {total_dea}"
    )
    print("=" * 80)
    return results
