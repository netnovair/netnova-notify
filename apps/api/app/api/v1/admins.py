from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import conflict
from app.db.session import get_db
from app.schemas.admin import (
    AdminCreate,
    AdminOut,
    AdminPasswordChange,
    AdminPasswordReset,
    AdminUpdate,
    TemporaryPasswordOut,
)
from app.services.admins import AdminService

router = APIRouter(prefix="/admins", tags=["admins"])


@router.get("", response_model=list[AdminOut])
def list_admins(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[AdminOut]:
    return [AdminOut.model_validate(admin) for admin in AdminService.list(db)]


@router.post("", response_model=AdminOut, status_code=201)
def create_admin(
    payload: AdminCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> AdminOut:
    admin = AdminService.create(
        db,
        email=payload.email,
        display_name=payload.display_name,
        password=payload.password,
        actor=ctx.actor,
    )
    db.commit()
    return AdminOut.model_validate(admin)


@router.patch("/{admin_id}", response_model=AdminOut)
def update_admin(
    admin_id: uuid.UUID,
    payload: AdminUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> AdminOut:
    admin = AdminService.get(db, admin_id)
    AdminService.update(
        db,
        admin=admin,
        display_name=payload.display_name,
        is_active=payload.is_active,
        actor=ctx.actor,
        current_admin_id=ctx.admin.id,
    )
    db.commit()
    return AdminOut.model_validate(admin)


@router.post("/me/password", status_code=204)
def change_my_password(
    payload: AdminPasswordChange,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> Response:
    AdminService.change_password(
        db,
        admin=ctx.admin,
        current_password=payload.current_password,
        new_password=payload.new_password,
        actor=ctx.actor,
        keep_session_id=ctx.session.id,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/{admin_id}/reset-password", response_model=TemporaryPasswordOut)
def reset_admin_password(
    admin_id: uuid.UUID,
    payload: AdminPasswordReset,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> TemporaryPasswordOut:
    admin = AdminService.get(db, admin_id)
    if payload.confirm_email.strip().lower() != admin.email:
        raise conflict("برای بازنشانی رمز، ایمیل مدیر را دقیقا وارد کنید.")
    if admin.id == ctx.admin.id:
        raise conflict("برای تغییر رمز خودتان از صفحه تنظیمات استفاده کنید.")
    temporary = AdminService.reset_password(db, admin=admin, actor=ctx.actor)
    db.commit()
    return TemporaryPasswordOut(
        admin_id=admin.id,
        temporary_password=temporary,
        message="رمز موقت ساخته شد. تمام نشست های این مدیر بسته شد. رمز را یک بار به او اعلام کنید.",
    )
