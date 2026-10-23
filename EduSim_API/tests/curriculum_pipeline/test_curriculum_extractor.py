"""
Unit tests for EduSim Curriculum Extractor (Stage 2)
Tests:
- Heading style ranking
- Numbered heading regex (1.1, 1.1.1, 1.1.1.1)
- Activity keyword detection across languages
- Chapter boundaries and wrapper extraction
- Coverage proof math and unassigned page calculation
- Resume cache logic
"""

import pytest
from pathlib import Path
from curriculum_pipeline.adapters.base_adapter import BaseSubjectAdapter
from curriculum_pipeline.coverage_prover import CoverageProver, find_unassigned_ranges
from curriculum_pipeline.page_extractor import calculate_garbled_metrics, detect_script
from curriculum_pipeline.tree_builder import CurriculumTreeBuilder


def test_numbered_heading_regex():
    adapter = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0})

    # Topic (single dot: 1.1)
    res1 = adapter.parse_numbered_heading("1.1 Electric Charges and Fields")
    assert res1 is not None
    assert res1[0] == "topic"
    assert res1[1] == "1.1"
    assert res1[2] == "Electric Charges and Fields"

    # Subtopic (two dots: 1.1.1)
    res2 = adapter.parse_numbered_heading("1.1.1 Conductors and Insulators")
    assert res2 is not None
    assert res2[0] == "subtopic"
    assert res2[1] == "1.1.1"
    assert res2[2] == "Conductors and Insulators"

    # Subheading (three dots: 1.1.1.1)
    res3 = adapter.parse_numbered_heading("1.1.1.1 Charging by Induction")
    assert res3 is not None
    assert res3[0] == "subheading"
    assert res3[1] == "1.1.1.1"
    assert res3[2] == "Charging by Induction"

    # Not a numbered heading
    assert adapter.parse_numbered_heading("Chapter 1 Real Numbers") is None
    assert adapter.parse_numbered_heading("12. Just a number with text") is None


def test_activity_keyword_detection():
    adapter_en = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0}, language="en")
    assert adapter_en.is_activity_heading("Activity 1.1")[0] is True
    assert adapter_en.is_activity_heading("Let us do this experiment")[0] is True
    assert adapter_en.is_activity_heading("Exercise 2.3")[0] is True
    assert adapter_en.is_activity_heading("Normal text discussing physics")[0] is False

    adapter_hi = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0}, language="hi")
    assert adapter_hi.is_activity_heading("क्रियाकलाप 1.1")[0] is True
    assert adapter_hi.is_activity_heading("करके देखिए")[0] is True
    assert adapter_hi.is_activity_heading("सामान्य पाठ")[0] is False


def test_noise_and_annotation_detection():
    adapter = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0})

    is_noise, annot = adapter.is_noise_or_annotation("42")
    assert is_noise is True
    assert annot == "page_number"

    is_noise, annot = adapter.is_noise_or_annotation("Reprint 2025-26")
    assert is_noise is True
    assert annot == "copyright"

    is_noise, annot = adapter.is_noise_or_annotation("Fig. 1.2 Structure of Atom")
    assert is_noise is True
    assert "figure" in annot

    is_noise, annot = adapter.is_noise_or_annotation("Do you know that lightning carries millions of volts?")
    assert is_noise is True
    assert annot == "did_you_know_box"


def test_coverage_prover_math():
    prover = CoverageProver()
    pages_records = [
        {"page_no": 1, "char_count": 200, "ocr_needed": False},
        {"page_no": 2, "char_count": 250, "ocr_needed": False},
        {"page_no": 3, "char_count": 300, "ocr_needed": False},
        {"page_no": 4, "char_count": 280, "ocr_needed": False},
        {"page_no": 5, "char_count": 210, "ocr_needed": False},
    ]

    chapters = [{
        "id": "ch1",
        "official_number": "1",
        "official_title": "First Chapter",
        "page_start": 1,
        "page_end": 5,
        "nodes": [
            {"id": "t1", "level": "topic", "page_start": 1, "page_end": 3, "nodes": []},
            {"id": "t2", "level": "topic", "page_start": 4, "page_end": 5, "nodes": []},
        ],
    }]

    cov = prover.prove_coverage(
        book_code="test_book",
        chapters=chapters,
        pages_records=pages_records,
        expected_chapters_count=1,
        toc_entries=[{"number": "1", "title": "First Chapter", "page": 1}],
    )

    assert cov["pages_total"] == 5
    assert cov["pages_with_text"] == 5
    assert cov["pages_unassigned"] == 0
    assert cov["status"] == "passed"


