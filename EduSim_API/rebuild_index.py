"""
EduSim Rebuild Index CLI Entrypoint
===================================
Rebuilds the FAISS vector index using FAISS_INDEX_V2_DIR or model-specific directory.
Supports --model and --output-dir, writing index_manifest.json next to index.faiss.
Protects the production index from being overwritten when building alternative model indexes.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EduSim.rebuild_index")

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def rebuild(model_name: str | None = None, output_dir: str | Path | None = None, batch_size: int = 64):
    model = model_name or DEFAULT_MODEL

    # Determine safe output directory
    if output_dir:
        index_dir = Path(output_dir).resolve()
    else:
        # Default behavior:
        # If model is default all-MiniLM-L6-v2, use FAISS_INDEX_V2_DIR
        # If model is a different/multilingual model, build to a separate directory to protect v2 index
        if model == "all-MiniLM-L6-v2":
            index_dir = Path(os.getenv("FAISS_INDEX_V2_DIR", str(API_ROOT / "faiss_index_v2"))).resolve()
        else:
            model_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", model).strip("_")
            index_dir = (API_ROOT / f"faiss_index_{model_slug}").resolve()

    textbooks_dir = Path(os.getenv("TEXTBOOKS_DIR", str(API_ROOT / "textbooks"))).resolve()

    logger.info("=========================================")
    logger.info("Rebuilding EduSim FAISS Index")
    logger.info("=========================================")
    logger.info("Embedding Model:       %s", model)
    logger.info("Target Index Dir:      %s", index_dir)
    logger.info("Resolved TEXTBOOKS_DIR: %s", textbooks_dir)

    chunks_dir = API_ROOT / "curriculum_pipeline" / "output" / "chunks"
    if chunks_dir.exists() and any(chunks_dir.glob("*.jsonl")):
        logger.info("Building index from curriculum pipeline chunks at %s...", chunks_dir)
        from curriculum_pipeline.indexer import CurriculumIndexer, print_stats_report

        indexer = CurriculumIndexer(
            chunks_dir=chunks_dir,
            index_dir=index_dir,
            model_name=model,
            batch_size=batch_size,
        )
        stats = indexer.build_or_update_index(rebuild=True)
        print_stats_report(stats)
        logger.info("Index build complete. Manifest written to: %s", index_dir / "index_manifest.json")
    else:
        logger.info("Building index from textbooks at %s via legacy pipeline...", textbooks_dir)
        from app.src.modules.legacy_rag.rebuild_index import rebuild as legacy_rebuild

        legacy_rebuild()


def main():
    parser = argparse.ArgumentParser(description="Rebuild EduSim FAISS Vector Index")
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Embedding model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory for the index (defaults to separate dir for non-default models)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for embedding generation (default: 64)",
    )
    args = parser.parse_args()
    rebuild(model_name=args.model, output_dir=args.output_dir, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
