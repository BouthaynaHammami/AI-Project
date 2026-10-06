from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.usage_event import UsageEvent
from app.models.user import User


def month_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return datetime(current.year, current.month, 1, tzinfo=timezone.utc)


def next_month_start_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def month_analysis_count(db: Session, user_id: int, now: datetime | None = None) -> int:
    start = month_start_utc(now).replace(tzinfo=None)
    event_count = int(
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.user_id == user_id,
            UsageEvent.type == "analysis",
            UsageEvent.status == "success",
            UsageEvent.created_at >= start,
        )
        .scalar()
        or 0
    )
    persisted_analyses = int(
        db.query(func.count(Analysis.id))
        .filter(Analysis.user_id == user_id, Analysis.created_at >= start)
        .scalar()
        or 0
    )
    return max(event_count, persisted_analyses)


def check_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    used = month_analysis_count(db, current_user.id)
    if used >= current_user.monthly_quota:
        reset_at = next_month_start_utc()
        retry_after = max(1, int((reset_at - datetime.now(timezone.utc)).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Votre quota mensuel de {current_user.monthly_quota} analyses est atteint. "
                "Il sera réinitialisé au début du mois prochain."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    return current_user


def add_usage_event(
    db: Session,
    user_id: int,
    event_type: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str | None = None,
    status: str = "success",
    created_at: datetime | None = None,
) -> UsageEvent:
    event = UsageEvent(
        user_id=user_id,
        type=event_type,
        tokens_in=max(0, int(tokens_in)),
        tokens_out=max(0, int(tokens_out)),
        model=model,
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(event)
    return event
