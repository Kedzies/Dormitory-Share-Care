from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(tags=["User Management"])


@router.get("/me", response_model=schemas.UserOut)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/check-username/{name}", response_model=schemas.UsernameAvailability)
def check_username(name: str, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.username == name).first()
    return schemas.UsernameAvailability(username=name, available=exists is None)


@router.get("/users", response_model=schemas.PaginatedUsers)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.User).order_by(models.User.id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return schemas.PaginatedUsers(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")
    return user


@router.put("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")

    # อนุญาตให้แก้ไขได้เฉพาะข้อมูลของตัวเองเท่านั้น (ป้องกันผู้ใช้อื่นมาแก้ข้อมูลกัน)
    if user.id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์แก้ไขข้อมูลผู้ใช้นี้")

    if payload.email is not None:
        email_taken = (
            db.query(models.User)
            .filter(models.User.email == payload.email, models.User.id != user_id)
            .first()
        )
        if email_taken:
            raise HTTPException(status_code=400, detail="Email นี้ถูกใช้งานแล้ว")
        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")

    # อนุญาตให้ลบได้เฉพาะบัญชีของตัวเองเท่านั้น (ป้องกันผู้ใช้อื่นมาลบบัญชีกัน)
    if user.id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์ลบผู้ใช้นี้")

    db.delete(user)
    db.commit()
    return None
