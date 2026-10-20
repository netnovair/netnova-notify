"""Service catalog management (main services, sub services, questions).

The bot always reads the catalog through :meth:`CatalogService.public_tree`, so
every change made in the admin panel is visible on the next Telegram message
without a restart or a cache invalidation step.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import bad_request, conflict, not_found
from app.core.security import utcnow
from app.domain.service_tree import CategoryView, NodeView, category_view, node_view
from app.models.catalog import (
    MAX_SERVICE_DEPTH,
    ServiceCategory,
    ServiceItem,
    ServiceQuestion,
    ServiceRequest,
)
from app.schemas.catalog import CategoryIn, ItemIn, QuestionIn
from app.services.audit import Actor, AuditService

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")


def _generated_key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _normalize_key(raw: str | None, prefix: str) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return _generated_key(prefix)
    if not KEY_RE.match(key):
        raise bad_request(
            "کلید فقط می تواند شامل حروف کوچک انگلیسی، عدد و خط تیره باشد.",
            code="invalid_key",
        )
    return key


class CatalogService:
    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    @staticmethod
    def tree(db: Session, *, include_inactive: bool = True) -> list[CategoryView]:
        """Whole service tree as immutable views (safe: never mutates the ORM).

        The descendants are loaded eagerly and rebuilt in Python, so a catalog
        with a few hundred nodes is still a single round-trip per level.
        """
        stmt = (
            select(ServiceCategory)
            .options(
                selectinload(ServiceCategory.items)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children),
                selectinload(ServiceCategory.items)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.questions),
                selectinload(ServiceCategory.items)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.questions),
                selectinload(ServiceCategory.items).selectinload(ServiceItem.questions),
            )
            .order_by(ServiceCategory.order_index, ServiceCategory.created_at)
        )
        if not include_inactive:
            stmt = stmt.where(ServiceCategory.is_active.is_(True))
        categories = list(db.scalars(stmt).all())
        return [
            category_view(category, include_inactive=include_inactive) for category in categories
        ]

    @staticmethod
    def category_detail(
        db: Session, category: ServiceCategory, *, include_inactive: bool = True
    ) -> CategoryView:
        """Reload one category with its items and return its view."""
        loaded = db.scalar(
            select(ServiceCategory)
            .where(ServiceCategory.id == category.id)
            .options(
                selectinload(ServiceCategory.items)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children),
            )
            .execution_options(populate_existing=True)
        )
        return category_view(loaded or category, include_inactive=include_inactive)

    @staticmethod
    def node_detail(db: Session, item: ServiceItem, *, include_inactive: bool = True) -> NodeView:
        """Reload one node with its questions and children, then return its view."""
        loaded = db.scalar(
            select(ServiceItem)
            .where(ServiceItem.id == item.id)
            .options(
                selectinload(ServiceItem.questions),
                selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children)
                .selectinload(ServiceItem.children),
            )
            .execution_options(populate_existing=True)
        )
        return node_view(loaded or item, include_inactive=include_inactive)

    @staticmethod
    def find_item(category: ServiceCategory, item_id: uuid.UUID) -> ServiceItem | None:
        """Resolve a node inside one category (any depth), never across tenants."""
        return next((item for item in category.items if item.id == item_id), None)

    @staticmethod
    def public_tree(db: Session) -> list[CategoryView]:
        """Active categories whose first level has at least one active node."""
        return [
            category
            for category in CatalogService.tree(db, include_inactive=False)
            if category.items
        ]

    @staticmethod
    def counters(db: Session) -> dict[str, int]:
        rows = db.execute(
            select(ServiceRequest.status, func.count()).group_by(ServiceRequest.status)
        ).all()
        counts = {status: int(total) for status, total in rows}
        for status in ("new", "contacted", "quoted", "won", "lost", "cancelled"):
            counts.setdefault(status, 0)
        counts["total"] = sum(counts.values())
        return counts

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------
    @staticmethod
    def get_category(db: Session, category_id: uuid.UUID) -> ServiceCategory:
        category = db.get(ServiceCategory, category_id)
        if category is None:
            raise not_found("این خدمت یافت نشد.")
        return category

    @staticmethod
    def _category_key(db: Session, raw: str | None, *, current: ServiceCategory | None = None):
        key = _normalize_key(raw, "svc")
        existing = db.scalar(select(ServiceCategory).where(ServiceCategory.key == key))
        if existing is not None and (current is None or existing.id != current.id):
            raise conflict("این کلید قبلا استفاده شده است.", code="duplicate_key")
        return key

    @staticmethod
    def create_category(db: Session, *, payload: CategoryIn, actor: Actor) -> ServiceCategory:
        now = utcnow()
        category = ServiceCategory(
            key=CatalogService._category_key(db, payload.key),
            title=payload.title.strip(),
            description=payload.description.strip(),
            emoji=payload.emoji.strip(),
            order_index=payload.order_index,
            is_active=payload.is_active,
            show_portfolio=payload.show_portfolio,
            portfolio_text=payload.portfolio_text.strip(),
            portfolio_url=payload.portfolio_url.strip(),
            created_at=now,
            updated_at=now,
        )
        db.add(category)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="catalog.category_created",
            entity_type="service_category",
            entity_id=category.id,
            context={"title": category.title},
            now=now,
        )
        return category

    @staticmethod
    def update_category(
        db: Session, *, category: ServiceCategory, payload: CategoryIn, actor: Actor
    ) -> ServiceCategory:
        now = utcnow()
        category.key = CatalogService._category_key(db, payload.key, current=category)
        category.title = payload.title.strip()
        category.description = payload.description.strip()
        category.emoji = payload.emoji.strip()
        category.order_index = payload.order_index
        category.is_active = payload.is_active
        category.show_portfolio = payload.show_portfolio
        category.portfolio_text = payload.portfolio_text.strip()
        category.portfolio_url = payload.portfolio_url.strip()
        category.updated_at = now
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="catalog.category_updated",
            entity_type="service_category",
            entity_id=category.id,
            context={"title": category.title},
            now=now,
        )
        return category

    @staticmethod
    def delete_category(db: Session, *, category: ServiceCategory, actor: Actor) -> None:
        used = db.scalar(
            select(func.count())
            .select_from(ServiceRequest)
            .where(ServiceRequest.category_id == category.id)
        )
        if used:
            raise conflict(
                "برای این خدمت سفارش ثبت شده است؛ به جای حذف آن را غیرفعال کنید.",
                code="category_in_use",
            )
        title = category.title
        AuditService.record(
            db,
            actor=actor,
            action="catalog.category_deleted",
            entity_type="service_category",
            entity_id=category.id,
            context={"title": title},
            now=utcnow(),
        )
        db.delete(category)
        db.flush()

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------
    @staticmethod
    def get_item(db: Session, item_id: uuid.UUID) -> ServiceItem:
        item = db.get(ServiceItem, item_id)
        if item is None:
            raise not_found("این زیرخدمت یافت نشد.")
        return item

    @staticmethod
    def _sync_questions(
        db: Session, *, item: ServiceItem, questions: list[QuestionIn]
    ) -> list[ServiceQuestion]:
        now = utcnow()
        existing = {question.key: question for question in item.questions}
        seen: set[str] = set()
        result: list[ServiceQuestion] = []
        for index, payload in enumerate(questions):
            key = (payload.key or "").strip().lower() or _generated_key("q")
            if key in seen:
                raise conflict("کلید سوال تکراری است.", code="duplicate_question_key")
            seen.add(key)
            values = {
                "label": payload.label.strip(),
                "help_text": payload.help_text.strip(),
                "field_type": payload.field_type,
                "required": payload.required,
                "options": payload.options if payload.field_type == "choice" else [],
                "min_value": payload.min_value if payload.field_type == "number" else None,
                "max_value": payload.max_value if payload.field_type == "number" else None,
                "order_index": payload.order_index if payload.order_index else index,
                "is_active": payload.is_active,
                "updated_at": now,
            }
            question = existing.get(key)
            if question is None:
                question = ServiceQuestion(item_id=item.id, key=key, created_at=now, **values)
                db.add(question)
            else:
                for field, value in values.items():
                    setattr(question, field, value)
            result.append(question)
        for key, question in existing.items():
            if key not in seen:
                db.delete(question)
        db.flush()
        return result

    @staticmethod
    def _assert_unique_sibling(
        db: Session,
        *,
        category_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        key: str,
        current_id: uuid.UUID | None = None,
    ) -> None:
        statement = select(ServiceItem.id).where(
            ServiceItem.category_id == category_id,
            ServiceItem.key == key,
        )
        statement = (
            statement.where(ServiceItem.parent_id.is_(None))
            if parent_id is None
            else statement.where(ServiceItem.parent_id == parent_id)
        )
        existing = db.scalar(statement)
        if existing is not None and existing != current_id:
            raise conflict("این کلید در همین سطح وجود دارد.", code="duplicate_key")

    @staticmethod
    def create_item(
        db: Session,
        *,
        category: ServiceCategory,
        payload: ItemIn,
        actor: Actor,
        parent: ServiceItem | None = None,
    ) -> ServiceItem:
        now = utcnow()
        key = _normalize_key(payload.key, "item")
        CatalogService._assert_unique_sibling(
            db, category_id=category.id, parent_id=parent.id if parent else None, key=key
        )
        level = (parent.level + 1) if parent is not None else 1
        if level > MAX_SERVICE_DEPTH:
            raise bad_request(
                f"حداکثر عمق درخت خدمات {MAX_SERVICE_DEPTH} سطح است.",
                code="max_depth",
            )
        item = ServiceItem(
            category_id=category.id,
            parent_id=parent.id if parent else None,
            level=level,
            key=key,
            title=payload.title.strip(),
            description=payload.description.strip(),
            order_index=payload.order_index,
            is_active=payload.is_active,
            show_portfolio=payload.show_portfolio,
            portfolio_text=payload.portfolio_text.strip(),
            portfolio_url=payload.portfolio_url.strip(),
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.flush()
        CatalogService._sync_questions(db, item=item, questions=payload.questions or [])
        AuditService.record(
            db,
            actor=actor,
            action="catalog.item_created",
            entity_type="service_item",
            entity_id=item.id,
            context={
                "title": item.title,
                "category": category.title,
                "parent": parent.title if parent else None,
            },
            now=now,
        )
        return item

    @staticmethod
    def update_item(
        db: Session, *, item: ServiceItem, payload: ItemIn, actor: Actor
    ) -> ServiceItem:
        now = utcnow()
        key = _normalize_key(payload.key, "item")
        CatalogService._assert_unique_sibling(
            db,
            category_id=item.category_id,
            parent_id=item.parent_id,
            key=key,
            current_id=item.id,
        )
        item.key = key
        item.title = payload.title.strip()
        item.description = payload.description.strip()
        item.order_index = payload.order_index
        item.is_active = payload.is_active
        item.show_portfolio = payload.show_portfolio
        item.portfolio_text = payload.portfolio_text.strip()
        item.portfolio_url = payload.portfolio_url.strip()
        item.updated_at = now
        # A node with children is a group: its own questions are never asked, so
        # the panel keeps them but the service reports that explicitly.
        if payload.questions is not None and not item.children:
            CatalogService._sync_questions(db, item=item, questions=payload.questions)
        db.flush()
        AuditService.record(
            db,
            actor=actor,
            action="catalog.item_updated",
            entity_type="service_item",
            entity_id=item.id,
            context={"title": item.title},
            now=now,
        )
        return item

    @staticmethod
    def delete_item(db: Session, *, item: ServiceItem, actor: Actor) -> None:
        subtree = [item, *CatalogService._descendants(item)]
        ids = [node.id for node in subtree]
        used = db.scalar(
            select(func.count()).select_from(ServiceRequest).where(ServiceRequest.item_id.in_(ids))
        )
        if used:
            raise conflict(
                "برای این زیرخدمت یا زیرشاخه های آن سفارش ثبت شده است؛ "
                "به جای حذف آن را غیرفعال کنید.",
                code="item_in_use",
            )
        title = item.title
        AuditService.record(
            db,
            actor=actor,
            action="catalog.item_deleted",
            entity_type="service_item",
            entity_id=item.id,
            context={"title": title, "nodes": len(subtree)},
            now=utcnow(),
        )
        db.delete(item)
        db.flush()

    @staticmethod
    def _descendants(item: ServiceItem) -> list[ServiceItem]:
        result: list[ServiceItem] = []
        for child in item.children:
            result.append(child)
            result.extend(CatalogService._descendants(child))
        return result

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------
    @staticmethod
    def seed_defaults(db: Session, *, actor: Actor) -> int:
        """Create the default agency catalog unless a catalog already exists."""
        from app.domain.catalog_seed import DEFAULT_CATALOG

        existing = db.scalar(select(func.count()).select_from(ServiceCategory)) or 0
        if existing:
            return 0
        now = utcnow()
        created = 0
        for category_order, entry in enumerate(DEFAULT_CATALOG):
            category = ServiceCategory(
                key=entry["key"],
                title=entry["title"],
                description=entry.get("description", ""),
                emoji=entry.get("emoji", ""),
                order_index=category_order,
                is_active=True,
                show_portfolio=entry.get("show_portfolio", False),
                portfolio_text=entry.get("portfolio_text", ""),
                portfolio_url=entry.get("portfolio_url", ""),
                created_at=now,
                updated_at=now,
            )
            db.add(category)
            db.flush()
            created += 1
            CatalogService._seed_items(db, category=category, entries=entry["items"], now=now)
        AuditService.record(
            db,
            actor=actor,
            action="catalog.seeded",
            entity_type="service_catalog",
            entity_id=None,
            context={"categories": created},
            now=now,
        )
        return created

    @staticmethod
    def _seed_items(
        db: Session,
        *,
        category: ServiceCategory,
        entries: list[dict],
        now,
        parent: ServiceItem | None = None,
    ) -> None:
        for order, entry in enumerate(entries):
            item = ServiceItem(
                category_id=category.id,
                parent_id=parent.id if parent else None,
                level=(parent.level + 1) if parent else 1,
                key=entry["key"],
                title=entry["title"],
                description=entry.get("description", ""),
                order_index=order,
                is_active=True,
                show_portfolio=entry.get("show_portfolio", False),
                portfolio_text=entry.get("portfolio_text", ""),
                portfolio_url=entry.get("portfolio_url", ""),
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.flush()
            for question_order, question in enumerate(entry.get("questions", [])):
                db.add(
                    ServiceQuestion(
                        item_id=item.id,
                        key=question["key"],
                        label=question["label"],
                        help_text=question.get("help_text", ""),
                        field_type=question.get("field_type", "text"),
                        required=question.get("required", True),
                        options=question.get("options", []),
                        min_value=question.get("min_value"),
                        max_value=question.get("max_value"),
                        order_index=question_order,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
            db.flush()
            if entry.get("items"):
                CatalogService._seed_items(
                    db, category=category, entries=entry["items"], now=now, parent=item
                )
