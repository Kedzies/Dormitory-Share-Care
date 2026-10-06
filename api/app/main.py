import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .database import Base, SessionLocal, engine
from .routers import admin, auth, community, deposits, items, lostfound, scan, users
from .security import hash_password

# สร้างตารางในฐานข้อมูลอัตโนมัติตอน service เริ่มทำงาน (เหมาะกับ dev/demo)
# งาน production จริงควรใช้เครื่องมือ migration เช่น Alembic แทน
Base.metadata.create_all(bind=engine)


def _ensure_columns() -> None:
    """create_all ไม่เพิ่มคอลัมน์ใหม่ให้ตารางที่มีอยู่แล้ว
    ฟังก์ชันนี้เติมคอลัมน์ที่เพิ่มภายหลังให้ฐานข้อมูลเก่า เพื่อไม่ต้องลบข้อมูลทิ้ง"""
    wanted = {
        "borrow_records": {
            "return_image": "TEXT",
            "return_note": "VARCHAR(300)",
            "reminded": "BOOLEAN DEFAULT FALSE",
        },
        "users": {"is_admin": "BOOLEAN DEFAULT FALSE"},
        "items": {"quantity": "INTEGER NOT NULL DEFAULT 1"},
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in wanted.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        # เวอร์ชันก่อนเก็บสถานะ "borrowed" ไว้ที่ item — ตอนนี้คำนวณจากรายการยืมแทน
        if inspector.has_table("items"):
            conn.execute(text("UPDATE items SET status = 'available' WHERE status = 'borrowed'"))


_ensure_columns()

# ของส่วนกลางชุดเริ่มต้น — ใส่ให้ครั้งแรกที่ตาราง items ยังว่างอยู่เท่านั้น
_DEFAULT_ITEMS = [
    {"name": "ร่มกันฝน", "category": "อื่นๆ", "emoji": "☂️", "quantity": 5, "status": "available"},
    {"name": "เตารีดไฟฟ้า", "category": "อุปกรณ์ทำความสะอาด", "emoji": "🧺", "quantity": 2, "status": "available"},
    {"name": "เครื่องดูดฝุ่น", "category": "อุปกรณ์ทำความสะอาด", "emoji": "🧹", "quantity": 1, "status": "available"},
    {"name": "ชุดไขควง", "category": "ซ่อมแซม", "emoji": "🔧", "quantity": 2, "status": "available"},
    {"name": "บอร์ดเกม Uno", "category": "ความบันเทิง", "emoji": "🎲", "quantity": 1, "status": "repair"},
    {"name": "ค้อน + ตะปู", "category": "ซ่อมแซม", "emoji": "🔨", "quantity": 1, "status": "available"},
]


def _seed_default_items() -> None:
    db = SessionLocal()
    try:
        if db.query(models.Item).first() is None:
            db.add_all(models.Item(**data) for data in _DEFAULT_ITEMS)
            db.commit()
    finally:
        db.close()


_seed_default_items()


def _ensure_admin() -> None:
    """สร้าง/ตั้งบัญชีนิติบุคคลจาก ADMIN_USERNAME + ADMIN_PASSWORD ใน .env
    ถ้ามีบัญชีชื่อนี้อยู่แล้ว จะแค่ให้สิทธิ์นิติ (ไม่เปลี่ยนรหัสผ่านเดิม)"""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username:
        return
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user.is_admin = True
        elif len(password) >= 6:
            db.add(models.User(
                username=username,
                full_name="นิติบุคคล",
                hashed_password=hash_password(password),
                is_admin=True,
            ))
        else:
            logging.warning("ADMIN_PASSWORD ต้องยาวอย่างน้อย 6 ตัวอักษร — ยังไม่ได้สร้างบัญชีนิติ")
            return
        db.commit()
    finally:
        db.close()


_ensure_admin()

app = FastAPI(
    title="Dormitory Share & Care API",
    description="REST API สำหรับระบบยืม-คืนของ ฝากของ ของหายได้คืน และแต้มความดีในหอพัก",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(items.router)
app.include_router(deposits.router)
app.include_router(lostfound.router)
app.include_router(community.router)
app.include_router(admin.router)
app.include_router(scan.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
