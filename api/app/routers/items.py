from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import (
    MIN_BORROW_FOR_POINTS,
    POINTS_RETURN_ON_TIME,
    award_points,
    borrowed_counts,
    check_badges,
    item_availability,
    log_activity,
    notify_waitlist,
)

router = APIRouter(tags=["Borrowing"])

# ระยะเวลายืมที่รองรับ -> จำนวนชั่วโมงก่อนครบกำหนดคืน
ALLOWED_DURATIONS = {"1 ชม.": 1, "1 วัน": 24, "3 วัน": 72}


def waitlist_info(db: Session, user_id: int) -> tuple[dict[int, int], dict[int, int]]:
    """(จำนวนคนรอของแต่ละ item, คิวที่เท่าไหร่ของฉันในแต่ละ item)"""
    rows = (
        db.query(models.ItemWaitlist.item_id, models.ItemWaitlist.user_id)
        .filter(models.ItemWaitlist.status == "waiting")
        .order_by(models.ItemWaitlist.created_at)
        .all()
    )
    counts: dict[int, int] = {}
    mine: dict[int, int] = {}
    for item_id, uid in rows:
        counts[item_id] = counts.get(item_id, 0) + 1
        if uid == user_id:
            mine[item_id] = counts[item_id]
    return counts, mine


def item_out(item: models.Item, borrowed: int, waiting: int = 0, my_pos=None) -> schemas.ItemOut:
    available, shown_status = item_availability(item, borrowed)
    return schemas.ItemOut(
        id=item.id,
        name=item.name,
        category=item.category,
        emoji=item.emoji,
        status=shown_status,
        quantity=item.quantity,
        borrowed_count=borrowed,
        available_count=available,
        waitlist_count=waiting,
        my_queue_position=my_pos,
        created_at=item.created_at,
    )


