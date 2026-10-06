import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import (
    POINTS_DEPOSIT_HANDED_OFF,
    award_points,
    find_user_by_username,
    log_activity,
    notify,
)

router = APIRouter(tags=["Deposits"])


def _new_code(db: Session) -> str:
    while True:
        code = "DP-" + secrets.token_hex(3).upper()
        if not db.query(models.Deposit).filter(models.Deposit.code == code).first():
            return code


def _to_out(db: Session, d: models.Deposit, me: models.User) -> schemas.DepositOut:
    return schemas.DepositOut(
        id=d.id,
        code=d.code,
        item_name=d.item_name,
        note=d.note,
        eta=d.eta,
        image_data=d.image_data,
        status=d.status,
        depositor_username=d.depositor.username,
        recipient_username=d.recipient_username,
        recipient_registered=find_user_by_username(db, d.recipient_username) is not None,
        direction="sent" if d.depositor_id == me.id else "received",
        created_at=d.created_at,
        collected_at=d.collected_at,
    )


@router.get("/deposits/me", response_model=list[schemas.DepositOut])
def my_deposits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """รายการที่ฉันฝากไว้ + รายการที่มีคนฝากให้ห้องฉัน"""
    deposits = (
        db.query(models.Deposit)
        .filter(
            or_(
                models.Deposit.depositor_id == current_user.id,
                models.Deposit.recipient_username == current_user.username,
            )
        )
        .order_by(models.Deposit.created_at.desc())
        .all()
    )
    return [_to_out(db, d, current_user) for d in deposits]


@router.post("/deposits", response_model=schemas.DepositOut, status_code=status.HTTP_201_CREATED)
def create_deposit(
    payload: schemas.DepositCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    recipient = payload.recipient_username.strip()
    if recipient == current_user.username:
        raise HTTPException(status_code=400, detail="ไม่สามารถฝากของให้ห้องตัวเองได้")

    deposit = models.Deposit(
        code=_new_code(db),
        depositor_id=current_user.id,
        recipient_username=recipient,
        item_name=payload.item_name,
        note=payload.note,
        eta=payload.eta,
        image_data=payload.image_data,
        status="waiting",
    )
    db.add(deposit)

    recipient_user = find_user_by_username(db, recipient)
    if recipient_user:
        notify(
            db, recipient_user.id, "📦", "มีของฝากถึงคุณ",
            f"{payload.item_name} จากห้อง {current_user.username}"
            + (f" · นัดรับ {payload.eta}" if payload.eta else ""),
        )
    log_activity(db, current_user.id, "📦", f"ฝาก{payload.item_name}ให้ห้อง {recipient}")
    db.commit()
    db.refresh(deposit)
    return _to_out(db, deposit, current_user)


def _get_deposit(db: Session, deposit_id: int) -> models.Deposit:
    d = db.query(models.Deposit).filter(models.Deposit.id == deposit_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="ไม่พบรายการฝากนี้")
    return d


@router.post("/deposits/{deposit_id}/collect", response_model=schemas.DepositOut)
def collect_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ยืนยันว่าของถึงมือผู้รับแล้ว — กดได้ทั้งผู้รับ หรือผู้ฝาก (กรณีผู้รับยังไม่มีบัญชีในระบบ)"""
    d = _get_deposit(db, deposit_id)
    is_depositor = d.depositor_id == current_user.id
    is_recipient = d.recipient_username == current_user.username
    if not (is_depositor or is_recipient):
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์ยืนยันรายการนี้")
    if d.status != "waiting":
        raise HTTPException(status_code=400, detail="รายการนี้ไม่ได้อยู่ในสถานะรอรับแล้ว")

    mark_collected(db, d, notify_depositor=is_recipient)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, current_user)


def mark_collected(db: Session, d: models.Deposit, notify_depositor: bool) -> None:
    """ปิดรายการฝากว่าส่งถึงมือแล้ว + ให้แต้มผู้ฝาก (ไม่ commit)"""
    d.status = "collected"
    d.collected_at = datetime.utcnow()

    award_points(db, d.depositor_id, POINTS_DEPOSIT_HANDED_OFF, f"ส่ง{d.item_name}ถึงห้อง {d.recipient_username} เรียบร้อย")
    log_activity(db, d.depositor_id, "✅", f"{d.item_name} ถึงมือห้อง {d.recipient_username} แล้ว (+{POINTS_DEPOSIT_HANDED_OFF} แต้ม)")

    recipient_user = find_user_by_username(db, d.recipient_username)
    if recipient_user:
        log_activity(db, recipient_user.id, "📥", f"รับ{d.item_name}จากห้อง {d.depositor.username}")
    if notify_depositor:
        notify(db, d.depositor_id, "📥", "ผู้รับได้รับของแล้ว", f"ห้อง {d.recipient_username} รับ{d.item_name}เรียบร้อย")
    elif recipient_user:
        notify(db, recipient_user.id, "📥", "ยืนยันรับของแล้ว", f"{d.item_name} จากห้อง {d.depositor.username}")


@router.post("/deposits/{deposit_id}/cancel", response_model=schemas.DepositOut)
def cancel_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    d = _get_deposit(db, deposit_id)
    if d.depositor_id != current_user.id:
        raise HTTPException(status_code=403, detail="ยกเลิกได้เฉพาะผู้ฝากเท่านั้น")
    if d.status != "waiting":
        raise HTTPException(status_code=400, detail="รายการนี้ไม่ได้อยู่ในสถานะรอรับแล้ว")

    d.status = "cancelled"
    recipient_user = find_user_by_username(db, d.recipient_username)
    if recipient_user:
        notify(db, recipient_user.id, "🚫", "รายการฝากถูกยกเลิก", f"{d.item_name} จากห้อง {current_user.username}")
    log_activity(db, current_user.id, "🚫", f"ยกเลิกการฝาก{d.item_name}")
    db.commit()
    db.refresh(d)
    return _to_out(db, d, current_user)
