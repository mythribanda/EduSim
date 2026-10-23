"""
Unit tests for curriculum hierarchy validator (Step 2).
Covers:
  - Empty or whitespace title (pass & fail)
  - Invalid parent-to-child level nesting (pass & fail)
  - Child page range outside parent range (pass & fail)
  - Sibling page order violated (pass & fail)
  - Missing source_file or invalid page numbers (pass & fail)
  - Duplicate sibling titles at Topic/Subtopic levels (pass & fail)
  - Explicit test: Repeated Activity titles PASS validation
  - Explicit test: Siblings sharing a boundary page PASS validation
  - Warnings: title over 100 chars, chapter with 0 activities, excessive subheadings, ocr_needed
"""

import pytest
from curriculum_pipeline.validator import CurriculumValidator


@pytest.fixture
def validator():
    return CurriculumValidator()


def create_base_chapter(**overrides):
    base = {
        "id": "ch_1",
        "level": "chapter",
        "official_number": "1",
        "official_title": "Chapter One",
        "page_start": 1,
        "page_end": 20,
        "source_file": "test_ch1.pdf",
        "ocr_needed": False,
        "nodes": [
            {
                "id": "act_default",
                "level": "activity",
                "official_title": "Default Activity",
                "page_start": 2,
                "page_end": 3,
                "source_file": "test_ch1.pdf",
                "ocr_needed": False,
                "nodes": [],
            }
        ],
    }
    base.update(overrides)
    return base


# ── Rule 1: Empty or whitespace title ─────────────────────────


def test_rule_empty_title_pass(validator):
    data = create_base_chapter(official_title="A Valid Title")
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 0


def test_rule_empty_title_fail(validator):
    data = create_base_chapter(official_title="   ")
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "empty_title"]
    assert len(errors) >= 1
    assert errors[0].severity == "ERROR"


# ── Rule 2: Missing source_file or invalid page numbers ───────


def test_rule_source_file_and_pages_pass(validator):
    data = create_base_chapter()
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 0


def test_rule_missing_source_file_fail(validator):
    data = create_base_chapter(source_file="")
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "missing_source_file"]
    assert len(errors) >= 1


def test_rule_invalid_page_range_fail(validator):
    data = create_base_chapter(page_start=15, page_end=5)
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "invalid_page_end"]
    assert len(errors) >= 1


# ── Rule 3: Invalid parent-to-child level nesting ─────────────


