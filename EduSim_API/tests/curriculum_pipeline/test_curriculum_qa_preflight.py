"""
Tests for Curriculum Pipeline QA Reporter, Preflight, and Parallel Extraction (Step 4).
"""
import json
import pytest
from pathlib import Path

from curriculum_pipeline.preflight import analyze_pdf_text_quality
from curriculum_pipeline.qa_reporter import generate_qa_report
from curriculum_pipeline.page_extractor import PageExtractor
from curriculum_pipeline.pipeline_config import TEXTBOOKS_DIR, PIPELINE_OUTPUT_ROOT


def test_preflight_classification_standard_pdf():
    pdf_path = TEXTBOOKS_DIR / "ncert books" / "aejm101.pdf"
    if not pdf_path.exists():
        pytest.skip("aejm101.pdf not present in test environment")
    res = analyze_pdf_text_quality(pdf_path, expected_lang="en")
    assert res["classification"] == "ok"
    assert res["total_pages"] > 0
    assert res["pua_ratio"] == 0.0


def test_qa_reporter_generation(tmp_path):
    # Setup mock book in temp directory
    books_dir = tmp_path / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    mock_book = {
        "book_code": "mock1",
        "book_title": "Mock Book 1",
        "board": "ncert",
        "class": "10",
        "subject": "science",
        "total_pages": 40,
        "extraction_status": "ok",
        "chapters": [
            {
                "id": "mock1_ch_1",
                "level": "chapter",
                "official_number": "1",
                "official_title": "First Chapter",
                "page_start": 1,
                "page_end": 20,
                "nodes": [
                    {
                        "id": "mock1_topic_1",
                        "level": "topic",
                        "official_number": "1.1",
                        "official_title": "First Topic",
                        "page_start": 1,
                        "page_end": 10,
                        "nodes": [],
                    }
                ],
            }
        ],
    }

    with open(books_dir / "mock1.json", "w", encoding="utf-8") as f:
        json.dump(mock_book, f)

    out_md = tmp_path / "qa_report.md"
    out_json = tmp_path / "qa_report.json"

    summary = generate_qa_report(
        books_dir=books_dir,
        output_md_path=out_md,
        output_json_path=out_json,
    )

    assert summary["total_books_audited"] == 1
    assert summary["total_nodes_by_level"]["chapter"] == 1
    assert summary["total_nodes_by_level"]["topic"] == 1
    assert out_md.exists()
    assert out_json.exists()

    md_content = out_md.read_text(encoding="utf-8")
    assert "Mock Book 1" in md_content or "mock1" in md_content
    assert "Executive Summary" in md_content


def test_parallel_batch_extraction(tmp_path):
    ncert_dir = TEXTBOOKS_DIR / "ncert books"
    test_files = ["aejm101.pdf", "aemr101.pdf"]
    tasks = []
    for fn in test_files:
        p = ncert_dir / fn
        if not p.exists():
            pytest.skip(f"{fn} not present in test environment")
        tasks.append((p, fn))

    extractor = PageExtractor(pages_output_dir=tmp_path)
    results = extractor.extract_batch_parallel(tasks, workers=2, force=True)

    assert len(results) == 2
    for r in results:
        assert r["status"] == "extracted"
        assert r["pages_extracted"] > 0
        assert len(r["sha256"]) == 64
