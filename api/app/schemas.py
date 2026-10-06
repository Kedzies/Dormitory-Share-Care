from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# รูปภาพส่งมาเป็น data URL (data:image/jpeg;base64,...) — หน้าเว็บย่อรูปก่อนส่งแล้ว
MAX_IMAGE_CHARS = 3_000_000  # ~2.2 MB


def _check_image(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not value.startswith("data:image/"):
        raise ValueError("รูปภาพไม่ถูกต้อง")
    if len(value) > MAX_IMAGE_CHARS:
        raise ValueError("รูปภาพมีขนาดใหญ่เกินไป")
    return value


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=100)


# ---------- User ----------
class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class PaginatedUsers(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[UserOut]


class UsernameAvailability(BaseModel):
    username: str
    available: bool


class MessageResponse(BaseModel):
    message: str


# ---------- Items / Borrowing ----------
ITEM_STATUSES = ("available", "repair", "retired")


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="อื่นๆ", max_length=50)
    emoji: str = Field(default="📦", max_length=10)
    quantity: int = Field(default=1, ge=1, le=999)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)
    emoji: Optional[str] = Field(default=None, max_length=10)
    quantity: Optional[int] = Field(default=None, ge=1, le=999)
    status: Optional[str] = Field(default=None, description="available | repair | retired")

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v):
        if v is not None and v not in ITEM_STATUSES:
            raise ValueError("สถานะต้องเป็น available, repair หรือ retired")
        return v


class ItemOut(BaseModel):
    id: int
    name: str
    category: str
    emoji: str
    status: str  # available | borrowed (ถูกยืมหมด) | repair | retired
    quantity: int = 1
    borrowed_count: int = 0
    available_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class BorrowRequest(BaseModel):
    duration_label: str = Field(description='หนึ่งใน "1 ชม.", "1 วัน", "3 วัน"')


class ReturnRequest(BaseModel):
    image_data: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=300)

    _img = field_validator("image_data")(_check_image)


class BorrowRecordOut(BaseModel):
    id: int
    item: ItemOut
    duration_label: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: Optional[datetime] = None
    status: str
    points_awarded: int = 0

    class Config:
        from_attributes = True


# ---------- Deposits ----------
class DepositCreate(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    recipient_username: str = Field(min_length=1, max_length=50)
    note: Optional[str] = Field(default=None, max_length=300)
    eta: Optional[str] = Field(default=None, max_length=100)
    image_data: Optional[str] = None

    _img = field_validator("image_data")(_check_image)


class DepositOut(BaseModel):
    id: int
    code: str
    item_name: str
    note: Optional[str] = None
    eta: Optional[str] = None
    image_data: Optional[str] = None
    status: str
    depositor_username: str
    recipient_username: str
    recipient_registered: bool
    direction: str  # sent | received
    created_at: datetime
    collected_at: Optional[datetime] = None


# ---------- Lost & Found ----------
class FoundCreate(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=150)
    found_time: Optional[str] = Field(default=None, max_length=100)
    emoji: str = Field(default="🎁", max_length=10)
    image_data: Optional[str] = None

    _img = field_validator("image_data")(_check_image)


class FoundOut(BaseModel):
    id: int
    item_name: str
    location: str
    found_time: Optional[str] = None
    emoji: str
    image_data: Optional[str] = None
    status: str
    finder_username: str
    is_mine: bool
    my_claim_status: Optional[str] = None  # สถานะคำขอรับของ "ของฉัน" ต่อชิ้นนี้ (ถ้ามี)
    pending_claims: int = 0  # จำนวนคำขอที่รอเรายืนยัน (เห็นเฉพาะผู้ที่เก็บได้)
    created_at: datetime


class LostCreate(BaseModel):
    item_name: str = Field(min_length=1, max_length=100)
    location_time: str = Field(min_length=1, max_length=150)
    emoji: str = Field(default="🔍", max_length=10)
    image_data: Optional[str] = None

    _img = field_validator("image_data")(_check_image)


class LostOut(BaseModel):
    id: int
    item_name: str
    location_time: str
    emoji: str
    image_data: Optional[str] = None
    status: str
    reporter_username: str
    is_mine: bool
    created_at: datetime


class ClaimCreate(BaseModel):
    detail: str = Field(min_length=5, max_length=500)


class ClaimOut(BaseModel):
    id: int
    found_item_id: int
    item_name: str
    item_emoji: str
    claimant_username: str
    detail: str
    status: str
    created_at: datetime


# ---------- Points / Notifications / Activity ----------
class PointEntry(BaseModel):
    amount: int
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class PointsSummary(BaseModel):
    total: int
    history: List[PointEntry]


class LeaderboardEntry(BaseModel):
    username: str
    points: int
    is_me: bool


class NotificationOut(BaseModel):
    id: int
    icon: str
    title: str
    body: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityOut(BaseModel):
    id: int
    icon: str
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class HomeSummary(BaseModel):
    username: str
    points: int
    unread_notifications: int
    recent_activity: List[ActivityOut]


# ---------- นิติบุคคล (Admin) ----------
class AdminOverview(BaseModel):
    residents: int
    item_types: int
    units_total: int
    units_borrowed: int
    units_available: int
    items_in_repair: int
    active_borrows: int
    overdue_borrows: int
    deposits_waiting: int
    found_open: int
    lost_open: int


class AdminBorrowOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    item_emoji: str
    borrower_username: str
    borrower_name: Optional[str] = None
    duration_label: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: Optional[datetime] = None
    status: str
    overdue: bool
    return_note: Optional[str] = None


class AdminDepositOut(BaseModel):
    id: int
    code: str
    item_name: str
    depositor_username: str
    recipient_username: str
    eta: Optional[str] = None
    note: Optional[str] = None
    status: str
    created_at: datetime
    collected_at: Optional[datetime] = None


class AdminUserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    is_admin: bool
    points: int
    active_borrows: int
    created_at: datetime


class SetActiveRequest(BaseModel):
    is_active: bool


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    body: Optional[str] = Field(default=None, max_length=300)


class AnnouncementResult(BaseModel):
    sent: int
