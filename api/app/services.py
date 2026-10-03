"""ฟังก์ชันกลางที่ทุกฟีเจอร์ใช้ร่วมกัน: ให้แต้ม, ส่งแจ้งเตือน, บันทึกประวัติ

ทุกฟังก์ชันแค่ db.add() ไม่ commit เอง — ให้ router เป็นคน commit ครั้งเดียวตอนจบ
เพื่อให้การเปลี่ยนแปลงทั้งหมดของ 1 request สำเร็จหรือล้มเหลวพร้อมกัน
"""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

# ---- กติกาแต้มความดี ----
POINTS_RETURN_ON_TIME = 10      # คืนของส่วนกลางตรงเวลา
POINTS_DEPOSIT_HANDED_OFF = 5   # ของที่ฝากถูกส่งถึงมือผู้รับ
POINTS_FOUND_RETURNED = 20      # เก็บของหายได้และคืนถึงเจ้าของ

# กันการปั๊มแต้ม: ต้องยืมไว้อย่างน้อยเท่านี้ การคืนตรงเวลาถึงจะได้แต้ม
MIN_BORROW_FOR_POINTS = timedelta(minutes=10)

REMIND_BEFORE = timedelta(hours=2)


def award_points(db: Session, user_id: int, amount: int, reason: str) -> None:
    db.add(models.PointTransaction(user_id=user_id, amount=amount, reason=reason))
    notify(db, user_id, "🎉", f"คุณได้รับ {amount} แต้ม!", reason)


def notify(db: Session, user_id: int, icon: str, title: str, body: str = "") -> None:
    db.add(models.Notification(user_id=user_id, icon=icon, title=title, body=body))


def log_activity(db: Session, user_id: int, icon: str, text: str) -> None:
    db.add(models.Activity(user_id=user_id, icon=icon, text=text))


def total_points(db: Session, user_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.PointTransaction.amount), 0))
        .filter(models.PointTransaction.user_id == user_id)
        .scalar()
    )
    return int(total or 0)


def find_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def remind_due_soon(db: Session, user_id: int) -> None:
    """สร้างแจ้งเตือน "ใกล้ถึงเวลาคืน" ให้รายการยืมที่จะครบกำหนดภายใน 2 ชม. (ครั้งเดียวต่อรายการ)

    เรียกตอนผู้ใช้เปิดแอป/ดูแจ้งเตือน แทนการใช้ background job เพื่อให้ระบบเรียบง่าย
    """
    now = datetime.utcnow()
    records = (
        db.query(models.BorrowRecord)
        .filter(
            models.BorrowRecord.borrower_id == user_id,
            models.BorrowRecord.status == "active",
            models.BorrowRecord.reminded.isnot(True),
            models.BorrowRecord.due_at <= now + REMIND_BEFORE,
        )
        .all()
    )
    for r in records:
        if r.due_at < now:
            notify(db, user_id, "⚠️", "เลยกำหนดคืนแล้ว", f"{r.item.name} — กรุณานำมาคืนโดยเร็ว")
        else:
            notify(db, user_id, "⏰", "ใกล้ถึงเวลาคืนแล้ว", f"{r.item.name} — ครบกำหนดภายใน 2 ชม.")
        r.reminded = True
    if records:
        db.commit()
