"""Admin routes — user management (admin only)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.dataset import DatasetFile
from app.models.prediction import PredictionLog
from app.models.training_job import JobStatus, TrainingJob
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    import math

    offset = (page - 1) * per_page
    stmt = (
        select(User, func.count(User.id).over().label("total_count"))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [
        UserListItem(
            id=u.User.id,
            email=u.User.email,
            full_name=u.User.full_name,
            role=u.User.role.value if isinstance(u.User.role, UserRole) else u.User.role,
            is_active=u.User.is_active,
            created_at=u.User.created_at.isoformat(),
        )
        for u in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot modify own account")

    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role") from None

    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)

    return UserListItem(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await db.delete(user)
    await db.commit()


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Platform usage statistics. Admin only."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar() or 0  # noqa: E712
    total_predictions = (await db.execute(select(func.count(PredictionLog.id)))).scalar() or 0
    total_training_jobs = (await db.execute(select(func.count(TrainingJob.id)))).scalar() or 0
    completed_jobs = (
        await db.execute(select(func.count(TrainingJob.id)).where(TrainingJob.status == JobStatus.completed))
    ).scalar() or 0
    total_datasets = (await db.execute(select(func.count(DatasetFile.id)))).scalar() or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_predictions": total_predictions,
        "total_training_jobs": total_training_jobs,
        "completed_jobs": completed_jobs,
        "total_datasets": total_datasets,
    }
