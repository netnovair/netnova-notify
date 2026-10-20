from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.db.session import get_db
from app.services.status import StatusService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict:
    return {"status": "ok", "time": utcnow().isoformat()}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    database = StatusService.database_status(db)
    worker = StatusService.worker_status(db)
    payload = {
        "status": "ok" if database.status == "ok" else "degraded",
        "database": database.model_dump(mode="json"),
        "worker": worker.model_dump(mode="json"),
        "time": utcnow().isoformat(),
    }
    return JSONResponse(status_code=200 if database.status == "ok" else 503, content=payload)
