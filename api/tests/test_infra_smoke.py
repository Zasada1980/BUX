"""
INFRA-1/2 Smoke Test - Verify telegram_users and channel_messages tables.

Tests:
1. INFRA-1: TelegramUser model exists, RBAC works
2. INFRA-2: ChannelMessage model exists
3. Migration 0024 applied successfully
4. Seed data exists (admin user)
"""
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from models import TelegramUser, ChannelMessage

DB_PATH = "/data/workledger.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)

def test_infra_1_model():
    """Test INFRA-1: TelegramUser model and table."""
    print("🧪 Test 1: INFRA-1 TelegramUser model...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert "telegram_users" in tables, "❌ telegram_users table not found"
    print("  ✅ telegram_users table exists")
    
    # Check columns
    columns = {col['name'] for col in inspector.get_columns("telegram_users")}
    required = {"id", "telegram_id", "user_id", "role", "display_name", "is_active", "created_at", "updated_at"}
    missing = required - columns
    assert not missing, f"❌ Missing columns: {missing}"
    print(f"  ✅ All required columns present: {required}")
    
    # Check indexes
    indexes = inspector.get_indexes("telegram_users")
    index_names = {idx['name'] for idx in indexes}
    assert "ix_telegram_users_telegram_id" in index_names, "❌ Missing telegram_id index"
    assert "ix_telegram_users_user_id" in index_names, "❌ Missing user_id index"
    assert "ix_telegram_users_role" in index_names, "❌ Missing role index"
    print(f"  ✅ All indexes present: {index_names}")
    
    print("✅ Test 1 PASS\n")


def test_infra_2_model():
    """Test INFRA-2: ChannelMessage model and table."""
    print("🧪 Test 2: INFRA-2 ChannelMessage model...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert "channel_messages" in tables, "❌ channel_messages table not found"
    print("  ✅ channel_messages table exists")
    
    # Check columns
    columns = {col['name'] for col in inspector.get_columns("channel_messages")}
    required = {"id", "channel_id", "message_id", "entity_type", "entity_id", "content_hash", "created_at", "updated_at"}
    missing = required - columns
    assert not missing, f"❌ Missing columns: {missing}"
    print(f"  ✅ All required columns present: {required}")
    
    # Check indexes
    indexes = inspector.get_indexes("channel_messages")
    index_names = {idx['name'] for idx in indexes}
    assert "ix_channel_messages_channel_id" in index_names, "❌ Missing channel_id index"
    assert "ix_channel_messages_message_id" in index_names, "❌ Missing message_id index"
    assert "ix_channel_messages_entity_id" in index_names, "❌ Missing entity_id index"
    assert "ix_channel_messages_entity_lookup" in index_names, "❌ Missing entity_lookup composite index"
    print(f"  ✅ All indexes present: {index_names}")
    
    print("✅ Test 2 PASS\n")


def test_seed_data():
    """Test seed data exists (admin user)."""
    print("🧪 Test 3: Seed data (admin user)...")
    
    session = SessionLocal()
    try:
        # Check admin user
        admin = session.query(TelegramUser).filter_by(role="admin").first()
        assert admin is not None, "❌ No admin user found"
        print(f"  ✅ Admin user exists: TG ID {admin.telegram_id} → User ID {admin.user_id}")
        
        assert admin.telegram_id == 8473812812, f"❌ Wrong telegram_id: {admin.telegram_id}"
        assert admin.user_id == "admin_8473812812", f"❌ Wrong user_id: {admin.user_id}"
        assert admin.is_active == 1, "❌ Admin user is not active"
        print("  ✅ Admin user has correct data")
        
        # Count total users
        total = session.query(TelegramUser).count()
        print(f"  ✅ Total users in DB: {total}")
        
    finally:
        session.close()
    
    print("✅ Test 3 PASS\n")


def test_rbac_logic():
    """Test RBAC logic with DB lookups."""
    print("🧪 Test 4: RBAC logic (DB lookups)...")
    
    session = SessionLocal()
    try:
        # Test admin lookup
        telegram_id = 8473812812
        user = session.query(TelegramUser).filter_by(telegram_id=telegram_id, is_active=1).first()
        
        assert user is not None, f"❌ User {telegram_id} not found"
        assert user.role == "admin", f"❌ User role is {user.role}, expected admin"
        print(f"  ✅ User {telegram_id} found with role '{user.role}'")
        
        # Test role hierarchy
        assert user.role in ("admin", "foreman", "worker"), "❌ Invalid role"
        print("  ✅ Role hierarchy valid")
        
    finally:
        session.close()
    
    print("✅ Test 4 PASS\n")


def test_channel_message_crud():
    """Test ChannelMessage CRUD operations."""
    print("🧪 Test 5: ChannelMessage CRUD...")
    
    session = SessionLocal()
    try:
        # Create
        msg = ChannelMessage(
            channel_id=-1001234567890,
            message_id=12345,
            entity_type="invoice",
            entity_id=1,
            content_hash="abc123"
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        print(f"  ✅ Created channel_message: ID {msg.id}")
        
        # Read
        found = session.query(ChannelMessage).filter_by(
            entity_type="invoice",
            entity_id=1
        ).first()
        assert found is not None, "❌ Channel message not found"
        assert found.channel_id == -1001234567890, "❌ Wrong channel_id"
        assert found.message_id == 12345, "❌ Wrong message_id"
        print(f"  ✅ Read channel_message: channel_id={found.channel_id}, message_id={found.message_id}")
        
        # Update
        found.message_id = 54321
        found.content_hash = "xyz789"
        session.commit()
        print(f"  ✅ Updated channel_message: new message_id={found.message_id}")
        
        # Delete
        session.delete(found)
        session.commit()
        print("  ✅ Deleted channel_message")
        
        # Verify deleted
        deleted = session.query(ChannelMessage).filter_by(id=msg.id).first()
        assert deleted is None, "❌ Channel message not deleted"
        print("  ✅ Verified deletion")
        
    finally:
        session.close()
    
    print("✅ Test 5 PASS\n")


if __name__ == "__main__":
    print("🚀 INFRA-1/2 SMOKE TEST\n")
    print("=" * 60)
    
    try:
        test_infra_1_model()
        test_infra_2_model()
        test_seed_data()
        test_rbac_logic()
        test_channel_message_crud()
        
        print("=" * 60)
        print("✅ ALL TESTS PASS - INFRA-1/2 READY FOR PRODUCTION\n")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
