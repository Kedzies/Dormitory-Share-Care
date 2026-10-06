"""สแกน QR / พิมพ์รหัส เพื่อยืนยันการส่งของ

- DP-xxxxxx  รหัสรับของฝาก: ผู้ฝาก (หรือนิติ) สแกน QR จากมือถือผู้รับ → ยืนยันว่าส่งถึงมือแล้ว
- BR-<id>    รหัสการยืม: นิติสแกนตอนผู้ยืมเอาของมาคืนที่ออฟฟิศ → บันทึกรับคืน
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from .admin import mark_returned_by_admin
from .deposits import mark_collected

router = APIRouter(tags=["QR Scan"])


@router.post("/scan", response_model=schemas.ScanResult)
def scan_code(
    payload: schemas.ScanRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    code = payload.code.strip().upper()

    if code.startswith("DP-"):
        d = db.query(models.Deposit).filter(models.Deposit.code == code).first()
        if not d:
            raise HTTPException(status_code=404, detail="ไม่พบรายการฝากของรหัสนี้")
        if d.depositor_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="รหัสนี้ไม่ใช่ของที่คุณฝาก — ให้ผู้ฝากเป็นคนสแกน")
        if d.status != "waiting":
            raise HTTPException(status_code=400, detail="รายการนี้ส่งถึงมือ/ยกเลิกไปแล้ว")
        mark_collected(db, d, notify_depositor=d.depositor_id != current_user.id)
        db.commit()
        return schemas.ScanResult(kind="deposit", message=f"ยืนยันส่ง {d.item_name} ถึงห้อง {d.recipient_username} แล้ว")

    if code.startswith("BR-"):
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="รหัสการยืมใช้สแกนที่นิติบุคคลเท่านั้น")
        try:
            record_id = int(code[3:])
        except ValueError:
            raise HTTPException(status_code=400, detail="รหัสไม่ถูกต้อง")
        record = db.query(models.BorrowRecord).filter(models.BorrowRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="ไม่พบรายการยืมรหัสนี้")
        if record.status != "active":
            raise HTTPException(status_code=400, detail="รายการนี้คืนไปแล้ว")
        mark_returned_by_admin(db, record)
        db.commit()
        return schemas.ScanResult(kind="borrow", message=f"บันทึกรับคืน {record.item.name} จากห้อง {record.borrower.username} แล้ว")

    raise HTTPException(status_code=400, detail="ไม่รู้จักรหัสนี้ — รหัสต้องขึ้นต้นด้วย DP- หรือ BR-")
