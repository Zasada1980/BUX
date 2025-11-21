"""add user profile fields

Revision ID: 82b375e8cb03
Revises: d0d215bdd858
Create Date: 2025-11-22 00:09:29.727929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82b375e8cb03'
down_revision: Union[str, Sequence[str], None] = 'd0d215bdd858'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user profile fields: telegram_username, instagram_nickname, phone, daily_salary.
    
    Problem: models_users.py defines these columns but they don't exist in DB (cloud migration d0d215bdd858).
    Symptom: OperationalError: no such column: users.telegram_username on /api/users endpoint.
    Solution: Add 4 optional profile columns to users table.
    """
    # Add telegram_username (e.g., @john_doe)
    op.add_column('users', sa.Column('telegram_username', sa.String(), nullable=True))
    
    # Add instagram_nickname (for linking to real employee)
    op.add_column('users', sa.Column('instagram_nickname', sa.String(), nullable=True))
    
    # Add phone number (auxiliary field)
    op.add_column('users', sa.Column('phone', sa.String(), nullable=True))
    
    # Add daily_salary in ₪ (Numeric(10,2) for precision)
    op.add_column('users', sa.Column('daily_salary', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    """Remove user profile fields."""
    op.drop_column('users', 'daily_salary')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'instagram_nickname')
    op.drop_column('users', 'telegram_username')
