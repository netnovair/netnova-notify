from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.db.session import get_db
from app.schemas.dashboard import DashboardOut, SystemStatusOut
from app.services.dashboard import DashboardService
from app.services.status import StatusService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> DashboardOut:
    return DashboardService.summary(db)


@router.get("/system/status", response_model=SystemStatusOut)
def system_status(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> SystemStatusOut:
    return StatusService.get(db)
