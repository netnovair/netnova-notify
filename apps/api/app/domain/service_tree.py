"""Read-only view objects for the service tree.

The ORM models stay the source of truth for writes, but the bot and the panel
read a *snapshot*: building a nested tree by assigning to ``category.items`` or
``item.children`` would make SQLAlchemy treat the rows that are not part of the
assigned list as orphans of a ``delete-orphan`` relationship and delete them.
That is a data-loss trap, so reads go through these immutable dataclasses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuestionView:
    id: uuid.UUID
    key: str
    label: str
    help_text: str
    field_type: str
    required: bool
    options: list[str]
    min_value: int | None
    max_value: int | None
    order_index: int
    is_active: bool


@dataclass(frozen=True)
class NodeView:
    id: uuid.UUID
    category_id: uuid.UUID
    parent_id: uuid.UUID | None
    level: int
    key: str
    title: str
    description: str
    order_index: int
    is_active: bool
    show_portfolio: bool
    portfolio_text: str
    portfolio_url: str
    questions: list[QuestionView] = field(default_factory=list)
    children: list[NodeView] = field(default_factory=list)

    @property
    def is_group(self) -> bool:
        """A node with children is a group; the bot asks to choose one."""
        return bool(self.children)


@dataclass(frozen=True)
class CategoryView:
    id: uuid.UUID
    key: str
    title: str
    description: str
    emoji: str
    order_index: int
    is_active: bool
    show_portfolio: bool
    portfolio_text: str
    portfolio_url: str
    items: list[NodeView] = field(default_factory=list)


def _question_view(question: Any) -> QuestionView:
    return QuestionView(
        id=question.id,
        key=question.key,
        label=question.label,
        help_text=question.help_text,
        field_type=question.field_type,
        required=question.required,
        options=[str(option) for option in (question.options or [])],
        min_value=question.min_value,
        max_value=question.max_value,
        order_index=question.order_index,
        is_active=question.is_active,
    )


def node_view(item: Any, *, include_inactive: bool = True) -> NodeView:
    """Convert one ORM ``ServiceItem`` (loaded with its children) into a view."""
    children = [child for child in item.children if include_inactive or child.is_active]
    questions = [question for question in item.questions if include_inactive or question.is_active]
    return NodeView(
        id=item.id,
        category_id=item.category_id,
        parent_id=item.parent_id,
        level=item.level,
        key=item.key,
        title=item.title,
        description=item.description,
        order_index=item.order_index,
        is_active=item.is_active,
        show_portfolio=item.show_portfolio,
        portfolio_text=item.portfolio_text,
        portfolio_url=item.portfolio_url,
        questions=[
            _question_view(question)
            for question in sorted(questions, key=lambda row: row.order_index)
        ],
        children=[
            node_view(child, include_inactive=include_inactive)
            for child in sorted(children, key=lambda row: row.order_index)
        ],
    )


def category_view(category: Any, *, include_inactive: bool = True) -> CategoryView:
    """Convert an ORM ``ServiceCategory`` (loaded with its items) into a view."""
    roots = [
        item
        for item in category.items
        if item.parent_id is None and (include_inactive or item.is_active)
    ]
    return CategoryView(
        id=category.id,
        key=category.key,
        title=category.title,
        description=category.description,
        emoji=category.emoji,
        order_index=category.order_index,
        is_active=category.is_active,
        show_portfolio=category.show_portfolio,
        portfolio_text=category.portfolio_text,
        portfolio_url=category.portfolio_url,
        items=[
            node_view(item, include_inactive=include_inactive)
            for item in sorted(roots, key=lambda row: row.order_index)
        ],
    )
