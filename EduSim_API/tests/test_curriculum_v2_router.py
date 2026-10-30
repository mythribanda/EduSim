"""
EduSim_API/tests/test_curriculum_v2_router.py
=============================================
Pytest suite testing the Curriculum V2 read-only endpoints:
1. GET /api/curriculum/v2/books - list active books with pagination and filters
2. GET /api/curriculum/v2/books/{book_code}/chapters - flat chapter list with page ranges
3. GET /api/curriculum/v2/books/{book_code}/tree - nested tree respecting real hierarchy with skipped levels
4. GET /api/curriculum/v2/books/{book_code}/tree?max_level= - tree depth filtering
5. 404 Handling - unknown book_code returns 404
6. Inactive nodes/books hidden - is_active=False items are hidden from list, tree, chapters, and node endpoints
7. GET /api/curriculum/v2/nodes/{node_id} - node detail with ancestor breadcrumb chain
"""

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["JWT_SECRET"] = "01234567890123456789012345678901"
os.environ["JWT_SECRET_KEY"] = "01234567890123456789012345678901"
os.environ["SUPABASE_URL"] = "https://qhdkgvthkktovccdyase.supabase.co"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.src.config.database import Base, get_db
from app.src.models.curriculum_pipeline_models import Book, CurriculumNode
from main import app


