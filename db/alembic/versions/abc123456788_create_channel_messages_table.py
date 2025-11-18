"""create_channel_messages_table

Revision ID: abc123456788
Revises: d6a4c8bd97ee
Create Date: 2025-11-18 16:00:00.000000

CI-8B: Create channel_messages table for INFRA-2 feature.
Stores Telegram channel message IDs for invoice/shift preview cards.
Enables auto-update (edit vs new post) for preview messages.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abc123456788'
down_revision = 'd6a4c8bd97ee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create channel_messages table."""
    op.create_table(
        'channel_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
    )
    
    # Create individual indexes
    op.create_index('ix_channel_messages_channel_id', 'channel_messages', ['channel_id'])
    op.create_index('ix_channel_messages_message_id', 'channel_messages', ['message_id'])
    op.create_index('ix_channel_messages_entity_id', 'channel_messages', ['entity_id'])


def downgrade() -> None:
    """Drop channel_messages table."""
    op.drop_index('ix_channel_messages_entity_id', table_name='channel_messages')
    op.drop_index('ix_channel_messages_message_id', table_name='channel_messages')
    op.drop_index('ix_channel_messages_channel_id', table_name='channel_messages')
    op.drop_table('channel_messages')

