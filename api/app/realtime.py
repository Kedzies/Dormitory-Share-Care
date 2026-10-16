"""แจ้งเตือนแบบ real-time ผ่าน WebSocket

หลักการ:
- เบราว์เซอร์ที่ล็อกอินอยู่เปิด WebSocket ค้างไว้ 1 เส้นที่ /ws แล้วส่ง token เป็นข้อความแรก
- โค้ดฝั่ง router ยังเรียก services.notify() เหมือนเดิม — notify จะจดไว้ใน session.info ว่าต้องส่งหาใคร
- เมื่อ db.commit() สำเร็จ (event after_commit) ค่อยส่งออกจริง → ไม่มีทางส่งเหตุการณ์ที่ถูก rollback
- router ของเราเป็นฟังก์ชันธรรมดา (รันใน thread pool) จึงส่งงานกลับเข้า event loop ด้วย call_soon_threadsafe

ข้อจำกัด: เก็บการเชื่อมต่อไว้ในหน่วยความจำของ process เดียว — ถ้ารันหลาย worker ต้องย้ายไปใช้ Redis pub/sub
"""
import asyncio
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import event

from . import models
from .database import SessionLocal
from .security import decode_access_token

log = logging.getLogger("realtime")


class ConnectionManager:
    def __init__(self) -> None:
        self.by_user: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def add(self, user_id: int, ws: WebSocket) -> None:
        self.by_user[user_id].add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        self.by_user[user_id].discard(ws)
        if not self.by_user[user_id]:
            self.by_user.pop(user_id, None)

    async def _send(self, sockets: list[WebSocket], message: dict) -> None:
        text = json.dumps(message, ensure_ascii=False, default=str)
        for ws in sockets:
            try:
                await ws.send_text(text)
            except Exception:  # แท็บปิดไปแล้ว — ตัวรับจะลบออกเองตอน disconnect
                pass

    def _dispatch(self, sockets: list[WebSocket], message: dict) -> None:
        """ส่งได้จากทุก thread (router แบบ sync รันใน thread pool)"""
        if not sockets or self.loop is None or self.loop.is_closed():
            return
        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(self._send(sockets, message)))

    def send_to_user(self, user_id: int, message: dict) -> None:
        self._dispatch(list(self.by_user.get(user_id, ())), message)

    def broadcast(self, message: dict) -> None:
        self._dispatch([ws for group in self.by_user.values() for ws in group], message)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# ผูกกับ SQLAlchemy: เก็บข้อความไว้ใน session.info แล้วส่งหลัง commit สำเร็จ
# ---------------------------------------------------------------------------
def queue_notification(db, user_id: int, icon: str, title: str, body: str) -> None:
    db.info.setdefault("rt_notifications", []).append(
        {"type": "notification", "user_id": user_id, "icon": icon, "title": title, "body": body}
    )


def queue_items_changed(db) -> None:
    db.info["rt_items_changed"] = True


@event.listens_for(SessionLocal, "after_commit")
def _flush_realtime(session) -> None:
    pending = session.info.pop("rt_notifications", [])
    items_changed = session.info.pop("rt_items_changed", False)
    for msg in pending:
        manager.send_to_user(msg["user_id"], msg)
    if items_changed:
        manager.broadcast({"type": "items_changed"})


@event.listens_for(SessionLocal, "after_rollback")
def _drop_realtime(session) -> None:
    session.info.pop("rt_notifications", None)
    session.info.pop("rt_items_changed", None)


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------
router = APIRouter(tags=["Realtime"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """ข้อความแรกต้องเป็น {"token": "<JWT>"} (ไม่ส่ง token ใน URL เพื่อไม่ให้ไปโผล่ใน log)"""
    await ws.accept()
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
        username = decode_access_token(str(first.get("token", "")))
    except Exception:
        username = None
    user_id = None
    if username:
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.username == username).first()
            if user and user.is_active:
                user_id = user.id
        finally:
            db.close()
    if user_id is None:
        await ws.close(code=4401)  # token ไม่ถูกต้อง / หมดอายุ
        return

    manager.loop = asyncio.get_running_loop()  # loop ที่ใช้ส่งข้อความจาก thread อื่น
    manager.add(user_id, ws)
    await ws.send_text(json.dumps({"type": "ready"}))
    try:
        while True:
            # ฝั่งเว็บส่ง "ping" มาเป็นระยะ กัน proxy ตัดการเชื่อมต่อที่เงียบนาน
            if await ws.receive_text() == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(user_id, ws)