def test_rule_level_nesting_pass(validator):
    # Valid nesting: chapter -> topic -> subtopic -> activity -> subheading
    data = create_base_chapter(
        nodes=[
            {
                "id": "top_1",
                "level": "topic",
                "official_title": "Topic 1",
                "page_start": 2,
                "page_end": 10,
                "source_file": "test.pdf",
                "nodes": [
                    {
                        "id": "sub_1",
                        "level": "subtopic",
                        "official_title": "Subtopic 1",
                        "page_start": 3,
                        "page_end": 6,
                        "source_file": "test.pdf",
                        "nodes": [
                            {
                                "id": "act_1",
                                "level": "activity",
                                "official_title": "Activity 1",
                                "page_start": 4,
                                "page_end": 5,
                                "source_file": "test.pdf",
                                "nodes": [
                                    {
                                        "id": "subh_1",
                                        "level": "subheading",
                                        "official_title": "Subheading 1",
                                        "page_start": 4,
                                        "page_end": 4,
                                        "source_file": "test.pdf",
                                        "nodes": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    )
    issues = validator.validate_data(data)
    nesting_errors = [i for i in issues if i.rule_id == "invalid_level_nesting"]
    assert len(nesting_errors) == 0


def test_rule_level_nesting_inversion_fail(validator):
    # Inversion: subtopic placed directly with a topic child
    data = create_base_chapter(
        nodes=[
            {
                "id": "sub_1",
                "level": "subtopic",
                "official_title": "Subtopic 1",
                "page_start": 2,
                "page_end": 10,
                "source_file": "test.pdf",
                "nodes": [
                    {
                        "id": "top_inverted",
                        "level": "topic",
                        "official_title": "Inverted Topic Child",
                        "page_start": 3,
                        "page_end": 5,
                        "source_file": "test.pdf",
                        "nodes": [],
                    }
                ],
            }
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "invalid_level_nesting"]
    assert len(errors) == 1
    assert "cannot be placed under parent level 'subtopic'" in errors[0].message


# ── Rule 4: Child page range outside parent range ─────────────


def test_rule_child_page_inside_parent_pass(validator):
    data = create_base_chapter(
        page_start=1,
        page_end=20,
        nodes=[
            {
                "id": "act_1",
                "level": "activity",
                "official_title": "Act 1",
                "page_start": 2,
                "page_end": 18,
                "source_file": "test.pdf",
                "nodes": [],
            }
        ],
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "child_page_outside_parent"]
    assert len(errors) == 0


def test_rule_child_page_outside_parent_fail(validator):
    data = create_base_chapter(
        page_start=5,
        page_end=15,
        nodes=[
            {
                "id": "act_out",
                "level": "activity",
                "official_title": "Act Outside",
                "page_start": 3,  # earlier than parent page_start=5
                "page_end": 18,  # later than parent page_end=15
                "source_file": "test.pdf",
                "nodes": [],
            }
        ],
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "child_page_outside_parent"]
    assert len(errors) >= 1


# ── Rule 5: Sibling page order violated & shared boundary page ─


def test_rule_sibling_page_order_pass(validator):
    data = create_base_chapter(
        nodes=[
            {
                "id": "top_1",
                "level": "topic",
                "official_title": "Topic 1",
                "page_start": 2,
                "page_end": 5,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "top_2",
                "level": "topic",
                "official_title": "Topic 2",
                "page_start": 6,
                "page_end": 10,
                "source_file": "test.pdf",
                "nodes": [],
            },
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "sibling_page_order_violated"]
    assert len(errors) == 0


def test_rule_sibling_sharing_boundary_page_pass(validator):
    # Sibling 1 spans 2..5, sibling 2 starts on boundary page 5..8: MUST PASS
    data = create_base_chapter(
        nodes=[
            {
                "id": "act_1",
                "level": "activity",
                "official_title": "Act 1",
                "page_start": 2,
                "page_end": 5,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "act_2",
                "level": "activity",
                "official_title": "Act 2",
                "page_start": 5,
                "page_end": 8,
                "source_file": "test.pdf",
                "nodes": [],
            },
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "sibling_page_order_violated"]
    assert len(errors) == 0


def test_rule_sibling_page_order_violated_fail(validator):
    # Sibling 2 starts on page 3, earlier than preceding sibling which started on page 8
    data = create_base_chapter(
        nodes=[
            {
                "id": "top_1",
                "level": "topic",
                "official_title": "Topic 1",
                "page_start": 8,
                "page_end": 12,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "top_2",
                "level": "topic",
                "official_title": "Topic 2",
                "page_start": 3,
                "page_end": 7,
                "source_file": "test.pdf",
                "nodes": [],
            },
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "sibling_page_order_violated"]
    assert len(errors) == 1


# ── Rule 6: Duplicate sibling titles & repeated activities ─────


def test_rule_duplicate_topic_sibling_fail(validator):
    # Duplicate topics under same chapter -> ERROR
    data = create_base_chapter(
        nodes=[
            {
                "id": "top_1",
                "level": "topic",
                "official_title": "Introduction",
                "page_start": 2,
                "page_end": 5,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "top_2",
                "level": "topic",
                "official_title": "Introduction",
                "page_start": 6,
                "page_end": 9,
                "source_file": "test.pdf",
                "nodes": [],
            },
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "duplicate_sibling_title"]
    assert len(errors) == 1


def test_rule_repeated_activity_titles_pass(validator):
    # Repeated activities (e.g. "Let us sing") under same parent are explicitly ALLOWED
    data = create_base_chapter(
        nodes=[
            {
                "id": "act_1",
                "level": "activity",
                "official_title": "Let us sing",
                "page_start": 2,
                "page_end": 3,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "act_2",
                "level": "activity",
                "official_title": "Let us sing",
                "page_start": 4,
                "page_end": 5,
                "source_file": "test.pdf",
                "nodes": [],
            },
            {
                "id": "act_3",
                "level": "activity",
                "official_title": "Let us sing",
                "page_start": 6,
                "page_end": 7,
                "source_file": "test.pdf",
                "nodes": [],
            },
        ]
    )
    issues = validator.validate_data(data)
    errors = [i for i in issues if i.rule_id == "duplicate_sibling_title"]
    assert len(errors) == 0


# ── Warnings ───────────────────────────────────────────────────


def test_warning_title_over_100_chars(validator):
    long_title = "A" * 105
    data = create_base_chapter(official_title=long_title)
    issues = validator.validate_data(data)
    warnings = [i for i in issues if i.rule_id == "title_over_100_chars"]
    assert len(warnings) == 1
    assert warnings[0].severity == "WARNING"


def test_warning_chapter_zero_activities(validator):
    # Chapter with 0 activities anywhere
    data = create_base_chapter(nodes=[])
    issues = validator.validate_data(data)
    warnings = [i for i in issues if i.rule_id == "chapter_zero_activities"]
    assert len(warnings) == 1
    assert warnings[0].severity == "WARNING"


def test_warning_excessive_subheadings(validator):
    subheadings = [
        {
            "id": f"subh_{i}",
            "level": "subheading",
            "official_title": f"Subheading {i}",
            "page_start": 2,
            "page_end": 2,
            "source_file": "test.pdf",
            "nodes": [],
        }
        for i in range(55)
    ]
    data = create_base_chapter(nodes=subheadings)
    issues = validator.validate_data(data)
    warnings = [i for i in issues if i.rule_id == "excessive_subheadings"]
    assert len(warnings) == 1
    assert warnings[0].severity == "WARNING"


def test_warning_ocr_needed_present(validator):
    data = create_base_chapter(ocr_needed=True)
    issues = validator.validate_data(data)
    warnings = [i for i in issues if i.rule_id == "ocr_needed_present"]
    assert len(warnings) == 1
    assert warnings[0].severity == "WARNING"


def test_warning_sibling_order_by_number(validator):
    # Pass case: 1.1 then 1.2
    data_pass = create_base_chapter(
        nodes=[
            {"id": "act_1", "level": "activity", "official_number": "1.1", "official_title": "Activity 1.1", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []},
            {"id": "act_2", "level": "activity", "official_number": "1.2", "official_title": "Activity 1.2", "page_start": 3, "page_end": 3, "source_file": "t.pdf", "nodes": []},
        ]
    )
    issues_pass = validator.validate_data(data_pass)
    assert len([i for i in issues_pass if i.rule_id == "sibling_order_by_number"]) == 0

    # Warn case: 1.6 then 1.5
    data_warn = create_base_chapter(
        nodes=[
            {"id": "act_6", "level": "activity", "official_number": "1.6", "official_title": "Activity 1.6", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []},
            {"id": "act_5", "level": "activity", "official_number": "1.5", "official_title": "Activity 1.5", "page_start": 3, "page_end": 3, "source_file": "t.pdf", "nodes": []},
        ]
    )
    issues_warn = validator.validate_data(data_warn)
    warns = [i for i in issues_warn if i.rule_id == "sibling_order_by_number"]
    assert len(warns) == 1
    assert warns[0].severity == "WARNING"


def test_warning_subtopic_parent_number_mismatch(validator):
    # Pass case: Topic 1.3 with Subtopic 1.3.1
    data_pass = create_base_chapter(
        nodes=[
            {
                "id": "top_3", "level": "topic", "official_number": "1.3", "official_title": "Effects", "page_start": 2, "page_end": 10, "source_file": "t.pdf",
                "nodes": [
                    {"id": "sub_1", "level": "subtopic", "official_number": "1.3.1", "official_title": "Corrosion", "page_start": 3, "page_end": 4, "source_file": "t.pdf", "nodes": []}
                ]
            }
        ]
    )
    issues_pass = validator.validate_data(data_pass)
    assert len([i for i in issues_pass if i.rule_id == "subtopic_parent_number_mismatch"]) == 0

    # Warn case: Topic 1.2 with Subtopic 1.3.1
    data_warn = create_base_chapter(
        nodes=[
            {
                "id": "top_2", "level": "topic", "official_number": "1.2", "official_title": "Types", "page_start": 2, "page_end": 10, "source_file": "t.pdf",
                "nodes": [
                    {"id": "sub_1", "level": "subtopic", "official_number": "1.3.1", "official_title": "Corrosion", "page_start": 3, "page_end": 4, "source_file": "t.pdf", "nodes": []}
                ]
            }
        ]
    )
    issues_warn = validator.validate_data(data_warn)
    warns = [i for i in issues_warn if i.rule_id == "subtopic_parent_number_mismatch"]
    assert len(warns) == 1
    assert warns[0].severity == "WARNING"


def test_warning_dangling_function_word(validator):
    # Failing cases with dangling function words
    dangling_examples = [
        ("1.3", "Properties of Matter and"),
        ("1.5", "Laws of"),
        ("1.5.4", "Gay Lussac's Law of"),
        ("1.9.1", "Empirical Formula for"),
        ("1.10", "Stoichiometry with"),
        ("1.1", "Between"),
    ]
    for num, title in dangling_examples:
        data = create_base_chapter(
            nodes=[
                {"id": "top_d", "level": "topic", "official_number": num, "official_title": title, "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}
            ]
        )
        issues = validator.validate_data(data)
        warns = [i for i in issues if i.rule_id == "dangling_function_word"]
        assert len(warns) >= 1, f"Expected dangling warning for '{title}'"
        assert warns[0].severity == "WARNING"

    # Passing cases
    pass_examples = [
        ("1.3", "Properties of Matter and their Measurement"),
        ("1.5", "Laws of Chemical Combinations"),
        ("1.5.4", "Gay Lussac's Law of Gaseous Volumes"),
    ]
    for num, title in pass_examples:
        data = create_base_chapter(
            nodes=[
                {"id": "top_p", "level": "topic", "official_number": num, "official_title": title, "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}
            ]
        )
        issues = validator.validate_data(data)
        warns = [i for i in issues if i.rule_id == "dangling_function_word"]
        assert len(warns) == 0, f"Unexpected dangling warning for '{title}'"


def test_plausibility_checks(validator):
    # 1. Lowercase start
    d_lower = create_base_chapter(nodes=[{"id": "n1", "level": "subtopic", "official_title": "an iron nail", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "title_starts_lowercase" for i in validator.validate_data(d_lower))

    # 2. Ends in comma
    d_comma = create_base_chapter(nodes=[{"id": "n2", "level": "subtopic", "official_title": "Properties of matter,", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "title_ends_comma" for i in validator.validate_data(d_comma))

    # 3. Unbalanced quotes
    d_quotes = create_base_chapter(nodes=[{"id": "n3", "level": "subtopic", "official_title": 'Definition of "Atom', "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "unbalanced_quotes" for i in validator.validate_data(d_quotes))

    # 4. Sentence boundary inside title
    d_sent = create_base_chapter(nodes=[{"id": "n4", "level": "subtopic", "official_title": "Mass and Weight. Next we consider", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "title_contains_sentence_boundary" for i in validator.validate_data(d_sent))

    # 5. Word count > 12
    long_t = "One two three four five six seven eight nine ten eleven twelve thirteen"
    d_long = create_base_chapter(nodes=[{"id": "n5", "level": "subtopic", "official_title": long_t, "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "title_word_count_exceeded" for i in validator.validate_data(d_long))

    # 6. Bare UNIT token
    d_unit = create_base_chapter(nodes=[{"id": "n6", "level": "subheading", "official_title": "UNIT - 1", "page_start": 2, "page_end": 2, "source_file": "t.pdf", "nodes": []}])
    assert any(i.rule_id == "bare_unit_token" for i in validator.validate_data(d_unit))


def test_suspicion_score_threshold(validator):
    # Book with 10 nodes, 2 suspicious (>10%)
    nodes = [{"id": f"n_{i}", "level": "subtopic", "official_title": f"Topic {i}", "page_start": i+1, "page_end": i+1, "source_file": "t.pdf", "nodes": []} for i in range(8)]
    nodes.append({"id": "susp_1", "level": "subtopic", "official_title": "an iron nail", "page_start": 9, "page_end": 9, "source_file": "t.pdf", "nodes": []})
    nodes.append({"id": "susp_2", "level": "subtopic", "official_title": "ends with comma,", "page_start": 10, "page_end": 10, "source_file": "t.pdf", "nodes": []})
    book_data = {"book_code": "test_susp", "chapters": [create_base_chapter(nodes=nodes)]}

    validator.validate_data(book_data)
    score, status = validator.get_suspicion_metrics()
    assert score > 0.10
    assert status == "needs_review"

    # Clean book
    clean_nodes = [{"id": f"cn_{i}", "level": "subtopic", "official_title": f"Valid Topic {i}", "page_start": i+1, "page_end": i+1, "source_file": "t.pdf", "nodes": []} for i in range(10)]
    clean_data = {"book_code": "test_clean", "chapters": [create_base_chapter(nodes=clean_nodes)]}
    validator.validate_data(clean_data)
    clean_score, clean_status = validator.get_suspicion_metrics()
    assert clean_score == 0.0
    assert clean_status == "ok"