@router.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ของส่วนกลางพร้อมจำนวนที่ว่างตอนนี้ (ของที่นิติปิดใช้งานแล้วจะไม่แสดง)"""
    query = db.query(models.Item).filter(models.Item.status != "retired")
    if category and category != "ทั้งหมด":
        query = query.filter(models.Item.category == category)
    counts = borrowed_counts(db)
    waits, mine = waitlist_info(db, current_user.id)
    result = [
        item_out(i, counts.get(i.id, 0), waits.get(i.id, 0), mine.get(i.id))
        for i in query.order_by(models.Item.id).all()
    ]
    if status_filter:
        result = [i for i in result if i.status == status_filter]
    return result


@router.post("/items/{item_id}/borrow", response_model=schemas.BorrowRecordOut, status_code=status.HTTP_201_CREATED)
def borrow_item(
    item_id: int,
    payload: schemas.BorrowRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.duration_label not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail="ระยะเวลายืมไม่ถูกต้อง")

    # ล็อกแถวของ item ไว้จนจบ transaction — กันสองคนยืมชิ้นสุดท้ายพร้อมกัน
    item = db.query(models.Item).filter(models.Item.id == item_id).with_for_update().first()
    if not item or item.status == "retired":
        raise HTTPException(status_code=404, detail="ไม่พบสิ่งของนี้")
    if item.status == "repair":
        raise HTTPException(status_code=400, detail="ของชิ้นนี้กำลังซ่อมแซม")
    in_use = (
        db.query(models.BorrowRecord)
        .filter(models.BorrowRecord.item_id == item.id, models.BorrowRecord.status == "active")
        .count()
    )
    if in_use >= item.quantity:
        raise HTTPException(status_code=400, detail="ของชิ้นนี้ถูกยืมหมดแล้ว ลองใหม่ภายหลัง")

    now = datetime.utcnow()
    record = models.BorrowRecord(
        item_id=item.id,
        borrower_id=current_user.id,
        duration_label=payload.duration_label,
        borrowed_at=now,
        due_at=now + timedelta(hours=ALLOWED_DURATIONS[payload.duration_label]),
        status="active",
    )
    db.add(record)
    # ยืมได้แล้ว = ออกจากคิวของชิ้นนี้
    for w in db.query(models.ItemWaitlist).filter(
        models.ItemWaitlist.item_id == item.id,
        models.ItemWaitlist.user_id == current_user.id,
        models.ItemWaitlist.status.in_(["waiting", "notified"]),
    ):
        w.status = "done"
    log_activity(db, current_user.id, item.emoji, f"ยืม{item.name} {payload.duration_label}")
    check_badges(db, current_user.id)
    db.commit()
    db.refresh(record)
    return record


@router.get("/borrow/me", response_model=list[schemas.BorrowRecordOut])
def my_borrow_records(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.BorrowRecord)
        .filter(models.BorrowRecord.borrower_id == current_user.id)
        .order_by(models.BorrowRecord.borrowed_at.desc())
        .all()
    )


@router.post("/borrow/{record_id}/return", response_model=schemas.BorrowRecordOut)
def return_item(
    record_id: int,
    payload: Optional[schemas.ReturnRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.query(models.BorrowRecord).filter(models.BorrowRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ไม่พบรายการยืมนี้")
    if record.borrower_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์แจ้งคืนรายการนี้")
    if record.status != "active":
        raise HTTPException(status_code=400, detail="รายการนี้ถูกคืนไปแล้ว")

    now = datetime.utcnow()
    record.status = "returned"
    record.returned_at = now
    if payload:
        record.return_image = payload.image_data
        record.return_note = payload.note

    on_time = now <= record.due_at
    held_long_enough = (now - record.borrowed_at) >= MIN_BORROW_FOR_POINTS
    earns_points = on_time and held_long_enough
    if earns_points:
        award_points(db, current_user.id, POINTS_RETURN_ON_TIME, f"คืน{record.item.name}ตรงเวลา")
        log_activity(db, current_user.id, record.item.emoji, f"คืน{record.item.name}ตรงเวลา (+{POINTS_RETURN_ON_TIME} แต้ม)")
    elif on_time:
        log_activity(db, current_user.id, record.item.emoji, f"คืน{record.item.name}")
    else:
        log_activity(db, current_user.id, record.item.emoji, f"คืน{record.item.name} (เลยกำหนด)")

    notify_waitlist(db, record.item)
    check_badges(db, current_user.id)
    db.commit()
    db.refresh(record)
    result = schemas.BorrowRecordOut.model_validate(record)
    result.points_awarded = POINTS_RETURN_ON_TIME if earns_points else 0
    return result


# ---------------------------------------------------------------------------
# คิวรอของว่าง
# ---------------------------------------------------------------------------
@router.post("/items/{item_id}/waitlist", response_model=schemas.WaitlistOut, status_code=status.HTTP_201_CREATED)
def join_waitlist(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item or item.status == "retired":
        raise HTTPException(status_code=404, detail="ไม่พบสิ่งของนี้")
    _, available_status = item_availability(item, borrowed_counts(db).get(item.id, 0))
    if available_status == "available":
        raise HTTPException(status_code=400, detail="ของชิ้นนี้ยังว่างอยู่ กดยืมได้เลย")
    exists = db.query(models.ItemWaitlist).filter(
        models.ItemWaitlist.item_id == item.id,
        models.ItemWaitlist.user_id == current_user.id,
        models.ItemWaitlist.status == "waiting",
    ).first()
    if not exists:
        db.add(models.ItemWaitlist(item_id=item.id, user_id=current_user.id))
        db.commit()
    waits, mine = waitlist_info(db, current_user.id)
    return schemas.WaitlistOut(item_id=item.id, position=mine[item.id], waitlist_count=waits[item.id])


@router.delete("/items/{item_id}/waitlist", status_code=status.HTTP_204_NO_CONTENT)
def leave_waitlist(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    for w in db.query(models.ItemWaitlist).filter(
        models.ItemWaitlist.item_id == item_id,
        models.ItemWaitlist.user_id == current_user.id,
        models.ItemWaitlist.status == "waiting",
    ):
        w.status = "cancelled"
    db.commit()
    return None
