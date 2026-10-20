from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.db.session import get_db
from app.schemas.catalog import (
    CatalogOut,
    CategoryIn,
    CategoryOut,
    ItemIn,
    ItemOut,
)
from app.services.catalog import CatalogService
from app.services.serializers import category_out, item_out

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _catalog(db: Session) -> CatalogOut:
    categories = CatalogService.tree(db, include_inactive=True)
    public = [category for category in categories if category.is_active and category.items]
    return CatalogOut(
        categories=[category_out(category) for category in categories],
        seeded=bool(categories),
        public_categories=len(public),
    )


@router.get("", response_model=CatalogOut)
def get_catalog(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> CatalogOut:
    return _catalog(db)


@router.post("/seed", response_model=CatalogOut)
def seed_catalog(
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> CatalogOut:
    """Install the default catalog once; a non-empty catalog is never touched."""
    CatalogService.seed_defaults(db, actor=ctx.actor)
    db.commit()
    return _catalog(db)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> CategoryOut:
    category = CatalogService.create_category(db, payload=payload, actor=ctx.actor)
    db.commit()
    db.refresh(category)
    return category_out(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> CategoryOut:
    category = CatalogService.get_category(db, category_id)
    CatalogService.update_category(db, category=category, payload=payload, actor=ctx.actor)
    db.commit()
    db.refresh(category)
    return category_out(category)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> Response:
    category = CatalogService.get_category(db, category_id)
    CatalogService.delete_category(db, category=category, actor=ctx.actor)
    db.commit()
    return Response(status_code=204)


@router.post("/categories/{category_id}/items", response_model=ItemOut, status_code=201)
def create_item(
    category_id: uuid.UUID,
    payload: ItemIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ItemOut:
    category = CatalogService.get_category(db, category_id)
    item = CatalogService.create_item(db, category=category, payload=payload, actor=ctx.actor)
    db.commit()
    db.refresh(item)
    return item_out(item)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ItemIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> ItemOut:
    item = CatalogService.get_item(db, item_id)
    CatalogService.update_item(db, item=item, payload=payload, actor=ctx.actor)
    db.commit()
    db.refresh(item)
    return item_out(item)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> Response:
    item = CatalogService.get_item(db, item_id)
    CatalogService.delete_item(db, item=item, actor=ctx.actor)
    db.commit()
    return Response(status_code=204)
