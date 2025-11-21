"""ci15_add_user_extra_columns_final

Revision ID: 46dcf48d1f5c
Revises: 03fb5a6f8158
Create Date: 2025-11-21 09:12:00.607055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46dcf48d1f5c'
down_revision: Union[str, Sequence[str], None] = '459fb896f7a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """CI-15: Add User model extra columns: telegram_username, instagram_nickname, phone, daily_salary."""
    op.add_column('users', sa.Column('telegram_username', sa.String(), nullable=True))
    op.add_column('users', sa.Column('instagram_nickname', sa.String(), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(), nullable=True))
    op.add_column('users', sa.Column('daily_salary', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    """CI-15: Remove User model extra columns."""
    op.drop_column('users', 'daily_salary')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'instagram_nickname')
    op.drop_column('users', 'telegram_username')
