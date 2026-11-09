"""Authorization tests: permission matrix, escalation attempts, 401 vs 403.

ENDPOINTS mirrors the permission matrix in the README: each row lists the
roles that are allowed. Every other role must get 403 and an anonymous
request must get 401, so a newly added role is denied everywhere by default.
"""

import logging
import uuid
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.deps import FORBIDDEN_DETAIL
from app.core.config import settings
from app.core.permissions import ROLE_PERMISSIONS, Role
from app.core.security import create_access_token
from tests.utils.item import create_random_item
from tests.utils.user import create_random_user, create_user_with_role
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
ADMIN, MANAGER, MEMBER = Role.ADMIN, Role.MANAGER, Role.MEMBER
EVERYONE = tuple(Role)


@pytest.fixture(autouse=True)
def no_emails() -> Generator[None]:
    with (
        patch("app.api.routes.users.send_email"),
        patch("app.api.routes.utils.send_email"),
    ):
        yield


# --- Permission matrix -------------------------------------------------------


@dataclass(frozen=True)
class Endpoint:
    name: str  # used in test ids, e.g. "member-cannot-list-users"
    method: str
    # Placeholders: {own_user_id}, {own_item_id}, {other_user_id},
    # {other_user_email}, {other_item_id}
    path: str
    allowed: tuple[Role, ...]
    json: dict[str, Any] | None = None
    ok_status: int = 200


ENDPOINTS = [
    # No permission needed: own profile and own items
    Endpoint("read-own-profile", "GET", "/users/me", EVERYONE),
    Endpoint(
        "update-own-profile", "PATCH", "/users/me", EVERYONE, json={"full_name": "N"}
    ),
    Endpoint("read-own-user-by-id", "GET", "/users/{own_user_id}", EVERYONE),
    Endpoint("read-own-item", "GET", "/items/{own_item_id}", EVERYONE),
    # users:read
    Endpoint("list-users", "GET", "/users/", (ADMIN, MANAGER)),
    Endpoint("read-other-user", "GET", "/users/{other_user_id}", (ADMIN, MANAGER)),
    # metrics:view
    Endpoint("view-metrics", "GET", "/metrics/", (ADMIN, MANAGER)),
    # users:create
    Endpoint(
        "create-user",
        "POST",
        "/users/",
        (ADMIN,),
        json={"email": random_email(), "password": random_lower_string()},
    ),
    # users:manage
    Endpoint(
        "update-other-user",
        "PATCH",
        "/users/{other_user_id}",
        (ADMIN,),
        json={"full_name": "Changed"},
    ),
    Endpoint("delete-other-user", "DELETE", "/users/{other_user_id}", (ADMIN,)),
    Endpoint(
        "preview-password-recovery-email",
        "POST",
        "/password-recovery-html-content/{other_user_email}",
        (ADMIN,),
    ),
    # items:manage_any
    Endpoint("read-other-users-item", "GET", "/items/{other_item_id}", (ADMIN,)),
    Endpoint(
        "update-other-users-item",
        "PUT",
        "/items/{other_item_id}",
        (ADMIN,),
        json={"title": "Changed"},
    ),
    Endpoint("delete-other-users-item", "DELETE", "/items/{other_item_id}", (ADMIN,)),
    # settings:manage
    Endpoint(
        "send-test-email",
        "POST",
        "/utils/test-email/?email_to=test@example.com",
        (ADMIN,),
        ok_status=201,
    ),
    # account:delete_own
    Endpoint("delete-own-account", "DELETE", "/users/me", (MANAGER, MEMBER)),
]


def matrix_cases() -> Iterator[Any]:
    for endpoint in ENDPOINTS:
        yield pytest.param(None, endpoint, 401, id=f"anonymous-cannot-{endpoint.name}")
        for role in Role:
            allowed = role in endpoint.allowed
            yield pytest.param(
                role,
                endpoint,
                endpoint.ok_status if allowed else 403,
                id=f"{role}-{'can' if allowed else 'cannot'}-{endpoint.name}",
            )


