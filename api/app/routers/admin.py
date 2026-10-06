"""endpoint สำหรับนิติบุคคล / ผู้ดูแลหอพัก — ทุกเส้นต้องเป็นบัญชี is_admin"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_admin
from ..services import borrowed_counts, log_activity, notify, total_points
from .items import item_out

router = APIRouter(prefix="/admin", tags=["Admin (นิติบุคคล)"])


# ---------------------------------------------------------------------------
# ภาพรวม
# ---------------------------------------------------------------------------
@router.get("/overview", response_model=schemas.AdminOverview)
def overview(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    now = datetime.utcnow()
    counts = borrowed_counts(db)
    items = db.query(models.Item).filter(models.Item.status != "retired").all()
    active = db.query(models.BorrowRecord).filter(models.BorrowRecord.status == "active")
    units_total = sum(i.quantity for i in items)
    units_borrowed = sum(counts.get(i.id, 0) for i in items)
    units_available = sum(
        max(i.quantity - counts.get(i.id, 0), 0) for i in items if i.status == "available"
    )
    return schemas.AdminOverview(
        residents=db.query(models.User).filter(models.User.is_active.is_(True), models.User.is_admin.isnot(True)).count(),
        item_types=len(items),
        units_total=units_total,
        units_borrowed=units_borrowed,
        units_available=units_available,
        items_in_repair=sum(1 for i in items if i.status == "repair"),
        active_borrows=active.count(),
        overdue_borrows=active.filter(models.BorrowRecord.due_at < now).count(),
        deposits_waiting=db.query(models.Deposit).filter(models.Deposit.status == "waiting").count(),
        found_open=db.query(models.FoundItem).filter(models.FoundItem.status == "open").count(),
        lost_open=db.query(models.LostReport).filter(models.LostReport.status == "open").count(),
    )


# ---------------------------------------------------------------------------
# คลังของส่วนกลาง
# ---------------------------------------------------------------------------
def _get_item(db: Session, item_id: int) -> models.Item:
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="ไม่พบสิ่งของนี้")
    return item


@router.get("/items", response_model=list[schemas.ItemOut])
def all_items(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    """ของทุกชิ้น รวมที่ปิดใช้งานแล้ว"""
    counts = borrowed_counts(db)
    return [item_out(i, counts.get(i.id, 0)) for i in db.query(models.Item).order_by(models.Item.id).all()]


@router.post("/items", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: schemas.ItemCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    item = models.Item(
        name=payload.name,
        category=payload.category,
        emoji=payload.emoji,
        quantity=payload.quantity,
        status="available",
        owner_id=admin.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_out(item, 0)


@router.put("/items/{item_id}", response_model=schemas.ItemOut)
def update_item(
    item_id: int,
    payload: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    item = _get_item(db, item_id)
    borrowed = borrowed_counts(db).get(item.id, 0)
    if payload.quantity is not None and payload.quantity < borrowed:
        raise HTTPException(
            status_code=400,
            detail=f"ตอนนี้ถูกยืมอยู่ {borrowed} ชิ้น ตั้งจำนวนทั้งหมดน้อยกว่านี้ไม่ได้",
        )
    for field in ("name", "category", "emoji", "quantity", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item_out(item, borrowed)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    item = _get_item(db, item_id)
    if db.query(models.BorrowRecord).filter(models.BorrowRecord.item_id == item.id).first():
        raise HTTPException(
            status_code=400,
            detail="ของชิ้นนี้มีประวัติการยืมแล้ว ลบไม่ได้ — ใช้ \"ปิดใช้งาน\" แทนเพื่อเก็บประวัติไว้",
        )
    db.delete(item)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# การยืม-คืน
# ---------------------------------------------------------------------------
def _borrow_out(r: models.BorrowRecord, now: datetime) -> schemas.AdminBorrowOut:
    return schemas.AdminBorrowOut(
        id=r.id,
        item_id=r.item_id,
        item_name=r.item.name,
        item_emoji=r.item.emoji,
        borrower_username=r.borrower.username,
        borrower_name=r.borrower.full_name,
        duration_label=r.duration_label,
        borrowed_at=r.borrowed_at,
        due_at=r.due_at,
        returned_at=r.returned_at,
        status=r.status,
        overdue=r.status == "active" and r.due_at < now,
        return_note=r.return_note,
    )


@router.get("/borrows", response_model=list[schemas.AdminBorrowOut])
def all_borrows(
    status_filter: str = Query("active", alias="status", description="active | returned | all"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    query = db.query(models.BorrowRecord)
    if status_filter != "all":
        query = query.filter(models.BorrowRecord.status == status_filter)
    if status_filter == "active":
        query = query.order_by(models.BorrowRecord.due_at)  # ใกล้ครบกำหนด/เลยกำหนดขึ้นก่อน
    else:
        query = query.order_by(models.BorrowRecord.borrowed_at.desc())
    now = datetime.utcnow()
    return [_borrow_out(r, now) for r in query.limit(limit).all()]


@router.post("/borrows/{record_id}/return", response_model=schemas.AdminBorrowOut)
def force_return(record_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    """นิติรับของคืนแทน (เช่น ผู้ยืมเอามาคืนที่ออฟฟิศ) — ไม่ให้แต้ม"""
    record = db.query(models.BorrowRecord).filter(models.BorrowRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ไม่พบรายการยืมนี้")
    if record.status != "active":
        raise HTTPException(status_code=400, detail="รายการนี้ถูกคืนไปแล้ว")
    record.status = "returned"
    record.returned_at = datetime.utcnow()
    record.return_note = "นิติบุคคลบันทึกรับคืน"
    notify(db, record.borrower_id, "✅", "นิติบุคคลบันทึกรับคืนแล้ว", record.item.name)
    log_activity(db, record.borrower_id, record.item.emoji, f"คืน{record.item.name} (บันทึกโดยนิติ)")
    db.commit()
    db.refresh(record)
    return _borrow_out(record, datetime.utcnow())


# ---------------------------------------------------------------------------
# ฝากของ
# ---------------------------------------------------------------------------
@router.get("/deposits", response_model=list[schemas.AdminDepositOut])
def all_deposits(
    status_filter: str = Query("waiting", alias="status", description="waiting | collected | cancelled | all"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    query = db.query(models.Deposit)
    if status_filter != "all":
        query = query.filter(models.Deposit.status == status_filter)
    deposits = query.order_by(models.Deposit.created_at.desc()).limit(limit).all()
    return [
        schemas.AdminDepositOut(
            id=d.id, code=d.code, item_name=d.item_name,
            depositor_username=d.depositor.username, recipient_username=d.recipient_username,
            eta=d.eta, note=d.note, status=d.status,
            created_at=d.created_at, collected_at=d.collected_at,
        )
        for d in deposits
    ]


# ---------------------------------------------------------------------------
# ผู้พักอาศัย
# ---------------------------------------------------------------------------
@router.get("/users", response_model=list[schemas.AdminUserOut])
def all_users(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    active_by_user: dict[int, int] = {}
    for (uid,) in (
        db.query(models.BorrowRecord.borrower_id).filter(models.BorrowRecord.status == "active").all()
    ):
        active_by_user[uid] = active_by_user.get(uid, 0) + 1
    return [
        schemas.AdminUserOut(
            id=u.id, username=u.username, full_name=u.full_name, email=u.email,
            is_active=bool(u.is_active), is_admin=bool(u.is_admin),
            points=total_points(db, u.id), active_borrows=active_by_user.get(u.id, 0),
            created_at=u.created_at,
        )
        for u in db.query(models.User).order_by(models.User.username).all()
    ]


@router.post("/users/{user_id}/active", response_model=schemas.MessageResponse)
def set_user_active(
    user_id: int,
    payload: schemas.SetActiveRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="ปิดใช้งานบัญชีของตัวเองไม่ได้")
    user.is_active = payload.is_active
    db.commit()
    return schemas.MessageResponse(
        message=f"{'เปิด' if payload.is_active else 'ปิด'}ใช้งานบัญชีห้อง {user.username} แล้ว"
    )


# ---------------------------------------------------------------------------
# ประกาศถึงทุกห้อง
# ---------------------------------------------------------------------------
@router.post("/announcements", response_model=schemas.AnnouncementResult)
def announce(
    payload: schemas.AnnouncementRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    users = db.query(models.User).filter(models.User.is_active.is_(True), models.User.id != admin.id).all()
    for u in users:
        notify(db, u.id, "📢", f"ประกาศจากนิติ: {payload.title}"[:150], payload.body or "")
    db.commit()
    return schemas.AnnouncementResult(sent=len(users))
