from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.feedback import Feedback
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.schemas.usage import (
    AdminStats,
    AdminUserSummary,
    AdminUserUpdate,
    DailyAdminStats,
    UsageMe,
)
from app.services.usage_service import (
    month_analysis_count,
    month_start_utc,
    next_month_start_utc,
)

usage_router = APIRouter(prefix="/usage", tags=["Usage"])
admin_router = APIRouter(prefix="/admin", tags=["Administration"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé à l’administration.")
    return current_user


@usage_router.get("/me", response_model=UsageMe)
def get_my_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = month_start_utc().replace(tzinfo=None)
    totals = db.query(
        func.coalesce(func.sum(UsageEvent.tokens_in), 0),
        func.coalesce(func.sum(UsageEvent.tokens_out), 0),
    ).filter(
        UsageEvent.user_id == current_user.id,
        UsageEvent.status == "success",
        UsageEvent.created_at >= start,
    ).one()
    return UsageMe(
        used=month_analysis_count(db, current_user.id),
        quota=current_user.monthly_quota,
        tokens_in=int(totals[0]),
        tokens_out=int(totals[1]),
        reset_at=next_month_start_utc(),
    )


def _admin_user_summary(db: Session, user: User) -> AdminUserSummary:
    start = month_start_utc().replace(tzinfo=None)
    usage = db.query(
        func.coalesce(func.sum(UsageEvent.tokens_in), 0),
        func.coalesce(func.sum(UsageEvent.tokens_out), 0),
        func.max(UsageEvent.created_at),
    ).filter(
        UsageEvent.user_id == user.id,
        UsageEvent.created_at >= start,
    ).one()
    last_usage = db.query(func.max(UsageEvent.created_at)).filter(
        UsageEvent.user_id == user.id,
    ).scalar()
    last_analysis = db.query(func.max(Analysis.created_at)).filter(Analysis.user_id == user.id).scalar()
    last_activity = max(
        (value for value in (last_usage, last_analysis) if value is not None),
        default=None,
    )
    return AdminUserSummary(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        monthly_quota=user.monthly_quota,
        analyses_used=month_analysis_count(db, user.id),
        tokens_in=int(usage[0] or 0),
        tokens_out=int(usage[1] or 0),
        last_activity=last_activity,
    )


@admin_router.get("/users", response_model=list[AdminUserSummary])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return [
        _admin_user_summary(db, user)
        for user in db.query(User).order_by(User.created_at.desc()).all()
    ]


@admin_router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Au moins un champ doit être fourni.")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if user.id == admin.id and changes.get("is_active") is False:
        raise HTTPException(status_code=422, detail="Vous ne pouvez pas désactiver votre propre compte.")
    if "monthly_quota" in changes:
        user.monthly_quota = changes["monthly_quota"]
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    db.commit()
    db.refresh(user)
    return _admin_user_summary(db, user)


@admin_router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day)
    window_start = today_start - timedelta(days=13)
    events = db.query(
        func.date(UsageEvent.created_at).label("day"),
        func.count(UsageEvent.id).filter(
            UsageEvent.type == "analysis",
            UsageEvent.status == "success",
        ).label("analyses"),
        func.count(UsageEvent.id).filter(UsageEvent.status == "error").label("errors"),
        func.coalesce(func.sum(UsageEvent.tokens_in), 0).label("tokens_in"),
        func.coalesce(func.sum(UsageEvent.tokens_out), 0).label("tokens_out"),
    ).filter(
        UsageEvent.created_at >= window_start,
    ).group_by(func.date(UsageEvent.created_at)).all()
    daily = [
        DailyAdminStats(
            date=str(row.day),
            analyses=int(row.analyses),
            errors=int(row.errors),
            tokens=int(row.tokens_in + row.tokens_out),
        )
        for row in events
    ]
    usage_totals = db.query(
        func.count(UsageEvent.id),
        func.count(UsageEvent.id).filter(UsageEvent.status == "error"),
        func.coalesce(func.sum(UsageEvent.tokens_in), 0),
        func.coalesce(func.sum(UsageEvent.tokens_out), 0),
    ).filter(UsageEvent.created_at >= window_start).one()
    votes = db.query(func.count(Feedback.id), func.count(Feedback.id).filter(Feedback.rating == 1)).one()
    today_analyses = db.query(func.count(Analysis.id)).filter(Analysis.created_at >= today_start).scalar() or 0
    event_count = int(usage_totals[0] or 0)
    return AdminStats(
        analyses_today=int(today_analyses),
        error_rate=(int(usage_totals[1] or 0) / event_count) if event_count else 0.0,
        like_rate=(int(votes[1] or 0) / int(votes[0])) if votes[0] else 0.0,
        tokens_in=int(usage_totals[2] or 0),
        tokens_out=int(usage_totals[3] or 0),
        daily=daily,
    )
