"""add_channel_messages_entity_lookup_index

Revision ID: abc123456789
Revises: f8a4b9c12d3e
Create Date: 2025-11-18 15:30:00.000000

CI-8B: Add composite index for ChannelMessage entity lookups.
This index supports efficient queries like:
  SELECT * FROM channel_messages WHERE entity_type='invoice' AND entity_id=123;

Matches __table_args__ in api/models.py (CI-7B).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abc123456789'
down_revision = 'abc123456788'  # Depends on channel_messages table creation
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create composite index for channel_messages entity lookups."""
    # CI-8B: Add composite index (entity_type, entity_id)
    # Matches CI-7B model definition:
    # Index("ix_channel_messages_entity_lookup", "entity_type", "entity_id")
    op.create_index(
        'ix_channel_messages_entity_lookup',
        'channel_messages',
        ['entity_type', 'entity_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove composite index."""
    op.drop_index('ix_channel_messages_entity_lookup', table_name='channel_messages')
