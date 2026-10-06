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
    check_badges(db, user_id)


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


def borrowed_counts(db: Session) -> dict[int, int]:
    """จำนวนชิ้นที่ถูกยืมอยู่ (ยังไม่คืน) ของแต่ละ item_id"""
    rows = (
        db.query(models.BorrowRecord.item_id, func.count(models.BorrowRecord.id))
        .filter(models.BorrowRecord.status == "active")
        .group_by(models.BorrowRecord.item_id)
        .all()
    )
    return {item_id: n for item_id, n in rows}


def item_availability(item: models.Item, borrowed: int) -> tuple[int, str]:
    """คืน (จำนวนที่ว่าง, สถานะที่แสดงผล) — สถานะ borrowed = ถูกยืมหมดทุกชิ้น"""
    if item.status != "available":
        return 0, item.status
    available = max((item.quantity or 0) - borrowed, 0)
    return available, ("available" if available > 0 else "borrowed")


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


# ---------------------------------------------------------------------------
# คิวรอของว่าง
# ---------------------------------------------------------------------------
def active_borrow_count(db: Session, item_id: int) -> int:
    return (
        db.query(models.BorrowRecord)
        .filter(models.BorrowRecord.item_id == item_id, models.BorrowRecord.status == "active")
        .count()
    )


def notify_waitlist(db: Session, item: models.Item) -> int:
    """แจ้งคนในคิว (ตามลำดับ) เท่ากับจำนวนชิ้นที่ว่างตอนนี้ — เรียกหลังคืนของ/เพิ่มจำนวน/เลิกซ่อม"""
    if item.status != "available":
        return 0
    db.flush()
    free = item.quantity - active_borrow_count(db, item.id)
    if free <= 0:
        return 0
    waiting = (
        db.query(models.ItemWaitlist)
        .filter(models.ItemWaitlist.item_id == item.id, models.ItemWaitlist.status == "waiting")
        .order_by(models.ItemWaitlist.created_at)
        .limit(free)
        .all()
    )
    now = datetime.utcnow()
    for w in waiting:
        w.status = "notified"
        w.notified_at = now
        notify(db, w.user_id, "🔔", f"{item.name} ว่างแล้ว!", "ถึงคิวของคุณแล้ว รีบไปกดยืมก่อนคนอื่นนะ")
    return len(waiting)


# ---------------------------------------------------------------------------
# เหรียญรางวัล — คำนวณจากข้อมูลจริง ได้แล้วเก็บไว้ใน user_badges และแจ้งเตือนครั้งเดียว
# ---------------------------------------------------------------------------
BADGES = [
    # code, ชื่อ, คำอธิบาย, สถิติที่ใช้วัด, เป้าหมาย
    ("first_borrow", "เริ่มต้นดี", "ยืมของส่วนกลางครั้งแรก", "borrows", 1),
    ("regular_10", "ขาประจำ", "ยืมของส่วนกลางครบ 10 ครั้ง", "borrows", 10),
    ("on_time_5", "ตรงต่อเวลา", "คืนของตรงเวลา 5 ครั้ง", "on_time", 5),
    ("on_time_20", "เป๊ะทุกนัด", "คืนของตรงเวลา 20 ครั้ง", "on_time", 20),
    ("handoff_5", "พลเมืองดี", "ส่งของฝากถึงมือผู้รับ 5 ครั้ง", "handoffs", 5),
    ("finder_1", "ฮีโร่ของหาย", "คืนของหายให้เจ้าของครั้งแรก", "found_returned", 1),
    ("finder_5", "นักสืบประจำหอ", "คืนของหายให้เจ้าของ 5 ครั้ง", "found_returned", 5),
    ("points_100", "คนดีศรีหอ", "สะสมแต้มความดีครบ 100 แต้ม", "points", 100),
]


def user_stats(db: Session, user_id: int) -> dict[str, int]:
    BR = models.BorrowRecord
    return {
        "borrows": db.query(BR).filter(BR.borrower_id == user_id).count(),
        "on_time": db.query(BR).filter(
            BR.borrower_id == user_id,
            BR.status == "returned",
            BR.returned_at <= BR.due_at,
            BR.returned_at - BR.borrowed_at >= MIN_BORROW_FOR_POINTS,
        ).count(),
        "handoffs": db.query(models.Deposit).filter(
            models.Deposit.depositor_id == user_id, models.Deposit.status == "collected"
        ).count(),
        "found_returned": db.query(models.FoundItem).filter(
            models.FoundItem.finder_id == user_id, models.FoundItem.status == "returned"
        ).count(),
        "points": total_points(db, user_id),
    }


def check_badges(db: Session, user_id: int) -> dict[str, int]:
    """มอบเหรียญที่ถึงเป้าแล้วแต่ยังไม่เคยได้ + แจ้งเตือน คืนค่าสถิติไว้ใช้ต่อ"""
    db.flush()  # ให้เห็นการเปลี่ยนแปลงที่ยังไม่ commit ของ request นี้
    stats = user_stats(db, user_id)
    owned = {b.code for b in db.query(models.UserBadge).filter(models.UserBadge.user_id == user_id)}
    for code, title, desc, stat, target in BADGES:
        if code not in owned and stats[stat] >= target:
            db.add(models.UserBadge(user_id=user_id, code=code))
            notify(db, user_id, "🏅", f"ได้รับเหรียญ \"{title}\"", desc)
    return stats
