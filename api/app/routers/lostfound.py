from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import POINTS_FOUND_RETURNED, award_points, log_activity, notify

router = APIRouter(tags=["Lost & Found"])


def _names_match(a: str, b: str) -> bool:
    """จับคู่ชื่อของแบบง่าย: ชื่อหนึ่งอยู่ในอีกชื่อ หรือมีคำ (คั่นด้วยช่องว่าง) ร่วมกัน"""
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    words_a = {w for w in a.split() if len(w) >= 2}
    words_b = {w for w in b.split() if len(w) >= 2}
    return bool(words_a & words_b)


def _found_out(db: Session, f: models.FoundItem, me: models.User) -> schemas.FoundOut:
    my_claim = (
        db.query(models.Claim)
        .filter(models.Claim.found_item_id == f.id, models.Claim.claimant_id == me.id)
        .order_by(models.Claim.created_at.desc())
        .first()
    )
    pending = 0
    if f.finder_id == me.id:
        pending = (
            db.query(models.Claim)
            .filter(models.Claim.found_item_id == f.id, models.Claim.status == "pending")
            .count()
        )
    return schemas.FoundOut(
        id=f.id,
        item_name=f.item_name,
        location=f.location,
        found_time=f.found_time,
        emoji=f.emoji,
        image_data=f.image_data,
        status=f.status,
        finder_username=f.finder.username,
        is_mine=f.finder_id == me.id,
        my_claim_status=my_claim.status if my_claim else None,
        pending_claims=pending,
        created_at=f.created_at,
    )


def _lost_out(l: models.LostReport, me: models.User) -> schemas.LostOut:
    return schemas.LostOut(
        id=l.id,
        item_name=l.item_name,
        location_time=l.location_time,
        emoji=l.emoji,
        image_data=l.image_data,
        status=l.status,
        reporter_username=l.reporter.username,
        is_mine=l.reporter_id == me.id,
        created_at=l.created_at,
    )


def _claim_out(c: models.Claim) -> schemas.ClaimOut:
    return schemas.ClaimOut(
        id=c.id,
        found_item_id=c.found_item_id,
        item_name=c.found_item.item_name,
        item_emoji=c.found_item.emoji,
        claimant_username=c.claimant.username,
        detail=c.detail,
        status=c.status,
        created_at=c.created_at,
    )


