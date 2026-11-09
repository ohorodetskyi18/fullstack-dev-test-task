"""Authorization model: roles, permissions and which role grants what.

This module is the single source of truth for "who can do what".
Application code checks permissions (``has_permission``), never role names.

To add a role: add it to ``Role`` and to ``ROLE_PERMISSIONS``; no other backend
code changes (see README → "Adding a new role" for the frontend label and tests).

Actions on your own data (profile, password, own items) need no permission:
any authenticated, active user may perform them.
"""

from enum import StrEnum
from typing import Protocol


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class Permission(StrEnum):
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_MANAGE = "users:manage"
    METRICS_VIEW = "metrics:view"
    ITEMS_MANAGE_ANY = "items:manage_any"
    SETTINGS_MANAGE = "settings:manage"
    ACCOUNT_DELETE_OWN = "account:delete_own"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(
        {
            Permission.USERS_READ,
            Permission.USERS_CREATE,
            Permission.USERS_MANAGE,
            Permission.METRICS_VIEW,
            Permission.ITEMS_MANAGE_ANY,
            Permission.SETTINGS_MANAGE,
            # No ACCOUNT_DELETE_OWN: an admin cannot delete their own account.
        }
    ),
    Role.MANAGER: frozenset(
        {
            Permission.USERS_READ,
            Permission.METRICS_VIEW,
            Permission.ACCOUNT_DELETE_OWN,
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.ACCOUNT_DELETE_OWN,
        }
    ),
}


class HasRole(Protocol):
    @property
    def role(self) -> Role: ...


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def has_permission(user: HasRole, permission: Permission) -> bool:
    return permission in permissions_for(user.role)