@pytest.mark.parametrize(("role", "endpoint", "expected_status"), list(matrix_cases()))
def test_permission_matrix(
    client: TestClient,
    db: Session,
    role: Role | None,
    endpoint: Endpoint,
    expected_status: int,
) -> None:
    other_user = create_random_user(db)
    other_item = create_random_item(db, owner_id=other_user.id)
    path_vars: dict[str, Any] = {
        "other_user_id": other_user.id,
        "other_user_email": other_user.email,
        "other_item_id": other_item.id,
        # Anonymous requests are rejected before ids matter.
        "own_user_id": other_user.id,
        "own_item_id": other_item.id,
    }
    headers: dict[str, str] = {}
    if role is not None:
        actor, headers = create_user_with_role(client=client, db=db, role=role)
        own_item = create_random_item(db, owner_id=actor.id)
        path_vars |= {"own_user_id": actor.id, "own_item_id": own_item.id}

    r = client.request(
        endpoint.method,
        f"{API}{endpoint.path.format(**path_vars)}",
        headers=headers,
        json=endpoint.json,
    )

    assert r.status_code == expected_status, r.text
    if expected_status == 403:
        assert r.json() == {"detail": FORBIDDEN_DETAIL}


def test_every_role_has_permissions_defined() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


EXPECTED_PERMISSIONS = {
    ADMIN: {
        "users:read",
        "users:create",
        "users:manage",
        "metrics:view",
        "items:manage_any",
        "settings:manage",
    },
    MANAGER: {"users:read", "metrics:view", "account:delete_own"},
    MEMBER: {"account:delete_own"},
}


@pytest.mark.parametrize("role", list(Role), ids=str)
def test_read_me_returns_permissions_of_role(
    client: TestClient, db: Session, role: Role
) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=role)

    r = client.get(f"{API}/users/me", headers=headers)

    assert r.status_code == 200
    assert r.json()["role"] == role
    assert set(r.json()["permissions"]) == EXPECTED_PERMISSIONS[role]


# --- Privilege escalation attempts ------------------------------------------


def test_member_cannot_change_own_role_via_update_me(
    client: TestClient, db: Session
) -> None:
    member, headers = create_user_with_role(client=client, db=db, role=MEMBER)

    r = client.patch(f"{API}/users/me", headers=headers, json={"role": "admin"})

    # UserUpdateMe has no role field, so the value is ignored.
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    db.refresh(member)
    assert member.role == MEMBER


def test_signup_always_creates_member(client: TestClient, db: Session) -> None:
    email = random_email()

    r = client.post(
        f"{API}/users/signup",
        json={"email": email, "password": random_lower_string(), "role": "admin"},
    )

    assert r.status_code == 200
    assert r.json()["role"] == "member"
    user = crud.get_user_by_email(session=db, email=email)
    assert user and user.role == MEMBER


def test_manager_cannot_change_another_users_role(
    client: TestClient, db: Session
) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=MANAGER)
    target = create_random_user(db)

    r = client.patch(
        f"{API}/users/{target.id}", headers=headers, json={"role": "admin"}
    )

    assert r.status_code == 403
    db.refresh(target)
    assert target.role == MEMBER


def test_manager_cannot_promote_themselves(client: TestClient, db: Session) -> None:
    manager, headers = create_user_with_role(client=client, db=db, role=MANAGER)

    r = client.patch(
        f"{API}/users/{manager.id}", headers=headers, json={"role": "admin"}
    )

    assert r.status_code == 403
    db.refresh(manager)
    assert manager.role == MANAGER


@pytest.mark.parametrize(
    "change",
    [{"role": "manager"}, {"role": "member"}, {"is_active": False}],
    ids=["demote-to-manager", "demote-to-member", "deactivate"],
)
def test_admin_cannot_remove_own_admin_access(
    client: TestClient, db: Session, change: dict[str, Any]
) -> None:
    admin, headers = create_user_with_role(client=client, db=db, role=ADMIN)

    r = client.patch(f"{API}/users/{admin.id}", headers=headers, json=change)

    assert r.status_code == 409
    assert r.json() == {"detail": "You cannot remove your own admin access"}
    db.refresh(admin)
    assert admin.role == ADMIN
    assert admin.is_active


