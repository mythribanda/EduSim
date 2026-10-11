"""
app/src/middleware/rbac.py — Role-Based Access Control (RBAC) dependencies for EduSim.

Exposes only:
- get_current_user
- require_admin
- require_self_or_admin(param="user_id")
"""

import logging
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.src.api.auth import get_current_user
from app.src.models.user import User

logger = logging.getLogger("EduSim.middleware.rbac")


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency enforcing that the current user has the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_self_or_admin(param: str = "user_id") -> Callable:
    """
    Dependency factory ensuring the requesting user is either:
    1. An admin, OR
    2. Accessing their own resource (matching path parameter `param`).
    """
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role == "admin":
            return current_user

        target_id = request.path_params.get(param)
        if target_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        if str(current_user.id) != str(target_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only access your own data.",
            )

        return current_user

    return dependency


__all__ = [
    "get_current_user",
    "require_admin",
    "require_self_or_admin",
]
