"""
Unit & Integration Tests for EduSim Curriculum Database Loader (Step 3)
Tests:
1. Load twice -> assert no duplicate records inserted.
2. Rename detection -> change a title with same official_number and assert node UUID is retained.
3. Soft deactivation & reactivation -> remove node asserts is_active=False, re-add asserts is_active=True.
4. needs_review refused without flag -> accepted with --include-review.
5. Invalid book refused -> fails validation and refuses load.
6. Unchanged sha256 skipped -> skips without --force.
7. Full-book fixtures (fegp1, jesc1) load cleanly into database.
"""

import json
import uuid
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.src.config.database import Base
from app.src.models.curriculum_pipeline_models import Book, CurriculumNode
from curriculum_pipeline.loader import CurriculumDatabaseLoader, compute_node_identity_key
from curriculum_pipeline.pipeline_config import PIPELINE_OUTPUT_ROOT, PIPELINE_VERSION


@pytest.fixture
def memory_db():
    """Provides an isolated, in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def _make_dummy_book(tmp_path: Path, book_code: str, status: str = "ok", sha256: str = "abc123sha", chapters=None) -> Path:
    if chapters is None:
        chapters = [
            {
                "id": f"{book_code}_ch_1",
                "level": "chapter",
                "source_file": f"{book_code}01.pdf",
                "official_number": "1",
                "official_title": "First Chapter",
                "normalized_title": "first chapter",
                "page_start": 1,
                "page_end": 10,
                "nodes": [
                    {
                        "id": f"{book_code}_top_1",
                        "level": "topic",
                        "source_file": f"{book_code}01.pdf",
                        "official_number": "1.1",
                        "official_title": "Original Topic Title",
                        "normalized_title": "original topic title",
                        "occurrence_index": 0,
                        "page_start": 1,
                        "page_end": 5,
                        "nodes": [],
                    },
                    {
                        "id": f"{book_code}_top_2",
                        "level": "topic",
                        "source_file": f"{book_code}01.pdf",
                        "official_number": "1.2",
                        "official_title": "Second Topic",
                        "normalized_title": "second topic",
                        "occurrence_index": 0,
                        "page_start": 6,
                        "page_end": 10,
                        "nodes": [],
                    },
                ],
            }
        ]

    book_dict = {
        "book_code": book_code,
        "board": "ncert",
        "class": 6,
        "subject": "math",
        "medium": "en",
        "title": f"Book {book_code}",
        "total_pages": 10,
        "source_sha256": sha256,
        "extraction_status": status,
        "source_files": [f"{book_code}01.pdf"],
        "chapters": chapters,
    }

    fpath = tmp_path / f"{book_code}.json"
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(book_dict, f)
    return fpath


def test_load_twice_no_duplicates(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    book_file = _make_dummy_book(tmp_path, "test_b1")
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())

    # First load
    res1 = loader.load_book(book_file, memory_db, run_id=run_id_1)
    memory_db.commit()
    assert res1["status"] == "loaded"
    assert res1["inserted"] == 3  # 1 chapter + 2 topics

    nodes_count_1 = memory_db.query(CurriculumNode).count()
    assert nodes_count_1 == 3

    # Second load with force=True
    res2 = loader.load_book(book_file, memory_db, run_id=run_id_2, force=True)
    memory_db.commit()
    assert res2["status"] == "loaded"
    assert res2["inserted"] == 0
    assert res2["unchanged"] == 3

    nodes_count_2 = memory_db.query(CurriculumNode).count()
    assert nodes_count_2 == 3, "No duplicate records should be created"


def test_rename_detection_retains_node_id(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    book_file = _make_dummy_book(tmp_path, "test_rename")
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())

    # Initial load
    res1 = loader.load_book(book_file, memory_db, run_id=run_id_1)
    memory_db.commit()
    assert res1["status"] == "loaded"

    orig_node = memory_db.query(CurriculumNode).filter(CurriculumNode.official_number == "1.1").first()
    assert orig_node is not None
    orig_id = orig_node.id
    assert orig_node.title == "Original Topic Title"

    # Modify title for 1.1 in file and reload with force
    with open(book_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["chapters"][0]["nodes"][0]["official_title"] = "Brand New Renamed Title"
    data["chapters"][0]["nodes"][0]["normalized_title"] = "brand new renamed title"
    with open(book_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res2 = loader.load_book(book_file, memory_db, run_id=run_id_2, force=True)
    memory_db.commit()

    assert res2["renamed"] == 1
    assert res2["inserted"] == 0

    renamed_node = memory_db.query(CurriculumNode).filter(CurriculumNode.official_number == "1.1").first()
    assert renamed_node.id == orig_id, "Node UUID must be retained upon rename"
    assert renamed_node.title == "Brand New Renamed Title"
    assert renamed_node.is_active is True


def test_soft_deactivation_and_reactivation(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    book_file = _make_dummy_book(tmp_path, "test_deact")
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())
    run_id_3 = str(uuid.uuid4())

    # 1. Initial load (3 nodes: ch, top1, top2)
    loader.load_book(book_file, memory_db, run_id=run_id_1)
    memory_db.commit()

    node2 = memory_db.query(CurriculumNode).filter(CurriculumNode.official_number == "1.2").first()
    assert node2.is_active is True
    node2_id = node2.id

    # 2. Remove node 1.2 from file and reload
    with open(book_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["chapters"][0]["nodes"] = [data["chapters"][0]["nodes"][0]]  # Keep only 1.1
    with open(book_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res2 = loader.load_book(book_file, memory_db, run_id=run_id_2, force=True)
    memory_db.commit()
    assert res2["deactivated"] == 1

    node2_after = memory_db.query(CurriculumNode).filter(CurriculumNode.id == node2_id).first()
    assert node2_after is not None, "Node must never be hard-deleted"
    assert node2_after.is_active is False

    # 3. Bring back node 1.2 and reload
    with open(book_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["chapters"][0]["nodes"].append({
        "id": "test_deact_top_2",
        "level": "topic",
        "source_file": "test_deact01.pdf",
        "official_number": "1.2",
        "official_title": "Second Topic",
        "normalized_title": "second topic",
        "occurrence_index": 0,
        "page_start": 6,
        "page_end": 10,
        "nodes": [],
    })
    with open(book_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res3 = loader.load_book(book_file, memory_db, run_id=run_id_3, force=True)
    memory_db.commit()
    assert res3["reactivated"] == 1

    node2_reactivated = memory_db.query(CurriculumNode).filter(CurriculumNode.id == node2_id).first()
    assert node2_reactivated.is_active is True


def test_needs_review_refused_without_flag(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    book_file = _make_dummy_book(tmp_path, "test_review", status="needs_review")
    run_id = str(uuid.uuid4())

    # Without include_review -> refused
    res_refused = loader.load_book(book_file, memory_db, run_id=run_id, include_review=False)
    assert res_refused["status"] == "refused"
    assert "needs_review" in res_refused["reason"]

    # With include_review -> accepted
    res_accepted = loader.load_book(book_file, memory_db, run_id=run_id, include_review=True)
    memory_db.commit()
    assert res_accepted["status"] == "loaded"


def test_invalid_book_refused(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    # Create invalid book: child page range [20, 20] outside parent [1, 10]
    bad_chapters = [
        {
            "id": "bad_ch",
            "official_number": "1",
            "official_title": "Bad Chapter",
            "normalized_title": "bad chapter",
            "page_start": 1,
            "page_end": 10,
            "nodes": [
                {
                    "id": "bad_top",
                    "level": "topic",
                    "official_number": "1.1",
                    "official_title": "Out of Range Topic",
                    "normalized_title": "out of range topic",
                    "occurrence_index": 0,
                    "page_start": 20,
                    "page_end": 20,
                    "nodes": [],
                }
            ],
        }
    ]
    bad_file = _make_dummy_book(tmp_path, "test_invalid", chapters=bad_chapters)
    run_id = str(uuid.uuid4())

    res = loader.load_book(bad_file, memory_db, run_id=run_id)
    assert res["status"] == "refused"
    assert "Validation failed" in res["reason"]


def test_unchanged_sha256_skipped(tmp_path, memory_db):
    loader = CurriculumDatabaseLoader()
    book_file = _make_dummy_book(tmp_path, "test_skip", sha256="fixed_hash_123")
    run_id = str(uuid.uuid4())

    # First load
    res1 = loader.load_book(book_file, memory_db, run_id=run_id)
    memory_db.commit()
    assert res1["status"] == "loaded"

    # Second load without force
    res2 = loader.load_book(book_file, memory_db, run_id=run_id, force=False)
    assert res2["status"] == "skipped"
    assert "Unchanged sha256" in res2["reason"]


def test_full_book_fixtures_load_cleanly(memory_db):
    loader = CurriculumDatabaseLoader()
    run_id = str(uuid.uuid4())

    for bcode, exp_nodes in [("fegp1", 178), ("jesc1", 304)]:
        bpath = PIPELINE_OUTPUT_ROOT / "curriculum" / "books" / f"{bcode}.json"
        if not bpath.exists():
            pytest.skip(f"{bcode}.json not available for test")

        res = loader.load_book(bpath, memory_db, run_id=run_id, force=True)
        memory_db.commit()
        assert res["status"] == "loaded"
        assert res["inserted"] == exp_nodes

        db_book = memory_db.query(Book).filter(Book.code == bcode).first()
        assert db_book is not None
        assert db_book.total_pages > 0

        db_nodes_count = memory_db.query(CurriculumNode).filter(CurriculumNode.book_id == db_book.id).count()
        assert db_nodes_count == exp_nodes