def test_admin_can_update_own_other_fields(client: TestClient, db: Session) -> None:
    admin, headers = create_user_with_role(client=client, db=db, role=ADMIN)

    r = client.patch(
        f"{API}/users/{admin.id}",
        headers=headers,
        json={"full_name": "Still Admin", "role": "admin"},
    )

    assert r.status_code == 200
    assert r.json()["full_name"] == "Still Admin"
    assert r.json()["role"] == "admin"


def test_admin_can_assign_role(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=ADMIN)
    target = create_random_user(db)

    r = client.patch(
        f"{API}/users/{target.id}", headers=headers, json={"role": "manager"}
    )

    assert r.status_code == 200
    db.refresh(target)
    assert target.role == MANAGER


def test_admin_can_create_user_with_role(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=ADMIN)

    r = client.post(
        f"{API}/users/",
        headers=headers,
        json={
            "email": random_email(),
            "password": random_lower_string(),
            "role": "manager",
        },
    )

    assert r.status_code == 200
    assert r.json()["role"] == "manager"


def test_role_change_applies_to_existing_token(client: TestClient, db: Session) -> None:
    manager, manager_headers = create_user_with_role(client=client, db=db, role=MANAGER)
    _, admin_headers = create_user_with_role(client=client, db=db, role=ADMIN)
    assert client.get(f"{API}/users/", headers=manager_headers).status_code == 200

    r = client.patch(
        f"{API}/users/{manager.id}", headers=admin_headers, json={"role": "member"}
    )
    assert r.status_code == 200

    # Same token, new role: the role is loaded from the DB on every request.
    assert client.get(f"{API}/users/", headers=manager_headers).status_code == 403


@pytest.mark.parametrize("field", ["role", "is_active", "email", "password"])
def test_update_user_rejects_explicit_null(
    client: TestClient, db: Session, field: str
) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=ADMIN)
    target = create_random_user(db)

    r = client.patch(f"{API}/users/{target.id}", headers=headers, json={field: None})

    assert r.status_code == 422


@pytest.mark.parametrize("resource", ["users", "items"])
def test_member_cannot_probe_ids(
    client: TestClient, db: Session, resource: str
) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=MEMBER)

    r = client.get(f"{API}/{resource}/{uuid.uuid4()}", headers=headers)

    # Same answer as for an existing id the member may not see: no 404 leak.
    assert r.status_code == 403


# --- 401 vs 403 and logging --------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        create_access_token("00000000-0000-0000-0000-000000000000", timedelta(-1)),
    ],
    ids=["malformed-token", "expired-token"],
)
def test_invalid_token_returns_401(client: TestClient, token: str) -> None:
    r = client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_token_of_deleted_user_returns_401(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_role(client=client, db=db, role=MEMBER)
    db.delete(user)
    db.commit()

    r = client.get(f"{API}/users/me", headers=headers)

    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_token_of_deactivated_user_returns_401(client: TestClient, db: Session) -> None:
    user, headers = create_user_with_role(client=client, db=db, role=MEMBER)
    user.is_active = False
    db.add(user)
    db.commit()

    r = client.get(f"{API}/users/me", headers=headers)

    assert r.status_code == 401
    assert r.json() == {"detail": "Inactive user"}


def test_denied_attempt_is_logged(
    client: TestClient, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    member, headers = create_user_with_role(client=client, db=db, role=MEMBER)

    with caplog.at_level(logging.WARNING, logger="app.authz"):
        r = client.get(f"{API}/users/", headers=headers)

    assert r.status_code == 403
    [record] = [rec for rec in caplog.records if rec.name == "app.authz"]
    message = record.getMessage()
    assert f"user_id={member.id}" in message
    assert "role=member" in message
    assert "permission=users:read" in message
    assert f"method=GET path={API}/users/" in message


def test_metrics_counts_users_per_role(client: TestClient, db: Session) -> None:
    _, headers = create_user_with_role(client=client, db=db, role=MANAGER)

    r = client.get(f"{API}/metrics/", headers=headers)

    assert r.status_code == 200
    metrics = r.json()
    assert set(metrics["users_by_role"]) == {role.value for role in Role}
    assert metrics["users_by_role"]["manager"] >= 1
    assert metrics["total_users"] == sum(metrics["users_by_role"].values())
    assert metrics["total_items"] >= 0