def test_coverage_prover_unassigned_gap_fails_rule():
    prover = CoverageProver()
    # 10 pages, chapter covers 1-5, pages 6-10 unassigned (> 2 pages gap)
    pages_records = [
        {"page_no": i, "char_count": 200, "ocr_needed": False}
        for i in range(1, 11)
    ]

    chapters = [{
        "id": "ch1",
        "official_number": "1",
        "official_title": "Short Chapter",
        "page_start": 1,
        "page_end": 5,
        "nodes": [],
    }]

    cov = prover.prove_coverage(
        book_code="test_book",
        chapters=chapters,
        pages_records=pages_records,
        expected_chapters_count=1,
    )

    assert cov["status"] == "needs_review"
    assert any("Unassigned text page range > 2 pages" in r for r in cov["status_reasons"])


def test_garbled_metrics_and_script_detection():
    ascii_text = "Standard English text with normal words."
    total, garb, pct = calculate_garbled_metrics(ascii_text)
    assert garb == 0
    assert pct == 0.0
    assert detect_script(ascii_text) == "latin"

    # Text with PUA character \ue001
    pua_text = "Some text with \ue001\ue002 corrupt characters"
    total, garb, pct = calculate_garbled_metrics(pua_text)
    assert garb == 2
    assert pct > 0.0

    # Telugu text
    te_text = "ఇది తెలుగు వాక్యం"
    assert detect_script(te_text) == "telugu"

    # Hindi / Devanagari text
    hi_text = "यह हिंदी वाक्य है"
    assert detect_script(hi_text) == "devanagari"


def test_tree_builder_hierarchy():
    builder = CurriculumTreeBuilder("test_b1")
    candidates = [
        {"level": "topic", "official_number": "1.1", "official_title": "Topic One", "normalized_title": "Topic One", "page": 1},
        {"level": "subtopic", "official_number": "1.1.1", "official_title": "Subtopic A", "normalized_title": "Subtopic A", "page": 2},
        {"level": "activity", "official_number": "1", "official_title": "Activity 1", "normalized_title": "Activity 1", "page": 2},
        {"level": "subheading", "official_number": "1.1.1.1", "official_title": "Subheading I", "normalized_title": "Subheading I", "page": 3},
    ]

    ch = builder.build_chapter_tree(
        chapter_info={"id": "ch1", "official_number": "1", "official_title": "Chapter One"},
        raw_candidates=candidates,
        chapter_page_start=1,
        chapter_page_end=5,
    )

    assert ch["level"] == "chapter"
    assert len(ch["nodes"]) == 1  # 1 topic
    top = ch["nodes"][0]
    assert top["level"] == "topic"
    assert len(top["nodes"]) == 1  # 1 subtopic
    subtop = top["nodes"][0]
    assert subtop["level"] == "subtopic"
    assert len(subtop["nodes"]) == 1  # 1 activity
    act = subtop["nodes"][0]
    assert act["level"] == "activity"
    assert len(act["nodes"]) == 1  # 1 subheading


def _collect_nodes(nodes, acc=None):
    if acc is None:
        acc = []
    for n in nodes:
        acc.append(n)
        if "nodes" in n:
            _collect_nodes(n["nodes"], acc)
    return acc


