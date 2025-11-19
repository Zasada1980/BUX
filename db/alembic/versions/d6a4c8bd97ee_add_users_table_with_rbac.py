"""add_users_table_with_rbac

Revision ID: d6a4c8bd97ee
Revises: cfc0d1a98ac8
Create Date: 2025-11-17 16:03:07.775096
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd6a4c8bd97ee'
down_revision: Union[str, Sequence[str], None] = 'cfc0d1a98ac8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('telegram_id', sa.BigInteger(), unique=True, nullable=True, index=True),
        sa.Column('telegram_username', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('instagram_nickname', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('daily_salary', sa.Numeric(10, 2), nullable=True),
        sa.Column('role', sa.String(), nullable=False, server_default='worker'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1', index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('users')
