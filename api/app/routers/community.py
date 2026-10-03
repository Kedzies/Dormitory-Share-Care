from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import remind_due_soon, total_points

router = APIRouter(tags=["Points, Notifications & Activity"])


@router.get("/summary/me", response_model=schemas.HomeSummary)
def home_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ข้อมูลสำหรับหน้าแรก: แต้มรวม, จำนวนแจ้งเตือนที่ยังไม่อ่าน, กิจกรรมล่าสุด"""
    remind_due_soon(db, current_user.id)
    unread = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id, models.Notification.is_read.is_(False))
        .count()
    )
    recent = (
        db.query(models.Activity)
        .filter(models.Activity.user_id == current_user.id)
        .order_by(models.Activity.created_at.desc())
        .limit(3)
        .all()
    )
    return schemas.HomeSummary(
        username=current_user.username,
        points=total_points(db, current_user.id),
        unread_notifications=unread,
        recent_activity=recent,
    )


@router.get("/points/me", response_model=schemas.PointsSummary)
def my_points(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    history = (
        db.query(models.PointTransaction)
        .filter(models.PointTransaction.user_id == current_user.id)
        .order_by(models.PointTransaction.created_at.desc())
        .all()
    )
    return schemas.PointsSummary(total=total_points(db, current_user.id), history=history)


@router.get("/leaderboard", response_model=list[schemas.LeaderboardEntry])
def leaderboard(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """อันดับ "คนดีศรีหอพัก" นับเฉพาะแต้มที่ได้ในเดือนปัจจุบัน"""
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    rows = (
        db.query(models.User.username, func.sum(models.PointTransaction.amount).label("pts"))
        .join(models.PointTransaction, models.PointTransaction.user_id == models.User.id)
        .filter(models.PointTransaction.created_at >= month_start)
        .group_by(models.User.username)
        .order_by(func.sum(models.PointTransaction.amount).desc())
        .limit(limit)
        .all()
    )
    return [
        schemas.LeaderboardEntry(username=u, points=int(p or 0), is_me=(u == current_user.username))
        for u, p in rows
    ]


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    remind_due_soon(db, current_user.id)
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(50)
        .all()
    )


@router.post("/notifications/read-all", response_model=schemas.MessageResponse)
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id, models.Notification.is_read.is_(False)
    ).update({models.Notification.is_read: True})
    db.commit()
    return schemas.MessageResponse(message="อ่านแจ้งเตือนทั้งหมดแล้ว")


@router.get("/activity/me", response_model=list[schemas.ActivityOut])
def my_activity(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Activity)
        .filter(models.Activity.user_id == current_user.id)
        .order_by(models.Activity.created_at.desc())
        .limit(100)
        .all()
    )