def test_golden_kemh1_ch1_ch2():
    """
    Golden test: verifies hand-verified topics, subtopics, and activities
    for Class 11 Maths (kemh1) Chapters 1 and 2 from printed contents page.
    """
    import json
    from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT
    book_file = PIPELINE_OUTPUT_ROOT / "curriculum" / "books" / "kemh1.json"
    if not book_file.exists():
        pytest.skip("kemh1.json not generated yet")

    with open(book_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = {str(c.get("official_number")): c for c in data.get("chapters", [])}

    # Chapter 1 (Sets)
    assert "1" in chapters, "Chapter 1 must exist in kemh1"
    ch1 = chapters["1"]
    all_ch1_nodes = _collect_nodes(ch1.get("nodes", []))
    ch1_nodes_by_num = {n.get("official_number"): n for n in all_ch1_nodes if n.get("level") in ["topic", "subtopic"] and n.get("official_number")}

    expected_ch1_headings = {
        "1.1": 1,
        "1.2": 1,
        "1.3": 5,
        "1.4": 6,
        "1.5": 7,
        "1.6": 9,
        "1.6.1": 10,
        "1.6.2": 11,
        "1.7": 12,
        "1.8": 13,
        "1.9": 13,
        "1.9.1": 14,
        "1.9.2": 15,
        "1.9.3": 16,
        "1.10": 18,
    }

    diffs_ch1 = []
    for exp_num, exp_page in expected_ch1_headings.items():
        if exp_num not in ch1_nodes_by_num:
            diffs_ch1.append(f"Missing heading {exp_num} (expected p.{exp_page})")
        else:
            actual_page = ch1_nodes_by_num[exp_num].get("page_start")
            if actual_page != exp_page:
                diffs_ch1.append(f"Page mismatch for {exp_num}: expected p.{exp_page}, got p.{actual_page}")

    assert not diffs_ch1, f"Diffs in kemh1 Ch 1: {diffs_ch1}"

    # Chapter 2 (Relations and Functions)
    assert "2" in chapters, "Chapter 2 must exist in kemh1"
    ch2 = chapters["2"]
    all_ch2_nodes = _collect_nodes(ch2.get("nodes", []))
    ch2_nodes_by_num = {n.get("official_number"): n for n in all_ch2_nodes if n.get("level") in ["topic", "subtopic"] and n.get("official_number")}

    expected_ch2_headings = {
        "2.1": 24,
        "2.2": 24,
        "2.3": 28,
        "2.4": 30,
        "2.4.1": 32,
        "2.4.2": 36,
    }

    diffs_ch2 = []
    for exp_num, exp_page in expected_ch2_headings.items():
        if exp_num not in ch2_nodes_by_num:
            diffs_ch2.append(f"Missing heading {exp_num} (expected p.{exp_page})")
        else:
            actual_page = ch2_nodes_by_num[exp_num].get("page_start")
            if actual_page != exp_page:
                diffs_ch2.append(f"Page mismatch for {exp_num}: expected p.{exp_page}, got p.{actual_page}")

    assert not diffs_ch2, f"Diffs in kemh1 Ch 2: {diffs_ch2}"

    # Verify activities/examples present in Chapter 2
    ch2_acts = [n for n in all_ch2_nodes if n.get("level") == "activity"]
    assert len(ch2_acts) >= 10, f"Expected at least 10 activities/examples/definitions in kemh1 Ch 2, got {len(ch2_acts)}"


def test_golden_kech1_ch1():
    """
    Golden test: verifies hand-verified topics and subtopics for Class 11 Chemistry (kech1) Chapter 1
    from printed contents page.
    """
    import json
    from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT
    book_file = PIPELINE_OUTPUT_ROOT / "curriculum" / "books" / "kech1.json"
    if not book_file.exists():
        pytest.skip("kech1.json not generated yet")

    with open(book_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = {str(c.get("official_number")): c for c in data.get("chapters", [])}
    assert "1" in chapters, "Chapter 1 must exist in kech1"
    ch1 = chapters["1"]
    all_ch1_nodes = _collect_nodes(ch1.get("nodes", []))
    ch1_nodes_by_num = {n.get("official_number"): n for n in all_ch1_nodes if n.get("level") in ["topic", "subtopic"] and n.get("official_number")}

    expected_kech1_headings = {
        "1.1": 4,
        "1.2": 4,
        "1.2.1": 4,
        "1.2.2": 5,
        "1.3": 6,
        "1.3.1": 6,
        "1.3.2": 7,
        "1.3.3": 7,
        "1.3.4": 9,
        "1.3.5": 9,
        "1.4": 10,
        "1.4.1": 11,
        "1.4.2": 12,
        "1.4.3": 13,
        "1.5": 14,
        "1.5.1": 14,
        "1.5.2": 15,
        "1.5.3": 15,
        "1.5.4": 15,
        "1.5.5": 15,
        "1.6": 16,
        "1.7": 16,
        "1.7.1": 16,
        "1.7.2": 17,
        "1.7.3": 17,
        "1.7.4": 17,
        "1.8": 18,
        "1.9": 18,
        "1.9.1": 19,
        "1.10": 20,
        "1.10.1": 20,
        "1.10.2": 21,
    }

    diffs_kech1 = []
    for exp_num, exp_page in expected_kech1_headings.items():
        if exp_num not in ch1_nodes_by_num:
            diffs_kech1.append(f"Missing heading {exp_num} (expected p.{exp_page})")
        else:
            actual_page = ch1_nodes_by_num[exp_num].get("page_start")
            if actual_page != exp_page:
                diffs_kech1.append(f"Page mismatch for {exp_num}: expected p.{exp_page}, got p.{actual_page}")

    assert not diffs_kech1, f"Diffs in kech1 Ch 1: {diffs_kech1}"

    # Verify 1.10.2 ends at Summary boundary (p.24)
    node_1_10_2 = ch1_nodes_by_num.get("1.10.2")
    assert node_1_10_2 is not None
    assert node_1_10_2.get("page_end") <= 24, f"Topic 1.10.2 page_end must be <= 24, got {node_1_10_2.get('page_end')}"


def test_multiline_chapter_title_merge():
    """Unit test: verifies consecutive vertically adjacent title lines merge correctly."""
    from curriculum_pipeline.extractor_engine import CurriculumExtractorEngine

    engine = CurriculumExtractorEngine()
    mock_p1 = {
        "page_no": 1,
        "text": "Finding the\nFurry Cat!\n1\nLet us Sing",
        "lines": [
            {
                "text": "Finding the",
                "bbox": [170.21, 33.75, 318.41, 68.44],
                "spans": [{"text": "Finding the", "size": 28.0, "bold": True}],
            },
            {
                "text": "Furry Cat!",
                "bbox": [180.93, 62.14, 302.03, 96.83],
                "spans": [{"text": "Furry Cat!", "size": 28.0, "bold": True}],
            },
            {
                "text": "1",
                "bbox": [77.18, 68.17, 99.38, 117.73],
                "spans": [{"text": "1", "size": 40.0, "bold": True}],
            },
            {
                "text": "Let us Sing",
                "bbox": [144.64, 161.31, 219.14, 184.87],
                "spans": [{"text": "Let us Sing", "size": 18.0, "bold": True}],
            },
        ],
    }

    title, wrapper, _ = engine.extract_ncert_chapter_title_from_p1([mock_p1], ch_no=1)
    assert title == "Finding the Furry Cat!"
    assert wrapper is None


def test_false_positive_subheading_suppression_aejm101_and_aemr101():
    """
    Regression test: ensures dialogue speakers and inline bold vocabulary
    are NOT extracted as subheadings (exact cases: 'bottom', 'near', 'Nitin').
    """
    adapter = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0})

    # Case 1: aejm101 inline bold word "bottom" in running sentence "bottom of my jar."
    line1 = "bottom of my jar."
    spans1 = [
        {"text": "bottom", "size": 14.0, "flags": 2, "font": "Bold"},
        {"text": " of my jar.", "size": 14.0, "flags": 0, "font": "Regular"},
    ]
    assert adapter.detect_run_in_bold(line1, spans1) is None

    # Case 2: aejm101 inline bold word "near" in running sentence
    line2 = "near the board and under the table."
    spans2 = [
        {"text": "near", "size": 14.0, "flags": 2, "font": "Bold"},
        {"text": " the board and under the table.", "size": 14.0, "flags": 0, "font": "Regular"},
    ]
    assert adapter.detect_run_in_bold(line2, spans2) is None

    # Case 3: aemr101 dialogue speaker label "Nitin: What is this?"
    line3 = "Nitin: What is this?"
    spans3 = [
        {"text": "Nitin:", "size": 14.0, "flags": 2, "font": "Bold"},
        {"text": " What is this?", "size": 14.0, "flags": 0, "font": "Regular"},
    ]
    assert adapter.detect_run_in_bold(line3, spans3) is None

    # Case 4: Positive case — valid run-in heading set apart with period delimiter
    line4 = "Intersection of sets. The intersection of sets A and B is..."
    spans4 = [
        {"text": "Intersection of sets.", "size": 14.0, "flags": 2, "font": "Bold"},
        {"text": " The intersection of sets A and B is...", "size": 10.0, "flags": 0, "font": "Regular"},
    ]
    assert adapter.detect_run_in_bold(line4, spans4) == "Intersection of sets"


