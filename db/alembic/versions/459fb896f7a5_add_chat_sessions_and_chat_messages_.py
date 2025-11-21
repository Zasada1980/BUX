"""Add chat_sessions and chat_messages tables

Revision ID: 459fb896f7a5
Revises: 8332a204ec53
Create Date: 2025-11-20 22:35:17.121605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '459fb896f7a5'
down_revision: Union[str, Sequence[str], None] = '8332a204ec53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE')
    )
    op.create_index('ix_chat_sessions_employee_id', 'chat_sessions', ['employee_id'])
    
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE')
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_employee_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
