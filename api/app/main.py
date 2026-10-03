from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .database import Base, SessionLocal, engine
from .routers import auth, community, deposits, items, lostfound, users

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


_ensure_columns()

# ของส่วนกลางชุดเริ่มต้น — ใส่ให้ครั้งแรกที่ตาราง items ยังว่างอยู่เท่านั้น
_DEFAULT_ITEMS = [
    {"name": "ร่มกันฝน", "category": "อื่นๆ", "emoji": "☂️", "status": "available"},
    {"name": "เตารีดไฟฟ้า", "category": "อุปกรณ์ทำความสะอาด", "emoji": "🧺", "status": "available"},
    {"name": "เครื่องดูดฝุ่น", "category": "อุปกรณ์ทำความสะอาด", "emoji": "🧹", "status": "available"},
    {"name": "ชุดไขควง", "category": "ซ่อมแซม", "emoji": "🔧", "status": "available"},
    {"name": "บอร์ดเกม Uno", "category": "ความบันเทิง", "emoji": "🎲", "status": "repair"},
    {"name": "ค้อน + ตะปู", "category": "ซ่อมแซม", "emoji": "🔨", "status": "available"},
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


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
