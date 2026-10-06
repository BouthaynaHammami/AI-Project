import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.analysis import Analysis
from app.models.share_link import ShareLink
from app.models.user import User
from app.schemas.share import (
    PublicAnalysis,
    ShareLinkCreate,
    ShareLinkCreated,
    ShareLinkSummary,
)

analysis_router = APIRouter(prefix="/analysis", tags=["Partage"])
public_router = APIRouter(prefix="/public", tags=["Partage public"])
NOT_FOUND = "Lien de partage introuvable."


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _owned_analysis(analysis_id: int, db: Session, user: User) -> Analysis:
    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id,
            Analysis.deleted_at.is_(None),
        )
        .first()
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    return analysis


@analysis_router.post(
    "/{analysis_id}/share",
    response_model=ShareLinkCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_share_link(
    analysis_id: int,
    payload: ShareLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = _owned_analysis(analysis_id, db, current_user)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    share = ShareLink(
        analysis_id=analysis.id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        created_by=current_user.id,
        created_at=now,
        expires_at=now + timedelta(days=payload.expires_in_days),
        view_count=0,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return ShareLinkCreated(id=share.id, token=token, expires_at=share.expires_at)


@analysis_router.get(
    "/{analysis_id}/share",
    response_model=list[ShareLinkSummary],
)
def list_share_links(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_analysis(analysis_id, db, current_user)
    now = datetime.now(timezone.utc)
    return (
        db.query(ShareLink)
        .filter(
            ShareLink.analysis_id == analysis_id,
            ShareLink.revoked_at.is_(None),
            ShareLink.expires_at > now,
        )
        .order_by(ShareLink.created_at.desc())
        .all()
    )


@analysis_router.delete(
    "/{analysis_id}/share/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_share_link(
    analysis_id: int,
    share_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_analysis(analysis_id, db, current_user)
    share = (
        db.query(ShareLink)
        .filter(ShareLink.id == share_id, ShareLink.analysis_id == analysis_id)
        .first()
    )
    if share is None:
        raise HTTPException(status_code=404, detail="Lien de partage introuvable.")
    if share.revoked_at is None:
        share.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@analysis_router.delete(
    "/{analysis_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_all_share_links(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_analysis(analysis_id, db, current_user)
    db.query(ShareLink).filter(
        ShareLink.analysis_id == analysis_id,
        ShareLink.revoked_at.is_(None),
    ).update(
        {ShareLink.revoked_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.get(
    "/analysis/{token}",
    response_model=PublicAnalysis,
)
@limiter.limit("30/minute")
def get_public_analysis(
    request: Request,
    token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    share = db.query(ShareLink).filter(ShareLink.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)
    if (
        share is None
        or share.revoked_at is not None
        or _utc(share.expires_at) <= now
    ):
        raise HTTPException(
            status_code=404,
            detail=NOT_FOUND,
            headers={
                "X-Robots-Tag": "noindex, nofollow, noarchive",
                "Cache-Control": "no-store, no-cache, must-revalidate, private",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
            },
        )

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == share.analysis_id,
            Analysis.deleted_at.is_(None),
        )
        .first()
    )
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=NOT_FOUND,
            headers={
                "X-Robots-Tag": "noindex, nofollow, noarchive",
                "Cache-Control": "no-store, no-cache, must-revalidate, private",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
            },
        )

    db.execute(
        update(ShareLink)
        .where(ShareLink.id == share.id)
        .values(view_count=ShareLink.view_count + 1)
    )
    db.commit()
    return PublicAnalysis(
        question=analysis.question,
        answer=analysis.answer,
        chart_config=analysis.chart_config,
        created_at=analysis.created_at,
    )
