"""
Regression tests for topic_subtopic_path coverage and fallback behavior.

Tests cover:
1. English (2 chapters):
   - keww1 Ch 2 (Literature story "A Pair of Mustachios" without subheadings): Legitimate null path.
   - keww1 Ch 3 (Literature story "The Rocking-horse Winner" without subheadings): Legitimate null path.
   - aemr1 Ch 1 (Primary English with section headings): Verified extraction of real section headings ('Parts of the Body', etc.).
2. Mathematics (2 chapters):
   - lemh2 Ch 1 (Class 12 Integrals): Numbered sections (7.1, 7.2...) correctly parsed, >= 90% path coverage.
   - kemh1 Ch 1 (Class 11 Sets): Numbered sections correctly parsed, >= 80% path coverage.
3. Social Science (2 chapters):
   - gees1 Ch 1 (Class 7 Geographical Diversity): Unnumbered section headings (The Himalayas, Gangetic Plains), >= 90% path coverage.
   - fees1 Ch 1 (Class 6 Social Science): Section headings preserved, >= 90% path coverage.
4. Fallback Behavior:
   - When topic_subtopic_path is null, query_rag_service context formatting gracefully falls back to chapter_title.
   - When topic_subtopic_path is present, it is formatted into the [TOPIC] prompt header.
"""

import sys
import json
import pytest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from unittest.mock import patch, AsyncMock


@pytest.fixture
def chunks_dir():
    return repo_root / "curriculum_pipeline" / "output" / "chunks"


@pytest.fixture
def books_dir():
    return repo_root / "curriculum_pipeline" / "output" / "curriculum" / "books"