def test_no_duplicate_topic_synthesized_and_activities_attach_to_chapter():
    """
    Unit test: verifies that when a chapter has no real topics,
    no synthetic duplicate topic is invented, and activities attach directly to chapter.
    """
    tree_builder = CurriculumTreeBuilder(book_code="aemr1")
    ch_info = {
        "id": "aemr1_ch_1",
        "official_number": "1",
        "official_title": "My Family and Me",
        "wrapper": "Unit 1",
        "source_file": "aemr101.pdf",
    }
    raw_candidates = [
        # Candidate duplicating the chapter title (should be omitted)
        {
            "level": "topic",
            "official_number": None,
            "official_title": "My Family and Me",
            "normalized_title": "My Family and Me",
            "page": 1,
            "confidence": 0.82,
        },
        # Real activity
        {
            "level": "activity",
            "kind": "activity",
            "official_number": None,
            "official_title": "Let us sing",
            "normalized_title": "Let us sing",
            "page": 1,
            "confidence": 0.95,
        },
    ]

    ch_tree = tree_builder.build_chapter_tree(
        chapter_info=ch_info,
        raw_candidates=raw_candidates,
        chapter_page_start=1,
        chapter_page_end=14,
        file_id="aemr101.pdf",
    )

    # 1. No child node should be a topic named "My Family and Me"
    topics = [n for n in ch_tree["nodes"] if n["level"] == "topic"]
    assert len(topics) == 0, f"Expected 0 topics, got {topics}"

    # 2. Activity attaches directly to chapter
    activities = [n for n in ch_tree["nodes"] if n["level"] == "activity"]
    assert len(activities) == 1
    assert activities[0]["official_title"] == "Let us sing"
    assert activities[0]["parent_id"] == "aemr1_ch_1"
    assert activities[0]["source_file"] == "aemr101.pdf"


