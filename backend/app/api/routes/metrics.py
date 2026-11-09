from fastapi import APIRouter, Depends
from sqlmodel import func, select

from app.api.deps import SessionDep, require_permission
from app.core.permissions import Permission, Role
from app.models import Item, MetricsPublic, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/",
    dependencies=[Depends(require_permission(Permission.METRICS_VIEW))],
    response_model=MetricsPublic,
)
def read_metrics(session: SessionDep) -> MetricsPublic:
    """
    Basic usage metrics (stub): user counts per role and total items.
    """
    users_by_role = dict.fromkeys(Role, 0)
    for role, count in session.exec(
        select(User.role, func.count()).group_by(User.role)
    ).all():
        users_by_role[Role(role)] = count

    total_items = session.exec(select(func.count()).select_from(Item)).one()
    return MetricsPublic(
        total_users=sum(users_by_role.values()),
        users_by_role=users_by_role,
        total_items=total_items,
    )
