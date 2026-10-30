import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.curriculum_pipeline_models import Book, CurriculumNode

router = APIRouter(prefix="/curriculum/v2", tags=["Curriculum V2"])

LEVEL_RANKS = {
    "chapter": 0,
    "topic": 1,
    "subtopic": 2,
    "activity": 3,
    "subheading": 4,
}


# ============================================================================
# Pydantic Response Models
# ============================================================================

class BookResponse(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    board: str
    class_num: int
    subject: str
    language: Optional[str] = None
    part: Optional[int] = None
    total_pages: int
    ocr_page_count: int
    text_quality: Optional[str] = None
    extraction_status: str
    pipeline_version: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BookListResponse(BaseModel):
    items: List[BookResponse]
    total: int
    limit: int
    offset: int


class ChapterSummaryResponse(BaseModel):
    id: uuid.UUID
    chapter_number: str
    official_number: Optional[str] = None
    title: str
    page_start: int
    page_end: int
    source_page_start: int
    source_page_end: int
    source_file: Optional[str] = None
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class TreeNodeResponse(BaseModel):
    id: uuid.UUID
    chapter_number: str
    level: str
    parent_id: Optional[uuid.UUID] = None
    order_index: int
    official_number: Optional[str] = None
    title: str
    normalized_title: str
    page_start: int
    page_end: int
    source_page_start: int
    source_page_end: int
    source_file: Optional[str] = None
    ocr_needed: bool = False
    metadata_json: Optional[Any] = None
    nodes: List["TreeNodeResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BreadcrumbItem(BaseModel):
    id: uuid.UUID
    level: str
    chapter_number: str
    official_number: Optional[str] = None
    title: str
    page_start: int
    page_end: int

    model_config = ConfigDict(from_attributes=True)


class NodeDetailResponse(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    chapter_number: str
    level: str
    parent_id: Optional[uuid.UUID] = None
    order_index: int
    official_number: Optional[str] = None
    title: str
    normalized_title: str
    occurrence_index: int
    page_start: int
    page_end: int
    source_page_start: int
    source_page_end: int
    source_file: Optional[str] = None
    ocr_needed: bool
    metadata_json: Optional[Any] = None
    identity_key: str
    is_active: bool
    breadcrumb: List[BreadcrumbItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/books", response_model=BookListResponse)
def list_books(
    board: Optional[str] = Query(None, description="Filter by board, e.g. ncert"),
    class_num: Optional[int] = Query(None, description="Filter by class number, e.g. 10"),
    subject: Optional[str] = Query(None, description="Filter by subject, e.g. physics"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Offset items"),
    db: Session = Depends(get_db),
):
    """List active curriculum books with optional filters and pagination."""
    query = db.query(Book).filter(Book.is_active.is_(True))

    if board:
        query = query.filter(func.lower(Book.board) == board.strip().lower())
    if class_num is not None:
        query = query.filter(Book.class_num == class_num)
    if subject:
        query = query.filter(func.lower(Book.subject) == subject.strip().lower())

    total = query.count()
    items = (
        query.order_by(Book.class_num.asc(), Book.subject.asc(), Book.code.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return BookListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/books/{book_code}/chapters", response_model=List[ChapterSummaryResponse])
def get_book_chapters(
    book_code: str,
    db: Session = Depends(get_db),
):
    """Return flat list of active chapters with page ranges for a book."""
    book = db.query(Book).filter(Book.code == book_code, Book.is_active.is_(True)).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book '{book_code}' not found",
        )

    chapters = (
        db.query(CurriculumNode)
        .filter(
            CurriculumNode.book_id == book.id,
            CurriculumNode.level == "chapter",
            CurriculumNode.is_active.is_(True),
        )
        .order_by(CurriculumNode.order_index.asc(), CurriculumNode.page_start.asc())
        .all()
    )

    return chapters


@router.get("/books/{book_code}/tree", response_model=List[TreeNodeResponse])
def get_book_tree(
    book_code: str,
    max_level: Optional[str] = Query(
        None,
        description="Filter maximum tree depth: chapter, topic, subtopic, activity, or subheading",
    ),
    db: Session = Depends(get_db),
):
    """Return nested curriculum tree respecting the real hierarchy without invented levels."""
    book = db.query(Book).filter(Book.code == book_code, Book.is_active.is_(True)).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book '{book_code}' not found",
        )

    allowed_levels = None
    if max_level:
        max_lvl_lower = max_level.strip().lower()
        if max_lvl_lower not in LEVEL_RANKS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid max_level '{max_level}'. Allowed values: {list(LEVEL_RANKS.keys())}",
            )
        target_rank = LEVEL_RANKS[max_lvl_lower]
        allowed_levels = [lvl for lvl, rank in LEVEL_RANKS.items() if rank <= target_rank]

    query = db.query(CurriculumNode).filter(
        CurriculumNode.book_id == book.id,
        CurriculumNode.is_active.is_(True),
    )
    if allowed_levels is not None:
        query = query.filter(CurriculumNode.level.in_(allowed_levels))

    nodes = query.order_by(CurriculumNode.order_index.asc(), CurriculumNode.page_start.asc()).all()

    # Build tree in memory
    tree_map = {}
    for n in nodes:
        tree_map[n.id] = TreeNodeResponse(
            id=n.id,
            chapter_number=n.chapter_number,
            level=n.level,
            parent_id=n.parent_id,
            order_index=n.order_index,
            official_number=n.official_number,
            title=n.title,
            normalized_title=n.normalized_title,
            page_start=n.page_start,
            page_end=n.page_end,
            source_page_start=n.source_page_start,
            source_page_end=n.source_page_end,
            source_file=n.source_file,
            ocr_needed=n.ocr_needed,
            metadata_json=n.metadata_json,
            nodes=[],
        )

    roots: List[TreeNodeResponse] = []
    for n in nodes:
        item = tree_map[n.id]
        if n.parent_id and n.parent_id in tree_map:
            tree_map[n.parent_id].nodes.append(item)
        elif n.level == "chapter" or n.parent_id is None:
            roots.append(item)

    return roots


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
def get_curriculum_node(
    node_id: str,
    db: Session = Depends(get_db),
):
    """Return a single active curriculum node with its ancestor breadcrumb chain."""
    try:
        node_uuid = uuid.UUID(str(node_id))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )

    node = (
        db.query(CurriculumNode)
        .filter(CurriculumNode.id == node_uuid, CurriculumNode.is_active.is_(True))
        .first()
    )
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )

    # Collect breadcrumbs upwards
    breadcrumb: List[BreadcrumbItem] = []
    curr_parent_id = node.parent_id
    while curr_parent_id:
        parent = (
            db.query(CurriculumNode)
            .filter(CurriculumNode.id == curr_parent_id, CurriculumNode.is_active.is_(True))
            .first()
        )
        if not parent:
            break
        breadcrumb.append(
            BreadcrumbItem(
                id=parent.id,
                level=parent.level,
                chapter_number=parent.chapter_number,
                official_number=parent.official_number,
                title=parent.title,
                page_start=parent.page_start,
                page_end=parent.page_end,
            )
        )
        curr_parent_id = parent.parent_id

    # Reverse breadcrumb to be root-to-parent order
    breadcrumb.reverse()

    return NodeDetailResponse(
        id=node.id,
        book_id=node.book_id,
        chapter_number=node.chapter_number,
        level=node.level,
        parent_id=node.parent_id,
        order_index=node.order_index,
        official_number=node.official_number,
        title=node.title,
        normalized_title=node.normalized_title,
        occurrence_index=node.occurrence_index,
        page_start=node.page_start,
        page_end=node.page_end,
        source_page_start=node.source_page_start,
        source_page_end=node.source_page_end,
        source_file=node.source_file,
        ocr_needed=node.ocr_needed,
        metadata_json=node.metadata_json,
        identity_key=node.identity_key,
        is_active=node.is_active,
        breadcrumb=breadcrumb,
    )
