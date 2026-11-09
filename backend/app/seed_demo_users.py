"""Create one demo user per role for local development.

Run from backend/:  uv run python -m app.seed_demo_users

- admin:   FIRST_SUPERUSER / FIRST_SUPERUSER_PASSWORD from .env (via init_db)
- manager: manager@example.com, password $DEMO_MANAGER_PASSWORD
- member:  member@example.com,  password $DEMO_MEMBER_PASSWORD

The default passwords below are for local development only. The script is
idempotent (existing emails are skipped) and refuses to run unless
FASTAPI_ENV=development.
"""

import logging
import os
from typing import NamedTuple

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.permissions import Role
from app.models import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DemoUser(NamedTuple):
    email: str
    role: Role
    password_env_var: str
    default_password: str


DEMO_USERS = [
    DemoUser(
        email="manager@example.com",
        role=Role.MANAGER,
        password_env_var="DEMO_MANAGER_PASSWORD",
        default_password="manager-demo-pass",
    ),
    DemoUser(
        email="member@example.com",
        role=Role.MEMBER,
        password_env_var="DEMO_MEMBER_PASSWORD",
        default_password="member-demo-pass",
    ),
]


def seed(session: Session) -> None:
    init_db(session)  # make sure the admin (FIRST_SUPERUSER) exists
    for demo in DEMO_USERS:
        if crud.get_user_by_email(session=session, email=demo.email):
            logger.info("Skipping %s: user already exists", demo.email)
            continue
        password = os.environ.get(demo.password_env_var, demo.default_password)
        user_in = UserCreate(email=demo.email, password=password, role=demo.role)
        crud.create_user(session=session, user_create=user_in)
        logger.info("Created %s with role %s", demo.email, demo.role)


def main() -> None:
    if settings.FASTAPI_ENV != "development":
        raise SystemExit(
            "Refusing to seed demo users: FASTAPI_ENV must be 'development'."
        )
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
