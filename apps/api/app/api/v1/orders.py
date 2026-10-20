from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.db.session import get_db
from app.schemas.catalog import (
    RequestCounters,
    RequestListItem,
    RequestOut,
    RequestStatus,
    RequestUpdate,
)
from app.schemas.common import Page, pages_for
from app.services.catalog import CatalogService
from app.services.orders import OrderService
from app.services.serializers import request_list_item, request_out

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=Page[RequestListItem])
def list_orders(
    status: RequestStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> Page[RequestListItem]:
    rows, total = OrderService.list(
        db, status=status, search=search, page=page, page_size=page_size
    )
    return Page[RequestListItem](
        items=[request_list_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages_for(total, page_size),
    )


@router.get("/counters", response_model=RequestCounters)
def order_counters(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> RequestCounters:
    return RequestCounters(**CatalogService.counters(db))


@router.get("/{request_id}", response_model=RequestOut)
def get_order(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> RequestOut:
    return request_out(OrderService.get(db, request_id))


@router.patch("/{request_id}", response_model=RequestOut)
def update_order(
    request_id: uuid.UUID,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> RequestOut:
    request = OrderService.get(db, request_id)
    OrderService.update(db, request=request, payload=payload, actor=ctx.actor)
    db.commit()
    db.refresh(request)
    return request_out(request)
