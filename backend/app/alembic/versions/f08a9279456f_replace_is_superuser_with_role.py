"""replace is_superuser with role

Revision ID: f08a9279456f
Revises: fe56fa70289e
Create Date: 2026-11-09 12:51:22.576155

Adds user.role (VARCHAR, not a native enum, so new roles need no migration),
promotes former superusers to 'admin' and drops is_superuser.
Downgrade maps 'admin' back to is_superuser = true; manager/member become
regular users, because the old schema cannot express those roles.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f08a9279456f'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user',
        sa.Column('role', sa.String(length=20), server_default='member', nullable=False),
    )
    op.execute('UPDATE "user" SET role = \'admin\' WHERE is_superuser')
    op.drop_column('user', 'is_superuser')


def downgrade():
    op.add_column(
        'user',
        sa.Column('is_superuser', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute('UPDATE "user" SET is_superuser = true WHERE role = \'admin\'')
    # The original schema had no server default on is_superuser.
    op.alter_column('user', 'is_superuser', server_default=None)
    op.drop_column('user', 'role')
