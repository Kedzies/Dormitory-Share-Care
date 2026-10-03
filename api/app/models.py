from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)
    full_name = Column(String(120), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# ยืม-คืนของส่วนกลาง
# ---------------------------------------------------------------------------
class Item(Base):
    """ของส่วนกลางที่เปิดให้ยืม-คืนได้ในหอพัก"""

    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="อื่นๆ")
    emoji = Column(String(10), default="📦")
    # available | borrowed | repair
    status = Column(String(20), nullable=False, default="available")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BorrowRecord(Base):
    """ประวัติการยืม-คืนของแต่ละครั้ง"""

    __tablename__ = "borrow_records"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    borrower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    duration_label = Column(String(20), nullable=False)
    borrowed_at = Column(DateTime, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    # active | returned
    status = Column(String(20), nullable=False, default="active")
    return_image = Column(Text, nullable=True)  # รูปสภาพของตอนคืน (data URL)
    return_note = Column(String(300), nullable=True)
    reminded = Column(Boolean, default=False)  # ส่งแจ้งเตือน "ใกล้ถึงเวลาคืน" ไปแล้วหรือยัง

    item = relationship("Item")
    borrower = relationship("User")


# ---------------------------------------------------------------------------
# ฝากของ
# ---------------------------------------------------------------------------
class Deposit(Base):
    """รายการฝากของให้ห้องอื่น (กุญแจ, พัสดุ ฯลฯ)"""

    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    depositor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_username = Column(String(50), index=True, nullable=False)
    item_name = Column(String(100), nullable=False)
    note = Column(String(300), nullable=True)
    eta = Column(String(100), nullable=True)
    image_data = Column(Text, nullable=True)
    # waiting | collected | cancelled
    status = Column(String(20), nullable=False, default="waiting")
    created_at = Column(DateTime, default=datetime.utcnow)
    collected_at = Column(DateTime, nullable=True)

    depositor = relationship("User")


# ---------------------------------------------------------------------------
# ของหายได้คืน
# ---------------------------------------------------------------------------
class FoundItem(Base):
    """ของที่มีคนเก็บได้ รอเจ้าของมารับ"""

    __tablename__ = "found_items"

    id = Column(Integer, primary_key=True, index=True)
    finder_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_name = Column(String(100), nullable=False)
    location = Column(String(150), nullable=False)
    found_time = Column(String(100), nullable=True)
    emoji = Column(String(10), default="🎁")
    image_data = Column(Text, nullable=True)
    # open | returned
    status = Column(String(20), nullable=False, default="open")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    returned_at = Column(DateTime, nullable=True)

    finder = relationship("User", foreign_keys=[finder_id])
    owner = relationship("User", foreign_keys=[owner_id])


class LostReport(Base):
    """ประกาศตามหาของหาย"""

    __tablename__ = "lost_reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_name = Column(String(100), nullable=False)
    location_time = Column(String(150), nullable=False)
    emoji = Column(String(10), default="🔍")
    image_data = Column(Text, nullable=True)
    # open | resolved
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    reporter = relationship("User")


class Claim(Base):
    """คำขอรับของ ("นี่คือของฉัน") — ผู้ที่เก็บของได้เป็นคนอนุมัติ"""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    found_item_id = Column(Integer, ForeignKey("found_items.id"), nullable=False)
    claimant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    detail = Column(String(500), nullable=False)
    # pending | approved | rejected
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    found_item = relationship("FoundItem")
    claimant = relationship("User")


# ---------------------------------------------------------------------------
# แต้มความดี / แจ้งเตือน / ประวัติกิจกรรม
# ---------------------------------------------------------------------------
class PointTransaction(Base):
    """สมุดบัญชีแต้ม: แต้มรวม = ผลรวมของ amount ทุกแถวของผู้ใช้"""

    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    icon = Column(String(10), default="🔔")
    title = Column(String(150), nullable=False)
    body = Column(String(300), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    icon = Column(String(10), default="📌")
    text = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
