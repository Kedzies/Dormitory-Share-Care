from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import Base, engine
from .routers import auth, users

# สร้างตารางในฐานข้อมูลอัตโนมัติตอน service เริ่มทำงาน (เหมาะกับ dev/demo)
# งาน production จริงควรใช้เครื่องมือ migration เช่น Alembic แทน
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Project Group API",
    description="REST API สำหรับระบบ Project ของกลุ่ม — Authentication & User Management",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
