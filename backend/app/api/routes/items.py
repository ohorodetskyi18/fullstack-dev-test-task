import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, col, func, select

from app.api.deps import CurrentUser, SessionDep, ensure_permission
from app.core.permissions import Permission, has_permission
from app.models import (
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
    Message,
    User,
)

router = APIRouter(prefix="/items", tags=["items"])


def get_item_or_403(
    request: Request, session: Session, current_user: User, item_id: uuid.UUID
) -> Item:
    """Load an item the current user owns, or any item with items:manage_any."""
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id:
        ensure_permission(request, current_user, Permission.ITEMS_MANAGE_ANY)
    return item


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve items.
    """

    if has_permission(current_user, Permission.ITEMS_MANAGE_ANY):
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = (
            select(Item).order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
        )
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .order_by(col(Item.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        items = session.exec(statement).all()

    items_public = [ItemPublic.model_validate(item) for item in items]
    return ItemsPublic(data=items_public, count=count)


@router.get("/{id}", response_model=ItemPublic)
def read_item(
    request: Request, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get item by ID.
    """
    return get_item_or_403(request, session, current_user, id)


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = get_item_or_403(request, session, current_user, id)
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    request: Request, session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = get_item_or_403(request, session, current_user, id)
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