def _load_book_chunks(chunks_dir: Path, book_code: str):
    chunk_file = chunks_dir / f"{book_code}.jsonl"
    if not chunk_file.exists():
        pytest.skip(f"Chunk file {chunk_file.name} does not exist in {chunks_dir}")
    chunks = []
    with open(chunk_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


# =============================================================================
# 1. English Regression Tests (Legitimate Null & Heading Extraction)
# =============================================================================

def test_english_keww1_ch2_legitimate_null_path(chunks_dir):
    """Verify that keww1 Ch 2 ('A Pair of Mustachios' prose story) preserves null path without inventing fake hierarchy."""
    chunks = _load_book_chunks(chunks_dir, "keww1")
    ch2_chunks = [c for c in chunks if str(c.get("chapter_number")) == "2"]
    assert len(ch2_chunks) > 0, "keww1 Ch 2 yielded no chunks"

    null_paths = [c for c in ch2_chunks if c.get("topic_subtopic_path") is None]
    assert len(null_paths) == len(ch2_chunks), (
        f"Expected all {len(ch2_chunks)} chunks in keww1 Ch 2 to have None topic_subtopic_path"
    )


def test_english_keww1_ch3_legitimate_null_path(chunks_dir):
    """Verify that keww1 Ch 3 ('The Rocking-horse Winner' story) preserves null path without inventing fake hierarchy."""
    chunks = _load_book_chunks(chunks_dir, "keww1")
    ch3_chunks = [c for c in chunks if str(c.get("chapter_number")) == "3"]
    assert len(ch3_chunks) > 0, "keww1 Ch 3 yielded no chunks"

    null_paths = [c for c in ch3_chunks if c.get("topic_subtopic_path") is None]
    assert len(null_paths) == len(ch3_chunks), (
        f"Expected all {len(ch3_chunks)} chunks in keww1 Ch 3 to have None topic_subtopic_path"
    )


def test_english_aemr1_ch1_subheadings_extracted(chunks_dir):
    """Verify that aemr1 Ch 1 sections with headings (e.g. Parts of the Body) extract non-null paths."""
    chunks = _load_book_chunks(chunks_dir, "aemr1")
    ch1_chunks = [c for c in chunks if str(c.get("chapter_number")) == "1"]
    assert len(ch1_chunks) > 0, "aemr1 Ch 1 yielded no chunks"

    with_path = [c for c in ch1_chunks if c.get("topic_subtopic_path")]
    assert len(with_path) > 0, "Expected aemr1 Ch 1 heading chunks to have non-null paths"
    sample_paths = " ".join([c["topic_subtopic_path"] for c in with_path])
    assert "Body" in sample_paths or "Hands" in sample_paths or "Alphabet" in sample_paths


# =============================================================================
# 2. Mathematics Regression Tests (Numbered Sections)
# =============================================================================

def test_math_lemh2_ch1_integrals_path_coverage(chunks_dir):
    """Verify that lemh2 Ch 1 (Integrals) extracts sections 7.1, 7.2 etc. and achieves >= 90% path coverage."""
    chunks = _load_book_chunks(chunks_dir, "lemh2")
    ch1_chunks = [c for c in chunks if str(c.get("chapter_number")) in ("1", "7")]
    assert len(ch1_chunks) > 0, "lemh2 Ch 1 yielded no chunks"

    with_path = [c for c in ch1_chunks if c.get("topic_subtopic_path")]
    coverage = len(with_path) / len(ch1_chunks)
    assert coverage >= 0.90, f"lemh2 Ch 1 path coverage {coverage:.2%} is below 90% threshold"

    # Verify key topics appear in topic paths
    sample_paths = " ".join([c["topic_subtopic_path"] for c in with_path])
    assert "Differentiation" in sample_paths or "Introduction" in sample_paths, (
        f"Expected key section titles in lemh2 Ch 1 paths, got: {sample_paths[:200]}"
    )


def test_math_kemh1_ch1_sets_path_coverage(chunks_dir):
    """Verify that kemh1 Ch 1 (Sets) achieves >= 80% path coverage."""
    chunks = _load_book_chunks(chunks_dir, "kemh1")
    ch1_chunks = [c for c in chunks if str(c.get("chapter_number")) == "1"]
    assert len(ch1_chunks) > 0, "kemh1 Ch 1 yielded no chunks"

    with_path = [c for c in ch1_chunks if c.get("topic_subtopic_path")]
    coverage = len(with_path) / len(ch1_chunks)
    assert coverage >= 0.80, f"kemh1 Ch 1 path coverage {coverage:.2%} is below 80% threshold"


# =============================================================================
# 3. Social Science Regression Tests (Unnumbered Sections)
# =============================================================================

def test_social_science_gees1_ch1_diversity_path_coverage(chunks_dir):
    """Verify that gees1 Ch 1 (Geographical Diversity) extracts unnumbered sections with >= 90% path coverage."""
    chunks = _load_book_chunks(chunks_dir, "gees1")
    ch1_chunks = [c for c in chunks if str(c.get("chapter_number")) == "1"]
    assert len(ch1_chunks) > 0, "gees1 Ch 1 yielded no chunks"

    with_path = [c for c in ch1_chunks if c.get("topic_subtopic_path")]
    coverage = len(with_path) / len(ch1_chunks)
    assert coverage >= 0.90, f"gees1 Ch 1 path coverage {coverage:.2%} is below 90% threshold"

    # Verify major geographic sections exist in chunk paths
    all_paths = [c["topic_subtopic_path"] for c in with_path]
    has_himalayas = any("Himalayas" in p for p in all_paths)
    assert has_himalayas, f"Expected 'The Himalayas' in gees1 Ch 1 chunk paths, got: {all_paths[:5]}"


def test_social_science_fees1_ch1_path_coverage(chunks_dir):
    """Verify that fees1 Ch 1 achieves >= 90% path coverage."""
    chunks = _load_book_chunks(chunks_dir, "fees1")
    ch1_chunks = [c for c in chunks if str(c.get("chapter_number")) == "1"]
    assert len(ch1_chunks) > 0, "fees1 Ch 1 yielded no chunks"

    with_path = [c for c in ch1_chunks if c.get("topic_subtopic_path")]
    coverage = len(with_path) / len(ch1_chunks)
    assert coverage >= 0.90, f"fees1 Ch 1 path coverage {coverage:.2%} is below 90% threshold"


# =============================================================================
# 4. Retrieval and Context Fallback Unit Tests
# =============================================================================

@pytest.mark.asyncio
async def test_retrieval_fallback_to_chapter_title_when_path_is_null():
    """Verify query_rag_service falls back to chapter_title in context prompt when topic_subtopic_path is null."""
    from app.src.modules.legacy_rag.service import query_rag_service

    mock_doc = {
        "chunk_id": "test_chunk_001",
        "book": "Woven Words Class 11",
        "chapter": "A Pair of Mustachios",
        "page_start": 4,
        "score": 0.88,
        "board": "NCERT",
        "class": 11,
        "subject": "english",
        "topic_subtopic_path": None,  # Legitimate null
        "text": "There are various kinds of mustachios in our land.",
    }

    with patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=[mock_doc]), \
         patch("app.src.modules.legacy_rag.service.vector_store.get_valid_subjects", return_value={"english"}), \
         patch("app.src.modules.legacy_rag.service.generate_response", new_callable=AsyncMock) as mock_gen:

        mock_gen.return_value = "This story is about prestige and mustachios."

        res = await query_rag_service(
            query="What is the story about?",
            subject="english",
            class_num=11,
        )

        assert res["sources"][0]["topic_subtopic_path"] is None
        # Verify context header passed to generate_response fell back to chapter
        call_kwargs = mock_gen.call_args.kwargs
        context = call_kwargs["context"]
        assert "[TOPIC]: A Pair of Mustachios" in context, f"Expected fallback [TOPIC]: A Pair of Mustachios, got:\n{context}"


@pytest.mark.asyncio
async def test_retrieval_preserves_topic_subtopic_path_when_present():
    """Verify query_rag_service includes topic_subtopic_path when present."""
    from app.src.modules.legacy_rag.service import query_rag_service

    mock_doc = {
        "chunk_id": "test_chunk_002",
        "book": "Exploring Society Class 7",
        "chapter": "Geographical Diversity of India",
        "page_start": 3,
        "score": 0.92,
        "board": "NCERT",
        "class": 7,
        "subject": "social-science",
        "topic_subtopic_path": "The Himalayas > The Himadri",
        "text": "The Himadri are the highest and most continuous range in the Himalayas.",
    }

    with patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=[mock_doc]), \
         patch("app.src.modules.legacy_rag.service.vector_store.get_valid_subjects", return_value={"social-science"}), \
         patch("app.src.modules.legacy_rag.service.generate_response", new_callable=AsyncMock) as mock_gen:

        mock_gen.return_value = "The Himadri is the highest Himalayan range."

        res = await query_rag_service(
            query="Which is the highest Himalayan range?",
            subject="social-science",
            class_num=7,
        )

        assert res["sources"][0]["topic_subtopic_path"] == "The Himalayas > The Himadri"
        call_kwargs = mock_gen.call_args.kwargs
        context = call_kwargs["context"]
        assert "[TOPIC]: The Himalayas > The Himadri" in context
