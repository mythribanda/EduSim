"""
EduSim RAG — Similarity Thresholds & Relative Scoring Config
============================================================
Provides per-model similarity cutoff thresholds and relative margin scoring.
Thresholds are keyed by EMBEDDING_MODEL with fallback to defaults or RAG_SIMILARITY_THRESHOLD.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("EduSim.config.similarity")

CONFIG_PATH = Path(__file__).resolve().parent / "similarity_thresholds.json"

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "all-MiniLM-L6-v2": 0.50,
    "sentence-transformers/all-MiniLM-L6-v2": 0.50,
    "intfloat/multilingual-e5-small": 0.82,
    "paraphrase-multilingual-MiniLM-L12-v2": 0.45,
    "BAAI/bge-m3": 0.55,
    "default": 0.50,
}

# Default margin parameters for relative scoring (top1 - top5)
DEFAULT_MIN_MARGIN: float = 0.06
DEFAULT_RESCUE_MARGIN: float = 0.10


def load_threshold_config() -> Dict[str, float]:
    """Loads per-model similarity threshold map from similarity_thresholds.json."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read {CONFIG_PATH}: {e}")
    return DEFAULT_THRESHOLDS


def get_similarity_threshold(model_name: Optional[str] = None) -> float:
    """
    Returns the similarity threshold:
    1. os.getenv("RAG_SIMILARITY_THRESHOLD") if explicitly set
    2. Config value keyed by model_name or os.getenv("EMBEDDING_MODEL")
    3. Default fallback (0.50)
    """
    env_override = os.getenv("RAG_SIMILARITY_THRESHOLD")
    if env_override:
        try:
            return float(env_override)
        except ValueError:
            pass

    effective_model = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    cfg = load_threshold_config()

    if effective_model in cfg:
        return float(cfg[effective_model])

    base_name = effective_model.split("/")[-1]
    if base_name in cfg:
        return float(cfg[base_name])

    return float(cfg.get("default", 0.50))


def evaluate_retrieval_confidence(
    chunks: List[Dict[str, Any]],
    threshold: float,
    min_margin: float = DEFAULT_MIN_MARGIN,
    rescue_margin: float = DEFAULT_RESCUE_MARGIN,
) -> Tuple[bool, str]:
    """
    Evaluates whether retrieved chunks represent confident topical retrieval vs noise.
    Supports both absolute thresholding and relative scoring margin:
    - If top_score >= threshold:
        - If multiple chunks exist and top1 - top5 margin is extremely flat (< 0.03),
          and top_score is barely above threshold (< threshold + 0.05), flags diffuse noise.
        - Otherwise returns (True, "passed_threshold").
    - If top_score < threshold:
        - Relative scoring rescue: if top_score >= (threshold - 0.15) and
          (top1 - top5) >= rescue_margin, accepts the query because of high topical separation.
        - Otherwise returns (False, "below_threshold").
    """
    if not chunks:
        return False, "no_chunks"

    scores = [float(c.get("score", 0.0)) for c in chunks]
    top_score = scores[0]
    tail_score = scores[-1] if len(scores) >= 5 else scores[-1]
    margin = top_score - tail_score

    # Check primary threshold
    if top_score >= threshold:
        # Detect flat diffuse background noise across unrelated chapters
        if len(chunks) >= 5 and margin < 0.02 and top_score < (threshold + 0.04):
            return False, f"flat_noise (top={top_score:.3f}, margin={margin:.3f})"
        return True, f"passed_threshold ({top_score:.3f} >= {threshold:.2f})"

    # Relative scoring rescue: high margin separates distinct relevant chapter
    rescue_floor = max(0.20, threshold - 0.15)
    if top_score >= rescue_floor and len(chunks) >= 3 and margin >= rescue_margin:
        return True, f"rescued_by_margin ({top_score:.3f} >= {rescue_floor:.2f}, margin={margin:.3f} >= {rescue_margin:.2f})"

    return False, f"below_threshold ({top_score:.3f} < {threshold:.2f})"
