import logging
from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.permissions import Permission, has_permission
from app.models import TokenPayload, User

authz_logger = logging.getLogger("app.authz")

FORBIDDEN_DETAIL = "The user doesn't have enough privileges"

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def ensure_permission(request: Request, user: User, permission: Permission) -> None:
    """Raise 403 and log the attempt unless ``user`` has ``permission``.

    Use inside handlers for object-level checks (e.g. "own item, or
    items:manage_any"). Route-level checks use ``require_permission``.
    """
    if has_permission(user, permission):
        return
    authz_logger.warning(
        "Permission denied: user_id=%s role=%s permission=%s method=%s path=%s",
        user.id,
        user.role,
        permission,
        request.method,
        request.url.path,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL)


def require_permission(permission: Permission) -> Callable[[Request, User], None]:
    """Route-level check: ``dependencies=[Depends(require_permission(...))]``."""

    def dependency(request: Request, current_user: CurrentUser) -> None:
        ensure_permission(request, current_user, permission)

    return dependency
