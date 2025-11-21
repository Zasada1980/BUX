"""
INFRA-1/2 Smoke Test - Verify telegram_users and channel_messages tables.

Tests:
1. INFRA-1: TelegramUser model exists, RBAC works
2. INFRA-2: ChannelMessage model exists
3. Migration 0024 applied successfully
4. Seed data exists (admin user)

CI-6 Refactoring:
- Removed manual engine/SessionLocal creation
- Use conftest fixtures: db_engine_and_session, seed_telegram_admin, db_session
- Removed 3 xfail decorators (seed_telegram_admin provides admin user)
"""
from sqlalchemy import inspect
from models import TelegramUser, ChannelMessage


def test_infra_1_model(db_engine_and_session):
    """Test INFRA-1: TelegramUser model and table."""
    engine, SessionLocal, Base = db_engine_and_session
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "telegram_users" in tables, "telegram_users table not found"

    # Check columns
    columns = {col['name'] for col in inspector.get_columns("telegram_users")}
    required = {"id", "telegram_id", "user_id", "role", "display_name", "is_active", "created_at", "updated_at"}
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"

    # Check indexes
    indexes = inspector.get_indexes("telegram_users")
    index_names = {idx['name'] for idx in indexes}
    assert "ix_telegram_users_telegram_id" in index_names, "Missing telegram_id index"
    assert "ix_telegram_users_user_id" in index_names, "Missing user_id index"
    assert "ix_telegram_users_role" in index_names, "Missing role index"


# CI-7B: Composite index ix_channel_messages_entity_lookup added in models.py
def test_infra_2_model(db_engine_and_session):
    """Test INFRA-2: ChannelMessage model and table."""
    engine, SessionLocal, Base = db_engine_and_session
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "channel_messages" in tables, "channel_messages table not found"

    # Check columns
    columns = {col['name'] for col in inspector.get_columns("channel_messages")}
    required = {"id", "channel_id", "message_id", "entity_type", "entity_id", "content_hash", "created_at", "updated_at"}
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"

    # Check indexes
    indexes = inspector.get_indexes("channel_messages")
    index_names = {idx['name'] for idx in indexes}
    assert "ix_channel_messages_channel_id" in index_names, "Missing channel_id index"
    assert "ix_channel_messages_message_id" in index_names, "Missing message_id index"
    assert "ix_channel_messages_entity_id" in index_names, "Missing entity_id index"
    assert "ix_channel_messages_entity_lookup" in index_names, "Missing entity_lookup composite index"


def test_seed_data(db_engine_and_session, seed_telegram_admin):
    """Test seed data exists (admin TelegramUser)."""
    engine, SessionLocal, Base = db_engine_and_session
    session = SessionLocal()

    try:
        # Check admin TelegramUser
        admin = session.query(TelegramUser).filter_by(role="admin").first()
        assert admin is not None, "No admin user found"

        assert admin.telegram_id == 8473812812, f"Wrong telegram_id: {admin.telegram_id}"
        assert admin.user_id == "admin_8473812812", f"Wrong user_id: {admin.user_id}"
        assert admin.is_active == 1, "Admin user is not active"

    finally:
        session.close()


def test_rbac_logic(db_engine_and_session, seed_telegram_admin):
    """Test RBAC logic with DB lookups."""
    engine, SessionLocal, Base = db_engine_and_session
    session = SessionLocal()

    try:
        # Test admin lookup
        telegram_id = 8473812812
        user = session.query(TelegramUser).filter_by(telegram_id=telegram_id, is_active=1).first()
        assert user is not None, f"User {telegram_id} not found"
        assert user.role == "admin", f"User role is {user.role}, expected admin"

        # Test role hierarchy
        assert user.role in ("admin", "foreman", "worker"), "Invalid role"

    finally:
        session.close()


def test_channel_message_crud(db_session):
    """Test ChannelMessage CRUD operations."""
    # Create
    msg = ChannelMessage(
        channel_id=-1001234567890,
        message_id=12345,
        entity_type="invoice",
        entity_id=1,
        content_hash="abc123"
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    # Read
    found = db_session.query(ChannelMessage).filter_by(
        entity_type="invoice",
        entity_id=1
    ).first()
    assert found is not None, "Channel message not found"
    assert found.channel_id == -1001234567890, "Wrong channel_id"
    assert found.message_id == 12345, "Wrong message_id"

    # Update
    found.message_id = 54321
    found.content_hash = "xyz789"
    db_session.commit()

    # Delete
    db_session.delete(found)
    db_session.commit()

    # Verify deleted
    deleted = db_session.query(ChannelMessage).filter_by(id=msg.id).first()
    assert deleted is None, "Channel message not deleted"

