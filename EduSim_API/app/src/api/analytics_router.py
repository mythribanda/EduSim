"""
app/src/api/analytics_router.py — Pure Python Class Analytics Router for EduSim.

Provides endpoints:
- GET /analytics/class/{class_id}
- GET /analytics/class/{class_id}/export (CSV download)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.user import User
from app.src.middleware.rbac import require_role, check_class_membership, normalize_role
from app.src.services.analytics import get_class_analytics, export_class_analytics_csv

logger = logging.getLogger("EduSim.api.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class TopicBreakdownItem(BaseModel):
    topic: str
    avg_mastery: float
    weak_students: int


class EngagementOut(BaseModel):
    active_this_week: int
    total_students: int


class AtRiskStudentOut(BaseModel):
    id: Optional[str] = None
    student_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    mastery: float
    last_active: str


class ClassAnalyticsResponse(BaseModel):
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    grade_level: Optional[str] = None
    class_average_mastery: float
    topic_breakdown: List[TopicBreakdownItem] = Field(default_factory=list)
    most_asked_topics: List[str] = Field(default_factory=list)
    engagement: EngagementOut
    assignments_submitted: Optional[int] = 0
    at_risk_students: List[AtRiskStudentOut] = Field(default_factory=list)


@router.get("/class/{class_id}", response_model=ClassAnalyticsResponse)
@router.get("/classes/{class_id}", response_model=ClassAnalyticsResponse, include_in_schema=False)
def get_analytics_for_class(
    class_id: str = Path(..., description="Class ID (UUID or string)"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Pure Python & SQL class analytics endpoint.
    Zero LLM / AI calls — 100% computed from database aggregations.
    """
    if normalize_role(getattr(current_user, "role", None)) != "admin":
        if not check_class_membership(current_user, class_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You are not authorized to view analytics for class {class_id}.",
            )
    try:
        analytics_data = get_class_analytics(class_id=class_id, db=db)
        return analytics_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing class analytics for '{class_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute class analytics.",
        )


@router.get("/class/{class_id}/export")
@router.get("/classes/{class_id}/export", include_in_schema=False)
def export_analytics_for_class(
    class_id: str = Path(..., description="Class ID (UUID or string)"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Export class analytics as a downloadable CSV report.
    """
    if normalize_role(getattr(current_user, "role", None)) != "admin":
        if not check_class_membership(current_user, class_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You are not authorized to export analytics for class {class_id}.",
            )
    try:
        csv_content = export_class_analytics_csv(class_id=class_id, db=db)
        filename = f"class_{class_id[:8]}_analytics_report.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV analytics for '{class_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export class analytics.",
        )

