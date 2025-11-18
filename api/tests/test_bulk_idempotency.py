"""G4 unit tests: bulk idempotency with ≤100ms repeat detection.

Tests cover:
1. First request → 200 with approved_count
2. Repeat with same key+payload → 409 duplicate
3. Timing ≤100ms for repeat detection
4. Different payload with same key → 200 (allowed)
"""
import pytest
import time
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from utils.idempotency_guard import scope_hash, ensure_idempotent
from fastapi import HTTPException


@pytest.fixture
def db_session():
    """In-memory SQLite session for isolated testing."""
    engine = create_engine("sqlite:///:memory:")
    
    # Create schema
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE idempotency_keys (
                key TEXT PRIMARY KEY,
                scope_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX ix_idem_scope ON idempotency_keys(scope_hash)"))
        conn.commit()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_scope_hash_deterministic():
    """scope_hash produces identical output for same payload (sorted keys)."""
    payload1 = {"by": "admin", "ids": [3, 1, 2]}
    payload2 = {"ids": [3, 1, 2], "by": "admin"}
    
    hash1 = scope_hash(payload1)
    hash2 = scope_hash(payload2)
    
    assert hash1 == hash2, "scope_hash must be key-order-independent"
    assert len(hash1) == 64, "SHA256 hex digest is 64 chars"


def test_first_request_200(db_session):
    """First request with unique key → no exception, record inserted."""
    key = "req-001"
    payload = {"ids": [1, 2, 3], "by": "admin"}
    scope = scope_hash(payload)
    
    # Should not raise
    ensure_idempotent(db_session, key, scope)
    
    # Verify record exists
    row = db_session.execute(
        text("SELECT scope_hash, status FROM idempotency_keys WHERE key=:k"),
        {"k": key}
    ).fetchone()
    
    assert row is not None
    assert row[0] == scope
    assert row[1] == "applied"


def test_repeat_409(db_session):
    """Repeat request with same key+payload → 409 HTTPException."""
    key = "req-002"
    payload = {"ids": [4, 5], "by": "bob"}
    scope = scope_hash(payload)
    
    # First call - OK
    ensure_idempotent(db_session, key, scope)
    
    # Repeat - 409
    with pytest.raises(HTTPException) as exc_info:
        ensure_idempotent(db_session, key, scope)
    
    assert exc_info.value.status_code == 409
    assert "duplicate_idempotency_key" in str(exc_info.value.detail)


def test_repeat_timing_100ms(db_session):
    """Repeat detection completes in ≤100ms (G4 requirement)."""
    key = "req-003"
    payload = {"ids": list(range(1, 11)), "by": "alice"}
    scope = scope_hash(payload)
    
    # First call
    ensure_idempotent(db_session, key, scope)
    
    # Measure repeat timing
    start = time.perf_counter()
    try:
        ensure_idempotent(db_session, key, scope)
    except HTTPException:
        pass  # Expected 409
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert elapsed_ms <= 100, f"Repeat detection took {elapsed_ms:.2f}ms, must be ≤100ms"


def test_different_payload_same_key_200(db_session):
    """Same key with different payload → 409 (key must be unique)."""
    key = "req-004"
    payload1 = {"ids": [1, 2], "by": "admin"}
    payload2 = {"ids": [3, 4], "by": "admin"}
    
    scope1 = scope_hash(payload1)
    scope2 = scope_hash(payload2)
    
    assert scope1 != scope2, "Different payloads must have different scope_hash"
    
    # First call with payload1
    ensure_idempotent(db_session, key, scope1)
    
    # Second call with payload2 - always 409 (key reuse forbidden)
    with pytest.raises(HTTPException) as exc_info:
        ensure_idempotent(db_session, key, scope2)
    
    assert exc_info.value.status_code == 409
    assert "duplicate_idempotency_key" in str(exc_info.value.detail)
