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

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.db import engine, init_db
from app.core.permissions import Role
from app.models import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (email, role, password env var, local-only default password)
DEMO_USERS = [
    ("manager@example.com", Role.MANAGER, "DEMO_MANAGER_PASSWORD", "manager-demo-pass"),
    ("member@example.com", Role.MEMBER, "DEMO_MEMBER_PASSWORD", "member-demo-pass"),
]


def seed(session: Session) -> None:
    init_db(session)  # make sure the admin (FIRST_SUPERUSER) exists
    for email, role, password_var, default_password in DEMO_USERS:
        if crud.get_user_by_email(session=session, email=email):
            logger.info("Skipping %s: user already exists", email)
            continue
        password = os.environ.get(password_var, default_password)
        user_in = UserCreate(email=email, password=password, role=role)
        crud.create_user(session=session, user_create=user_in)
        logger.info("Created %s with role %s", email, role)


def main() -> None:
    if settings.FASTAPI_ENV != "development":
        raise SystemExit(
            "Refusing to seed demo users: FASTAPI_ENV must be 'development'."
        )
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
