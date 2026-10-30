"""
EduSim Curriculum Pipeline — Vector Indexer
==========================================
Reads chunk JSONL files from output/chunks/*.jsonl, embeds with all-MiniLM-L6-v2
(384-dim, normalized), and writes a unified FAISS index to EduSim_API/faiss_index_v2/
(index.faiss + metadata.json aligned by row id).

Idempotent: skips chunks already indexed by chunk_id, enabling incremental updates.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from curriculum_pipeline.pipeline_config import API_ROOT, PIPELINE_OUTPUT_ROOT
from curriculum_pipeline.chunker import compute_content_hash

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("EduSim.indexer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CHUNKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "chunks"
BOOKS_DIR: Path = PIPELINE_OUTPUT_ROOT / "curriculum" / "books"
INDEX_V2_DIR: Path = API_ROOT / "faiss_index_v2"
INDEX_V2_FILE: Path = INDEX_V2_DIR / "index.faiss"
METADATA_V2_FILE: Path = INDEX_V2_DIR / "metadata.json"
MODEL_NAME: str = "all-MiniLM-L6-v2"
EMBEDDING_DIM: int = 384


class CurriculumIndexer:
    def __init__(
        self,
        chunks_dir: Optional[Path] = None,
        books_dir: Optional[Path] = None,
        index_dir: Optional[Path] = None,
        model_name: str = MODEL_NAME,
        batch_size: int = 64,
    ):
        self.chunks_dir = chunks_dir or CHUNKS_DIR
        self.books_dir = books_dir or BOOKS_DIR
        self.index_dir = index_dir or INDEX_V2_DIR
        self.index_file = self.index_dir / "index.faiss"
        self.metadata_file = self.index_dir / "metadata.json"
        self.model_name = model_name
        self.batch_size = batch_size
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def load_existing_index(self) -> Tuple[Optional[faiss.IndexFlatIP], List[Dict[str, Any]], Dict[str, str]]:
        """Loads existing FAISS index and metadata map (chunk_id -> content_hash)."""
        if not (self.index_file.exists() and self.metadata_file.exists()):
            return None, [], {}

        try:
            logger.info(f"Loading existing FAISS index from {self.index_file}...")
            index = faiss.read_index(str(self.index_file))
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            indexed_hashes = {
                m.get("chunk_id"): m.get("content_hash", "")
                for m in metadata if m.get("chunk_id")
            }
            logger.info(f"Loaded existing index with {index.ntotal} vectors and {len(metadata)} metadata rows.")
            return index, metadata, indexed_hashes
        except Exception as e:
            logger.warning(f"Could not load existing index from {self.index_dir}: {e}. Creating new.")
            return None, [], {}

    def get_disallowed_book_codes(self) -> Set[str]:
        """Finds books marked needs_review or non-ok that must not be indexed."""
        disallowed = set()
        for bf in self.books_dir.glob("*.json"):
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    bdata = json.load(f)
                bcode = bdata.get("book_code") or bf.stem
                st = bdata.get("extraction_status")
                tq = bdata.get("text_quality")
                if st == "needs_review" or (tq is not None and tq != "ok") or (st and st.startswith("skipped_")):
                    disallowed.add(bcode)
            except Exception:
                pass
        return disallowed

    def load_all_chunks(self) -> List[Dict[str, Any]]:
        """Reads all chunks from output/chunks/*.jsonl, skipping disallowed books."""
        disallowed = self.get_disallowed_book_codes()
        chunks = []
        chunk_files = sorted(list(self.chunks_dir.glob("*.jsonl")))
        for cf in chunk_files:
            bcode = cf.stem
            if bcode in disallowed:
                logger.info(f"Skipping chunks file {cf.name}: book '{bcode}' is flagged or needs_review.")
                continue

            with open(cf, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if line_s:
                        chk = json.loads(line_s)
                        if "content_hash" not in chk:
                            chk["content_hash"] = compute_content_hash(
                                text=chk.get("text", ""),
                                board=chk.get("board", ""),
                                class_num=chk.get("class"),
                                subject=chk.get("subject", ""),
                                book_code=chk.get("book_code", ""),
                                chapter_number=str(chk.get("chapter_number", "")),
                                page_start=chk.get("page_start", 1),
                                page_end=chk.get("page_end", 1),
                            )
                        chunks.append(chk)
        return chunks

    def build_or_update_index(self, force: bool = False, rebuild: bool = False) -> Dict[str, Any]:
        """
        Builds or incrementally updates the FAISS index from chunks.
        If rebuild=True, builds in a temp dir and atomically swaps.
        Checks content_hash so updated chunks are re-embedded.
        """
        all_chunks = self.load_all_chunks()
        logger.info(f"Loaded {len(all_chunks)} chunks from {self.chunks_dir}.")

        if rebuild:
            return self._rebuild_index_atomically(all_chunks)

        index, metadata, indexed_hashes = (None, [], {}) if force else self.load_existing_index()

        # Check for changed content hashes or new chunks
        new_chunks = []
        hash_mismatches = 0
        for c in all_chunks:
            cid = c.get("chunk_id")
            chash = c.get("content_hash")
            if cid not in indexed_hashes:
                new_chunks.append(c)
            elif indexed_hashes.get(cid) != chash:
                hash_mismatches += 1

        if hash_mismatches > 0 or force or index is None:
            logger.info(f"Detected {hash_mismatches} content_hash mismatches or force/clean rebuild. Rebuilding index.")
            return self._rebuild_index_atomically(all_chunks)

        logger.info(f"Found {len(new_chunks)} new chunks to embed and index ({len(all_chunks) - len(new_chunks)} skipped).")

        if new_chunks:
            texts = [c["text"] for c in new_chunks]
            logger.info(f"Embedding {len(texts)} chunks using {self.model_name} (batch_size={self.batch_size})...")

            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

            embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
            faiss.normalize_L2(embeddings)

            start_row = index.ntotal
            index.add(embeddings)

            # Assign row_ids and append metadata
            for i, chunk in enumerate(new_chunks):
                row_meta = dict(chunk)
                row_meta["row_id"] = start_row + i
                metadata.append(row_meta)

            logger.info(f"Saving updated index ({index.ntotal} vectors) to {self.index_file}...")
            faiss.write_index(index, str(self.index_file))

            logger.info(f"Saving updated metadata ({len(metadata)} rows) to {self.metadata_file}...")
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

        stats = self.compute_stats(metadata)
        return stats

    def _rebuild_index_atomically(self, all_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Builds the entire index from scratch in a temp directory, then atomically swaps."""
        temp_dir = self.index_dir.parent / f"{self.index_dir.name}_tmp_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_index_file = temp_dir / "index.faiss"
        temp_metadata_file = temp_dir / "metadata.json"

        logger.info(f"Rebuilding index from scratch with {len(all_chunks)} chunks in {temp_dir}...")
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        metadata = []

        if all_chunks:
            texts = [c["text"] for c in all_chunks]
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
            faiss.normalize_L2(embeddings)
            index.add(embeddings)

            for i, chunk in enumerate(all_chunks):
                row_meta = dict(chunk)
                row_meta["row_id"] = i
                metadata.append(row_meta)

        faiss.write_index(index, str(temp_index_file))
        with open(temp_metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # Atomic swap
        backup_dir = self.index_dir.parent / f"{self.index_dir.name}_bak_{uuid.uuid4().hex[:6]}"
        if self.index_dir.exists():
            try:
                os.rename(str(self.index_dir), str(backup_dir))
            except Exception as e:
                logger.warning(f"Failed to rename {self.index_dir} to backup: {e}")
                # Fallback to copy/replace
                shutil.copy2(str(temp_index_file), str(self.index_file))
                shutil.copy2(str(temp_metadata_file), str(self.metadata_file))
                shutil.rmtree(temp_dir, ignore_errors=True)
                stats = self.compute_stats(metadata)
                return stats

        os.rename(str(temp_dir), str(self.index_dir))
        shutil.rmtree(backup_dir, ignore_errors=True)
        logger.info(f"Atomically swapped rebuilt index into {self.index_dir} ({index.ntotal} vectors).")

        stats = self.compute_stats(metadata)
        return stats

    def compute_stats(self, metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Computes breakdown stats by board, class, and subject."""
        board_counts = Counter()
        class_counts = Counter()
        subject_counts = Counter()

        for m in metadata:
            board = str(m.get("board", "unknown")).upper()
            cls_val = m.get("class")
            cls_str = f"Class {cls_val}" if cls_val is not None else "Unknown"
            subj = str(m.get("subject", "unknown")).lower()

            board_counts[board] += 1
            class_counts[cls_str] += 1
            subject_counts[subj] += 1

        return {
            "total_vectors": len(metadata),
            "by_board": dict(sorted(board_counts.items())),
            "by_class": dict(sorted(class_counts.items(), key=lambda x: (len(x[0]), x[0]))),
            "by_subject": dict(sorted(subject_counts.items(), key=lambda x: -x[1])),
        }


def print_stats_report(stats: Dict[str, Any]):
    """Pretty prints index inventory statistics."""
    print("\n" + "=" * 65)
    print("FAISS INDEX V2 INVENTORY REPORT")
    print("=" * 65)
    print(f"Total Vectors Indexed: {stats['total_vectors']}")

    print("\n--- By Board ---")
    for board, cnt in stats["by_board"].items():
        print(f"  {board:<15}: {cnt:>5} vectors")

    print("\n--- By Class ---")
    for cls, cnt in stats["by_class"].items():
        print(f"  {cls:<15}: {cnt:>5} vectors")

    print("\n--- By Subject ---")
    for subj, cnt in stats["by_subject"].items():
        print(f"  {subj:<25}: {cnt:>5} vectors")

    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build EduSim FAISS V2 vector index")
    parser.add_argument("--force", action="store_true", help="Force re-evaluate index from scratch")
    parser.add_argument("--rebuild", action="store_true", help="Atomically rebuild FAISS index from scratch in temp dir")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    args = parser.parse_args()

    indexer = CurriculumIndexer(batch_size=args.batch_size)
    stats = indexer.build_or_update_index(force=args.force, rebuild=args.rebuild)
    print_stats_report(stats)


if __name__ == "__main__":
    main()
