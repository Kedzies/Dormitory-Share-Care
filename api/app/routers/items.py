from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import MIN_BORROW_FOR_POINTS, POINTS_RETURN_ON_TIME, award_points, log_activity

router = APIRouter(tags=["Borrowing"])

# ระยะเวลายืมที่รองรับ -> จำนวนชั่วโมงก่อนครบกำหนดคืน
ALLOWED_DURATIONS = {"1 ชม.": 1, "1 วัน": 24, "3 วัน": 72}


@router.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Item)
    if category and category != "ทั้งหมด":
        query = query.filter(models.Item.category == category)
    if status_filter:
        query = query.filter(models.Item.status == status_filter)
    return query.order_by(models.Item.id).all()


@router.post("/items", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = models.Item(
        name=payload.name,
        category=payload.category,
        emoji=payload.emoji,
        status="available",
        owner_id=current_user.id,
    )
    db.add(item)
    log_activity(db, current_user.id, item.emoji, f"เพิ่ม {item.name} เป็นของส่วนกลาง")
    db.commit()
    db.refresh(item)
    return item


@router.post("/items/{item_id}/borrow", response_model=schemas.BorrowRecordOut, status_code=status.HTTP_201_CREATED)
def borrow_item(
    item_id: int,
    payload: schemas.BorrowRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.duration_label not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail="ระยะเวลายืมไม่ถูกต้อง")

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="ไม่พบสิ่งของนี้")
    if item.status != "available":
        raise HTTPException(status_code=400, detail="ของชิ้นนี้ไม่ว่างในขณะนี้")

    now = datetime.utcnow()
    record = models.BorrowRecord(
        item_id=item.id,
        borrower_id=current_user.id,
        duration_label=payload.duration_label,
        borrowed_at=now,
        due_at=now + timedelta(hours=ALLOWED_DURATIONS[payload.duration_label]),
        status="active",
    )
    item.status = "borrowed"
    db.add(record)
    log_activity(db, current_user.id, item.emoji, f"ยืม{item.name} {payload.duration_label}")
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
    record.item.status = "available"

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

    db.commit()
    db.refresh(record)
    result = schemas.BorrowRecordOut.model_validate(record)
    result.points_awarded = POINTS_RETURN_ON_TIME if earns_points else 0
    return result