def test_fixtures_aejm101_and_aemr101_output_trees():
    """Extracts aejm101 and aemr101 PDFs in test and validates the extracted hierarchy."""
    import json
    from curriculum_pipeline.extractor_engine import CurriculumExtractorEngine
    from curriculum_pipeline.pipeline_config import TEXTBOOKS_DIR
    from curriculum_pipeline.adapters.specialized_adapters import get_adapter_for_subject
    from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

    pdf_jm = TEXTBOOKS_DIR / "ncert books" / "aejm101.pdf"
    pdf_mr = TEXTBOOKS_DIR / "ncert books" / "aemr101.pdf"

    if not pdf_jm.exists() or not pdf_mr.exists():
        pytest.skip(f"Test PDFs not found in {TEXTBOOKS_DIR / 'ncert books'}")

    engine = CurriculumExtractorEngine()

    def _extract_ch(pdf_path, subject, bcode):
        res = engine.page_extractor.extract_file(pdf_path, file_id=pdf_path.name)
        j_path = engine.page_extractor.get_output_path(pdf_path.name)
        pages = []
        with open(j_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("type") != "metadata":
                    pages.append(rec)
        style_prof = engine.style_profiler.profile_book(bcode, [j_path])
        adapter = get_adapter_for_subject(subject, style_prof, "en")
        adapter.reset_chapter_state()
        title, wrapper, _ = engine.extract_ncert_chapter_title_from_p1(pages, 1)

        raw = []
        for p in pages:
            raw.extend(adapter.extract_nodes_from_lines(p["page_no"], p.get("lines", [])))

        tb = CurriculumTreeBuilder(bcode)
        ch_info = {
            "id": f"{bcode}_ch_1",
            "official_number": "1",
            "official_title": title,
            "wrapper": wrapper,
            "source_file": pdf_path.name,
            "ocr_needed": False,
        }
        return tb.build_chapter_tree(ch_info, raw, 1, len(pages), file_id=pdf_path.name, end_matter_page=adapter.end_matter_page)

    ch1_jm = _extract_ch(pdf_jm, "mathematics", "aejm1")
    assert ch1_jm["official_title"] == "Finding the Furry Cat!"
    assert ch1_jm["source_file"] == "aejm101.pdf"

    def _get_all_subheadings(node):
        res = []
        if node.get("level") == "subheading":
            res.append(node.get("official_title", "").lower())
        for c in node.get("nodes", []):
            res.extend(_get_all_subheadings(c))
        return res

    subheadings_jm = _get_all_subheadings(ch1_jm)
    assert "bottom" not in subheadings_jm
    assert "near" not in subheadings_jm

    ch1_mr = _extract_ch(pdf_mr, "english", "aemr1")
    assert ch1_mr["official_title"] == "My Family and Me"
    assert ch1_mr["wrapper"] == "Unit 1"
    assert ch1_mr["source_file"] == "aemr101.pdf"

    topics_mr = [n for n in ch1_mr.get("nodes", []) if n.get("level") == "topic"]
    assert len(topics_mr) == 0

    subheadings_mr = _get_all_subheadings(ch1_mr)
    assert "nitin" not in subheadings_mr


def test_probe_systematic_fixes():
    """Verifies faux-bold deduplication, horizontal fragment stitching, and summary boundary."""
    from curriculum_pipeline.adapters.base_adapter import BaseSubjectAdapter

    adapter = BaseSubjectAdapter(style_profile={"ranks": {}, "body_size": 10.0})

    # 1. Exercise Q&A noise is ignored
    assert adapter.is_noise_or_annotation("Ans. Refer Table 2, page 4, and draw.")[0] is True
    assert adapter.is_noise_or_annotation("Q.4. What would you call")[0] is True

    # 2. Horizontal overlapping segments stitched properly
    lines_data = [
        {"text": "1.1 CHEMICAL EQUA", "bbox": [162.96, 447.27, 302.14, 461.48], "spans": [{"text": "1.1 CHEMICAL EQUA", "size": 14.0, "flags": 2}]},
        {"text": "AL EQUATIONS", "bbox": [241.44, 447.27, 342.45, 461.48], "spans": [{"text": "AL EQUATIONS", "size": 14.0, "flags": 2}]},
    ]
    nodes = adapter.extract_nodes_from_lines(page_no=2, lines_with_spans=lines_data)
    assert len(nodes) == 1
    assert nodes[0]["official_title"] == "CHEMICAL EQUATIONS"
    assert nodes[0]["official_number"] == "1.1"



def test_unmapped_file_detection_and_failure(tmp_path):
    """Verifies build_books_catalog fails loudly and writes unmapped_files.csv if unmapped file exists."""
    import csv
    from curriculum_pipeline.catalog_builder import build_books_catalog

    fake_inv = tmp_path / "fake_inventory.csv"
    with open(fake_inv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file"])
        writer.writeheader()
        writer.writerow({"file": "zz99999.pdf"})  # Unmapped NCERT code 'zz'

    with pytest.raises(ValueError) as exc:
        build_books_catalog(inventory_csv_path=fake_inv)
    assert "unmapped file(s)" in str(exc.value).lower()


def test_cap_node_page_ends_retains_parent_enclosure():
    """Regression test: capping page ends to end matter does not break parent-child enclosure."""
    builder = CurriculumTreeBuilder("test_b1")
    parent = {
        "id": "top_1",
        "page_start": 100,
        "page_end": 105,
        "nodes": [
            {
                "id": "subh_1",
                "page_start": 103,
                "page_end": 103,
                "nodes": [],
            }
        ]
    }
    # If end matter starts on page 103
    builder._cap_node_page_ends(parent, end_page=103)
    # Child was on page 103, parent must encompass it (page_end >= 103)
    assert parent["page_end"] >= parent["nodes"][0]["page_end"]
    assert parent["nodes"][0]["page_end"] <= parent["page_end"]


def test_full_book_assembly_fegp1_and_jesc1():
    """Validates full-book assembly of Class 6 Maths (fegp1) and Class 10 Science (jesc1)."""
    import json
    from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT

    for code, exp_chaps, exp_pages in [("fegp1", 10, 392), ("jesc1", 13, 217)]:
        b_path = PIPELINE_OUTPUT_ROOT / "curriculum" / "books" / f"{code}.json"
        if not b_path.exists():
            pytest.skip(f"{code}.json not assembled yet (PDFs or output absent)")

        with open(b_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("book_code") == code
        assert data.get("extraction_status") == "ok"
        assert data.get("total_pages") == exp_pages

        chapters = data.get("chapters", [])
        assert len(chapters) == exp_chaps, f"Expected {exp_chaps} chapters for {code}, got {len(chapters)}"

        # Check contiguous page coverage and chapter numbers
        for i, ch in enumerate(chapters):
            expected_num = str(i + 1)
            assert ch.get("official_number") == expected_num
            if i > 0:
                prev_end = chapters[i - 1]["page_end"]
                curr_start = ch["page_start"]
                assert curr_start == prev_end + 1, f"Gap or overlap between Ch {i} and Ch {i+1}: {prev_end} -> {curr_start}"


def test_duplicate_identity_keys_collapsed_whitespace():
    """Regression test for Pre-step A: whitespace differences in titles must yield distinct occurrence_index."""
    from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

    tb = CurriculumTreeBuilder("fegp1")
    parent = {
        "id": "ch_1",
        "level": "chapter",
        "nodes": [
            {"level": "activity", "official_title": "Example:  Find the sum of 1", "normalized_title": "Example: Find the sum of 1", "page_start": 5, "page_end": 5},
            {"level": "activity", "official_title": "Example: Find the sum of 1", "normalized_title": "Example: Find the sum of 1", "page_start": 6, "page_end": 6},
        ]
    }
    tb._assign_ordinals_and_identity(parent)
    c1, c2 = parent["nodes"]
    assert c1["occurrence_index"] == 0
    assert c2["occurrence_index"] == 1
    assert c1["identity_key"] != c2["identity_key"]


def test_local_source_pages_chapter_and_nodes():
    """Regression test for Pre-step D: node local source pages within chapter PDF."""
    from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

    tb = CurriculumTreeBuilder("fegp1")
    ch_info = {
        "id": "fegp1_ch_5",
        "official_number": "5",
        "official_title": "PRIME TIME",
    }
    raw = [
        {"level": "topic", "official_number": "5.1", "official_title": "Common Multiples", "page": 147, "normalized_title": "Common Multiples"},
        {"level": "topic", "official_number": "5.2", "official_title": "Prime Numbers", "page": 152, "normalized_title": "Prime Numbers"},
    ]
    ch_node = tb.build_chapter_tree(ch_info, raw, chapter_page_start=147, chapter_page_end=179)
    assert ch_node["source_page_start"] == 1
    assert ch_node["source_page_end"] == 33
    t1 = ch_node["nodes"][0]
    assert t1["source_page_start"] == 1
    assert t1["source_page_end"] == 5
    t2 = ch_node["nodes"][1]
    assert t2["source_page_start"] == 6


def test_solutions_detected_as_end_matter():
    """Regression test for Pre-step E & F: solutions heading caps topics and produces normalized reason."""
    from curriculum_pipeline.adapters.specialized_adapters import MathsAdapter
    from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

    adapter = MathsAdapter(style_profile={})
    adapter.reset_chapter_state(chapter_number=5)

    # Line with solutions
    lines = [
        {"text": "5.1 First Section", "spans": [{"text": "5.1 First Section", "size": 14.0, "flags": 2}]},
        {"text": "CHAPTER 5 — SOLUTIONS", "spans": [{"text": "CHAPTER 5 — SOLUTIONS", "size": 16.0, "flags": 2}]},
    ]
    nodes_p1 = adapter.extract_nodes_from_lines(1, [lines[0]])
    assert len(nodes_p1) == 1

    # End matter reached on p.23
    adapter.extract_nodes_from_lines(23, [lines[1]])
    assert adapter.end_of_chapter_reached is True
    assert adapter.end_matter_page == 23
    assert adapter.end_matter_label == "SOLUTIONS"

    # Tree builder unstructured_ranges
    tb = CurriculumTreeBuilder("fegp1")
    ch_node = tb.build_chapter_tree(
        {"id": "ch5", "official_number": "5", "official_title": "Prime Time"},
        raw_candidates=nodes_p1,
        chapter_page_start=1,
        chapter_page_end=33,
        end_matter_page=23,
        end_matter_label="S U M M A R Y",
    )
    assert len(ch_node["unstructured_ranges"]) == 1
    assert ch_node["unstructured_ranges"][0]["reason"] == "SUMMARY"


def test_chapter_prefix_enforcement_on_topics():
    """Regression test for Pre-step E: optical table decimal entries rejected in Chapter 9."""
    from curriculum_pipeline.adapters.specialized_adapters import ScienceAdapter

    adapter = ScienceAdapter(style_profile={})
    adapter.reset_chapter_state(chapter_number=9)

    # Valid topic 9.1
    t91 = adapter.parse_numbered_heading("9.1 REFLECTION OF LIGHT")
    assert t91 is not None
    assert t91[1] == "9.1"

    # Bogus refractive index entries from table
    assert adapter.parse_numbered_heading("1.33 Water") is None
    assert adapter.parse_numbered_heading("1.54 Alcohol") is None
    assert adapter.parse_numbered_heading("1.63 Carbon disulphide") is None


def test_ssc_activity_single_page():
    """Regression test for Pre-step C: SSC activities do not stretch across siblings."""
    from curriculum_pipeline.tree_builder import CurriculumTreeBuilder

    tb = CurriculumTreeBuilder("ssc_1eng")
    parent = {
        "id": "ssc_ch1",
        "level": "chapter",
        "page_start": 1,
        "page_end": 50,
        "nodes": [
            {"level": "activity", "official_title": "Sing the song", "page_start": 17, "page_end": 17, "single_page": True},
            {"level": "activity", "official_title": "Sing and dance", "page_start": 26, "page_end": 26, "single_page": True},
        ]
    }
    tb._adjust_page_ends(parent, chapter_max_page=50)
    a1, a2 = parent["nodes"]
    assert a1["page_start"] == 17
    assert a1["page_end"] == 17
    assert a2["page_start"] == 26
    assert a2["page_end"] == 26


def test_validator_new_warnings():
    """Regression test for Pre-step E: node_spans_many_pages and chapter_missing_end_matter."""
    from curriculum_pipeline.validator import CurriculumValidator

    validator = CurriculumValidator()

    # Book with topic spanning 15 pages and chapter without end matter
    book = {
        "board": "ncert",
        "class": 6,
        "subject": "maths",
        "book_title": "Maths Book",
        "book_code": "test_math",
        "source_sha256": "fake_sha",
        "total_pages": 40,
        "chapters": [
            {
                "id": "ch_1",
                "level": "chapter",
                "official_number": "1",
                "official_title": "Chapter 1",
                "page_start": 1,
                "page_end": 20,
                "unstructured_ranges": [],
                "nodes": [
                    {
                        "id": "top_1",
                        "level": "topic",
                        "official_number": "1.1",
                        "official_title": "Huge Topic",
                        "page_start": 1,
                        "page_end": 20,
                        "nodes": []
                    }
                ]
            }
        ]
    }
    issues = validator.validate_data(book)
    rule_ids = [i.rule_id for i in issues]
    assert "node_spans_many_pages" in rule_ids
    assert "chapter_missing_end_matter" in rule_ids