@pytest.fixture(scope="module")
def db_context():
    """Setup an in-memory SQLite database and test client with sample curriculum data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Create active books
    b1 = Book(
        id=uuid.uuid4(),
        code="keph1",
        title="Physics Part 1",
        board="ncert",
        class_num=11,
        subject="physics",
        language="en",
        total_pages=150,
        ocr_page_count=0,
        text_quality="ok",
        extraction_status="ok",
        pipeline_version="2.0.0",
        is_active=True,
    )
    b2 = Book(
        id=uuid.uuid4(),
        code="keph2",
        title="Physics Part 2",
        board="ncert",
        class_num=11,
        subject="physics",
        language="en",
        total_pages=160,
        ocr_page_count=0,
        text_quality="ok",
        extraction_status="ok",
        pipeline_version="2.0.0",
        is_active=True,
    )
    b3 = Book(
        id=uuid.uuid4(),
        code="jesc1",
        title="Science Class 10",
        board="ncert",
        class_num=10,
        subject="science",
        language="en",
        total_pages=200,
        ocr_page_count=0,
        text_quality="ok",
        extraction_status="ok",
        pipeline_version="2.0.0",
        is_active=True,
    )
    # Inactive book
    b_inactive = Book(
        id=uuid.uuid4(),
        code="archived_book",
        title="Archived Book",
        board="ncert",
        class_num=12,
        subject="chemistry",
        language="en",
        total_pages=100,
        ocr_page_count=0,
        text_quality="ok",
        extraction_status="ok",
        pipeline_version="2.0.0",
        is_active=False,
    )
    session.add_all([b1, b2, b3, b_inactive])
    session.flush()

    # Add nodes to b1 (keph1) demonstrating:
    # 1. Normal chapter -> topic -> subtopic
    # 2. Skipped levels:
    #    - Chapter 1 directly has Activity 1.1 (skipping topic level)
    #    - Topic 1.2 directly has Subheading 1.2.1 (skipping subtopic level)
    # 3. Inactive node
    ch1 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="chapter",
        parent_id=None,
        order_index=1,
        official_number="1",
        title="Units and Measurements",
        normalized_title="units and measurements",
        page_start=1,
        page_end=30,
        source_page_start=5,
        source_page_end=34,
        identity_key="ch_1",
        is_active=True,
    )
    ch2 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="2",
        level="chapter",
        parent_id=None,
        order_index=2,
        official_number="2",
        title="Motion in a Straight Line",
        normalized_title="motion in a straight line",
        page_start=31,
        page_end=60,
        source_page_start=35,
        source_page_end=64,
        identity_key="ch_2",
        is_active=True,
    )
    session.add_all([ch1, ch2])
    session.flush()

    # Children of Chapter 1:
    top1 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="topic",
        parent_id=ch1.id,
        order_index=1,
        official_number="1.1",
        title="Introduction to Units",
        normalized_title="introduction to units",
        page_start=1,
        page_end=5,
        source_page_start=5,
        source_page_end=9,
        identity_key="top_1_1",
        is_active=True,
    )
    # Skipped level: Activity directly under Chapter 1
    act1 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="activity",
        parent_id=ch1.id,
        order_index=2,
        official_number="Activity 1.1",
        title="Measuring Pendulum Period",
        normalized_title="measuring pendulum period",
        page_start=6,
        page_end=7,
        source_page_start=10,
        source_page_end=11,
        identity_key="act_1_1",
        is_active=True,
    )
    top2 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="topic",
        parent_id=ch1.id,
        order_index=3,
        official_number="1.2",
        title="Significant Figures",
        normalized_title="significant figures",
        page_start=8,
        page_end=15,
        source_page_start=12,
        source_page_end=19,
        identity_key="top_1_2",
        is_active=True,
    )
    # Inactive topic under Chapter 1
    top_inactive = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="topic",
        parent_id=ch1.id,
        order_index=4,
        official_number="1.3",
        title="Deprecated Measurement",
        normalized_title="deprecated measurement",
        page_start=16,
        page_end=20,
        source_page_start=20,
        source_page_end=24,
        identity_key="top_1_3_inactive",
        is_active=False,
    )
    session.add_all([top1, act1, top2, top_inactive])
    session.flush()

    # Skipped level: Subheading directly under Topic 1.2 (skipping subtopic)
    subhead1 = CurriculumNode(
        id=uuid.uuid4(),
        book_id=b1.id,
        chapter_number="1",
        level="subheading",
        parent_id=top2.id,
        order_index=1,
        official_number=None,
        title="Rounding Off Numbers",
        normalized_title="rounding off numbers",
        page_start=10,
        page_end=12,
        source_page_start=14,
        source_page_end=16,
        identity_key="subhead_rounding",
        is_active=True,
    )
    session.add(subhead1)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "session": session,
        "books": {"keph1": b1, "keph2": b2, "jesc1": b3, "archived": b_inactive},
        "nodes": {
            "ch1": ch1,
            "ch2": ch2,
            "top1": top1,
            "act1": act1,
            "top2": top2,
            "top_inactive": top_inactive,
            "subhead1": subhead1,
        },
    }

    app.dependency_overrides.pop(get_db, None)
    session.close()


def test_list_books_pagination_and_filter(db_context):
    """Test GET /api/curriculum/v2/books pagination, sorting, and query filters."""
    client = db_context["client"]

    # 1. List all active books (inactive book 'archived_book' must not appear)
    res = client.get("/api/curriculum/v2/books")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    codes = [b["code"] for b in data["items"]]
    assert "archived_book" not in codes
    assert "keph1" in codes
    assert "keph2" in codes
    assert "jesc1" in codes

    # 2. Pagination: limit=2, offset=0
    res_page1 = client.get("/api/curriculum/v2/books?limit=2&offset=0")
    assert res_page1.status_code == 200
    p1 = res_page1.json()
    assert len(p1["items"]) == 2
    assert p1["limit"] == 2
    assert p1["offset"] == 0
    assert p1["total"] == 3

    # Pagination: limit=2, offset=2
    res_page2 = client.get("/api/curriculum/v2/books?limit=2&offset=2")
    assert res_page2.status_code == 200
    p2 = res_page2.json()
    assert len(p2["items"]) == 1
    assert p2["offset"] == 2

    # 3. Filtering by class_num
    res_cls10 = client.get("/api/curriculum/v2/books?class_num=10")
    assert res_cls10.status_code == 200
    cls10_items = res_cls10.json()["items"]
    assert len(cls10_items) == 1
    assert cls10_items[0]["code"] == "jesc1"

    # 4. Filtering by subject (case-insensitive)
    res_subj = client.get("/api/curriculum/v2/books?subject=PHYSICS")
    assert res_subj.status_code == 200
    subj_items = res_subj.json()["items"]
    assert len(subj_items) == 2
    assert all(b["subject"] == "physics" for b in subj_items)

    # 5. Filtering by board
    res_board = client.get("/api/curriculum/v2/books?board=ncert")
    assert res_board.status_code == 200
    assert res_board.json()["total"] == 3


def test_get_book_chapters(db_context):
    """Test GET /api/curriculum/v2/books/{book_code}/chapters flat chapter list."""
    client = db_context["client"]

    # 1. Fetch chapters for keph1
    res = client.get("/api/curriculum/v2/books/keph1/chapters")
    assert res.status_code == 200
    chapters = res.json()
    assert len(chapters) == 2
    assert chapters[0]["chapter_number"] == "1"
    assert chapters[0]["title"] == "Units and Measurements"
    assert chapters[0]["page_start"] == 1
    assert chapters[0]["page_end"] == 30
    assert chapters[0]["source_page_start"] == 5
    assert chapters[0]["source_page_end"] == 34
    assert chapters[1]["chapter_number"] == "2"
    assert chapters[1]["title"] == "Motion in a Straight Line"


def test_get_unknown_book_code_404(db_context):
    """Verify 404 is returned when requesting nonexistent or inactive book_code."""
    client = db_context["client"]

    # Nonexistent book code
    res_tree = client.get("/api/curriculum/v2/books/nonexistent_code/tree")
    assert res_tree.status_code == 404
    assert "not found" in res_tree.json()["detail"].lower()

    res_chap = client.get("/api/curriculum/v2/books/nonexistent_code/chapters")
    assert res_chap.status_code == 404

    # Inactive book code returns 404
    res_inact_tree = client.get("/api/curriculum/v2/books/archived_book/tree")
    assert res_inact_tree.status_code == 404

    res_inact_chap = client.get("/api/curriculum/v2/books/archived_book/chapters")
    assert res_inact_chap.status_code == 404


def test_get_book_tree_with_skipped_levels(db_context):
    """Verify nested tree preserves real hierarchy without invented placeholder levels."""
    client = db_context["client"]

    res = client.get("/api/curriculum/v2/books/keph1/tree")
    assert res.status_code == 200
    tree = res.json()

    # Roots should be Chapter 1 and Chapter 2
    assert len(tree) == 2
    ch1_node = next(c for c in tree if c["chapter_number"] == "1")
    assert ch1_node["level"] == "chapter"
    assert ch1_node["title"] == "Units and Measurements"

    # Chapter 1 direct children: Topic 1.1, Activity 1.1 (skipped topic!), Topic 1.2
    ch1_children = ch1_node["nodes"]
    assert len(ch1_children) == 3
    child_levels = [c["level"] for c in ch1_children]
    assert child_levels == ["topic", "activity", "topic"]

    # Verify Activity 1.1 is directly under Chapter 1 without an invented intermediate level
    act_child = ch1_children[1]
    assert act_child["level"] == "activity"
    assert act_child["official_number"] == "Activity 1.1"
    assert act_child["title"] == "Measuring Pendulum Period"

    # Verify Topic 1.2 has Subheading directly under it (skipping subtopic level)
    top2_child = ch1_children[2]
    assert top2_child["level"] == "topic"
    assert len(top2_child["nodes"]) == 1
    subhead_child = top2_child["nodes"][0]
    assert subhead_child["level"] == "subheading"
    assert subhead_child["title"] == "Rounding Off Numbers"


def test_get_book_tree_max_level(db_context):
    """Verify max_level query parameter filters tree depth."""
    client = db_context["client"]

    # 1. max_level = "topic": Should include chapter and topic, but omit activity and subheading
    res = client.get("/api/curriculum/v2/books/keph1/tree?max_level=topic")
    assert res.status_code == 200
    tree = res.json()
    ch1_node = next(c for c in tree if c["chapter_number"] == "1")
    ch1_children = ch1_node["nodes"]

    # Only topics should remain (Activity 1.1 excluded)
    assert len(ch1_children) == 2
    assert all(c["level"] == "topic" for c in ch1_children)

    # Subheading inside Topic 1.2 should also be omitted
    top2 = ch1_children[1]
    assert len(top2["nodes"]) == 0

    # 2. max_level = "chapter": Only chapters returned with empty nodes
    res_chap = client.get("/api/curriculum/v2/books/keph1/tree?max_level=chapter")
    assert res_chap.status_code == 200
    tree_chap = res_chap.json()
    assert len(tree_chap) == 2
    assert tree_chap[0]["nodes"] == []
    assert tree_chap[1]["nodes"] == []

    # 3. Invalid max_level returns 400 Bad Request
    res_invalid = client.get("/api/curriculum/v2/books/keph1/tree?max_level=paragraph")
    assert res_invalid.status_code == 400
    assert "Invalid max_level" in res_invalid.json()["detail"]


def test_inactive_nodes_hidden(db_context):
    """Verify nodes with is_active=False are omitted from tree and return 404 from node endpoint."""
    client = db_context["client"]
    nodes = db_context["nodes"]
    inactive_node = nodes["top_inactive"]

    # 1. Inactive node must not be in tree
    res_tree = client.get("/api/curriculum/v2/books/keph1/tree")
    assert res_tree.status_code == 200
    tree_text = res_tree.text
    assert "Deprecated Measurement" not in tree_text
    assert str(inactive_node.id) not in tree_text

    # 2. Requesting the inactive node directly returns 404
    res_node = client.get(f"/api/curriculum/v2/nodes/{inactive_node.id}")
    assert res_node.status_code == 404
    assert "not found" in res_node.json()["detail"].lower()


def test_get_curriculum_node_with_breadcrumb(db_context):
    """Test GET /api/curriculum/v2/nodes/{node_id} returns node details and ancestor breadcrumbs."""
    client = db_context["client"]
    nodes = db_context["nodes"]
    subhead = nodes["subhead1"]

    # 1. Request leaf node (Subheading 1.2.1)
    res = client.get(f"/api/curriculum/v2/nodes/{subhead.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(subhead.id)
    assert data["level"] == "subheading"
    assert data["title"] == "Rounding Off Numbers"
    assert data["is_active"] is True

    # Breadcrumb chain must be top-down: [Chapter 1, Topic 1.2]
    breadcrumb = data["breadcrumb"]
    assert len(breadcrumb) == 2
    assert breadcrumb[0]["level"] == "chapter"
    assert breadcrumb[0]["title"] == "Units and Measurements"
    assert breadcrumb[1]["level"] == "topic"
    assert breadcrumb[1]["title"] == "Significant Figures"

    # 2. Request root node (Chapter 1) -> breadcrumb is empty list
    ch1 = nodes["ch1"]
    res_ch = client.get(f"/api/curriculum/v2/nodes/{ch1.id}")
    assert res_ch.status_code == 200
    assert res_ch.json()["breadcrumb"] == []

    # 3. Invalid UUID returns 404
    res_bad_id = client.get("/api/curriculum/v2/nodes/not-a-valid-uuid")
    assert res_bad_id.status_code == 404

    # 4. Nonexistent UUID returns 404
    random_uuid = uuid.uuid4()
    res_nonexistent = client.get(f"/api/curriculum/v2/nodes/{random_uuid}")
    assert res_nonexistent.status_code == 404