# ---------------- ของที่มีคนเก็บได้ ----------------
@router.get("/found", response_model=list[schemas.FoundOut])
def list_found(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    items = (
        db.query(models.FoundItem)
        .filter(models.FoundItem.status == "open")
        .order_by(models.FoundItem.created_at.desc())
        .all()
    )
    return [_found_out(db, f, current_user) for f in items]


@router.post("/found", response_model=schemas.FoundOut, status_code=status.HTTP_201_CREATED)
def report_found(
    payload: schemas.FoundCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    found = models.FoundItem(
        finder_id=current_user.id,
        item_name=payload.item_name,
        location=payload.location,
        found_time=payload.found_time,
        emoji=payload.emoji,
        image_data=payload.image_data,
        status="open",
    )
    db.add(found)
    log_activity(db, current_user.id, "🎁", f"แจ้งเจอ{payload.item_name} ที่{payload.location}")

    # แจ้งเตือนคนที่ประกาศตามหาของที่ชื่อคล้ายกัน
    open_lost = db.query(models.LostReport).filter(models.LostReport.status == "open").all()
    for lost in open_lost:
        if lost.reporter_id != current_user.id and _names_match(lost.item_name, payload.item_name):
            notify(
                db, lost.reporter_id, "🔍", "มีคนพบของที่อาจตรงกับที่คุณตามหา",
                f"{payload.item_name} — พบที่{payload.location} ดูได้ในแท็บ \"พบของ\"",
            )

    db.commit()
    db.refresh(found)
    return _found_out(db, found, current_user)


@router.post("/found/{found_id}/claims", response_model=schemas.ClaimOut, status_code=status.HTTP_201_CREATED)
def claim_found(
    found_id: int,
    payload: schemas.ClaimCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    found = db.query(models.FoundItem).filter(models.FoundItem.id == found_id).first()
    if not found:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้")
    if found.status != "open":
        raise HTTPException(status_code=400, detail="ของชิ้นนี้ถูกส่งคืนเจ้าของไปแล้ว")
    if found.finder_id == current_user.id:
        raise HTTPException(status_code=400, detail="ไม่สามารถขอรับของที่คุณแจ้งเจอเองได้")

    existing = (
        db.query(models.Claim)
        .filter(
            models.Claim.found_item_id == found_id,
            models.Claim.claimant_id == current_user.id,
            models.Claim.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="คุณส่งคำขอรับของชิ้นนี้ไปแล้ว รอผู้พบยืนยัน")

    claim = models.Claim(found_item_id=found_id, claimant_id=current_user.id, detail=payload.detail)
    db.add(claim)
    notify(
        db, found.finder_id, "✋", "มีคนขอรับของที่คุณเก็บได้",
        f"ห้อง {current_user.username} บอกว่า{found.item_name}เป็นของเขา — ตรวจสอบรายละเอียดแล้วกดยืนยัน",
    )
    log_activity(db, current_user.id, "✋", f"ส่งคำขอรับ{found.item_name}")
    db.commit()
    db.refresh(claim)
    return _claim_out(claim)


# ---------------- คำขอรับของ ----------------
@router.get("/claims/incoming", response_model=list[schemas.ClaimOut])
def incoming_claims(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """คำขอรับของที่รอฉันยืนยัน (สำหรับของที่ฉันเก็บได้)"""
    claims = (
        db.query(models.Claim)
        .join(models.FoundItem, models.Claim.found_item_id == models.FoundItem.id)
        .filter(models.FoundItem.finder_id == current_user.id, models.Claim.status == "pending")
        .order_by(models.Claim.created_at.desc())
        .all()
    )
    return [_claim_out(c) for c in claims]


def _get_my_pending_claim(db: Session, claim_id: int, me: models.User) -> models.Claim:
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="ไม่พบคำขอนี้")
    if claim.found_item.finder_id != me.id:
        raise HTTPException(status_code=403, detail="เฉพาะผู้ที่เก็บของได้เท่านั้นที่ยืนยันคำขอนี้ได้")
    if claim.status != "pending":
        raise HTTPException(status_code=400, detail="คำขอนี้ถูกพิจารณาไปแล้ว")
    return claim


@router.post("/claims/{claim_id}/approve", response_model=schemas.ClaimOut)
def approve_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    claim = _get_my_pending_claim(db, claim_id, current_user)
    found = claim.found_item
    now = datetime.utcnow()

    claim.status = "approved"
    claim.decided_at = now
    found.status = "returned"
    found.owner_id = claim.claimant_id
    found.returned_at = now

    # คำขออื่นของชิ้นเดียวกันถือว่าไม่ผ่านโดยอัตโนมัติ
    others = (
        db.query(models.Claim)
        .filter(models.Claim.found_item_id == found.id, models.Claim.id != claim.id, models.Claim.status == "pending")
        .all()
    )
    for other in others:
        other.status = "rejected"
        other.decided_at = now
        notify(db, other.claimant_id, "❌", "คำขอรับของไม่ผ่าน", f"{found.item_name} ถูกส่งคืนให้ผู้อื่นแล้ว")

    award_points(db, current_user.id, POINTS_FOUND_RETURNED, f"คืน{found.item_name}ให้เจ้าของ")
    log_activity(db, current_user.id, "🎉", f"คืน{found.item_name}ให้ห้อง {claim.claimant.username} (+{POINTS_FOUND_RETURNED} แต้ม)")
    notify(db, claim.claimant_id, "✅", "ยืนยันแล้ว! ไปรับของได้เลย", f"{found.item_name} — ติดต่อรับจากห้อง {current_user.username}")
    log_activity(db, claim.claimant_id, "🎁", f"ได้รับ{found.item_name}คืนจากห้อง {current_user.username}")

    # ถ้าเจ้าของเคยประกาศตามหาของที่ชื่อตรงกัน ปิดประกาศให้อัตโนมัติ
    for lost in db.query(models.LostReport).filter(
        models.LostReport.reporter_id == claim.claimant_id, models.LostReport.status == "open"
    ):
        if _names_match(lost.item_name, found.item_name):
            lost.status = "resolved"
            lost.resolved_at = now

    db.commit()
    db.refresh(claim)
    return _claim_out(claim)


@router.post("/claims/{claim_id}/reject", response_model=schemas.ClaimOut)
def reject_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    claim = _get_my_pending_claim(db, claim_id, current_user)
    claim.status = "rejected"
    claim.decided_at = datetime.utcnow()
    notify(db, claim.claimant_id, "❌", "คำขอรับของไม่ผ่าน",
           f"ผู้พบ{claim.found_item.item_name}ตรวจสอบแล้วรายละเอียดไม่ตรง")
    db.commit()
    db.refresh(claim)
    return _claim_out(claim)


# ---------------- ประกาศตามหาของ ----------------
@router.get("/lost", response_model=list[schemas.LostOut])
def list_lost(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    reports = (
        db.query(models.LostReport)
        .filter(models.LostReport.status == "open")
        .order_by(models.LostReport.created_at.desc())
        .all()
    )
    return [_lost_out(l, current_user) for l in reports]


@router.post("/lost", response_model=schemas.LostOut, status_code=status.HTTP_201_CREATED)
def report_lost(
    payload: schemas.LostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    report = models.LostReport(
        reporter_id=current_user.id,
        item_name=payload.item_name,
        location_time=payload.location_time,
        emoji=payload.emoji,
        image_data=payload.image_data,
        status="open",
    )
    db.add(report)
    log_activity(db, current_user.id, "📢", f"ประกาศตามหา{payload.item_name}")

    # ถ้ามีคนเคยแจ้งเจอของที่ชื่อคล้ายกันอยู่แล้ว บอกผู้ประกาศทันที
    for f in db.query(models.FoundItem).filter(models.FoundItem.status == "open"):
        if f.finder_id != current_user.id and _names_match(f.item_name, payload.item_name):
            notify(
                db, current_user.id, "🔍", "มีของที่อาจตรงกับที่คุณตามหาอยู่แล้ว",
                f"{f.item_name} — พบที่{f.location} ดูได้ในแท็บ \"พบของ\"",
            )

    db.commit()
    db.refresh(report)
    return _lost_out(report, current_user)


@router.post("/lost/{lost_id}/resolve", response_model=schemas.LostOut)
def resolve_lost(
    lost_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    report = db.query(models.LostReport).filter(models.LostReport.id == lost_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="ไม่พบประกาศนี้")
    if report.reporter_id != current_user.id:
        raise HTTPException(status_code=403, detail="ปิดประกาศได้เฉพาะผู้ประกาศเท่านั้น")
    if report.status != "open":
        raise HTTPException(status_code=400, detail="ประกาศนี้ถูกปิดไปแล้ว")
    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    log_activity(db, current_user.id, "😊", f"เจอ{report.item_name}แล้ว ปิดประกาศตามหา")
    db.commit()
    db.refresh(report)
    return _lost_out(report, current_user)
