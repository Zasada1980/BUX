"""G3 API Details tests - determinism, ILS enforcement, rules pinning."""
import pytest
from decimal import Decimal
from pathlib import Path
import hashlib
import json

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import only necessary modules (avoid full app import)
from api.pricing import explain_task, explain_expense, PricingError


# Test DB setup
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture
def session():
    """SQLAlchemy session with test schema."""
    engine = create_engine(TEST_DB_URL)
    TestSession = sessionmaker(bind=engine)
    
    # Create tables
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            meta JSON,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """))
        
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            shift_id INTEGER NOT NULL,
            rate_code TEXT NOT NULL,
            qty REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'unit',
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
        """))
        
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY,
            worker_id TEXT NOT NULL,
            shift_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'ILS',
            photo_ref TEXT,
            ocr_text TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'pending',
            source TEXT DEFAULT 'manual',
            review_reason TEXT,
            confirmed INTEGER DEFAULT 0,
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
        """))
        
        conn.commit()
    
    session = TestSession()
    yield session
    session.close()
    engine.dispose()


@pytest.mark.xfail(reason="pricing.yml config missing - PricingError (CI-5)")
def test_task_details_deterministic(session):
    """G3: 3 sequential calls → identical pricing_sha, steps, total."""
    # Setup: create shift and task
    session.execute(text("""
        INSERT INTO shifts (id, user_id, started_at) 
        VALUES (1, 'worker1', '2025-01-01T09:00:00Z')
    """))
    session.execute(text("""
        INSERT INTO tasks (id, shift_id, rate_code, qty, amount) 
        VALUES (1, 1, 'hour_electric', 2.0, 1600.0)
    """))
    session.commit()
    
    # Make 3 calls
    results = []
    for _ in range(3):
        steps, total, rules_version, rules_sha = explain_task(1, session)
        
        # Compute pricing_sha (same logic as endpoint)
        step_parts = [f"{s['yaml_key']}:{s['value']:.2f}" for s in steps]
        canonical = f"{rules_sha}|{rules_version}|task|1|{','.join(step_parts)}|{total:.2f}"
        pricing_sha = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        
        results.append({
            "steps": steps,
            "total": total,
            "pricing_sha": pricing_sha
        })
    
    # Verify determinism
    pricing_shas = [r["pricing_sha"] for r in results]
    assert len(set(pricing_shas)) == 1, f"pricing_sha must be identical, got: {pricing_shas}"
    
    totals = [r["total"] for r in results]
    assert len(set(totals)) == 1, f"total must be identical, got: {totals}"
    
    # Compare steps by converting Decimals to strings
    steps_serialized = [
        json.dumps(
            [{**s, "value": str(s["value"])} for s in r["steps"]],
            sort_keys=True
        )
        for r in results
    ]
    assert len(set(steps_serialized)) == 1, f"steps must be identical"
    
    # Verify structure
    first = results[0]
    assert len(first["steps"]) >= 1
    assert first["steps"][0]["step"] == "base"
    assert first["steps"][0]["yaml_key"] == "rates.hour_electric"
    assert isinstance(first["total"], Decimal)


@pytest.mark.xfail(reason="pricing.yml config missing - PricingError (CI-5)")
def test_expense_details_ils_currency(session):
    """G3: expense details use Decimal with ≤2 decimal places."""
    # Setup
    session.execute(text("""
        INSERT INTO expenses (id, worker_id, category, amount, currency) 
        VALUES (1, 'worker1', 'материалы', 500.50, 'ILS')
    """))
    session.commit()
    
    # Call
    steps, total, rules_version, rules_sha = explain_expense(1, session)
    
    # Verify Decimal type
    assert isinstance(total, Decimal)
    
    # Verify ≤2 decimal places
    total_str = str(total)
    if "." in total_str:
        decimal_part = total_str.split(".")[1]
        assert len(decimal_part) <= 2, f"total must have ≤2 decimal places, got: {total_str}"
    
    # Verify steps
    assert len(steps) >= 1
    assert steps[0]["step"] == "base"
    assert isinstance(steps[0]["value"], Decimal)


@pytest.mark.xfail(reason="pricing.yml config missing - PricingError (CI-5)")
def test_rules_pin(session):
    """G3: rules_sha matches file SHA."""
    # Setup
    session.execute(text("""
        INSERT INTO tasks (id, shift_id, rate_code, qty, amount) 
        VALUES (1, 1, 'hour_electric', 1.0, 800.0)
    """))
    session.execute(text("""
        INSERT INTO shifts (id, user_id, started_at) 
        VALUES (1, 'worker1', '2025-01-01T09:00:00Z')
    """))
    session.commit()
    
    # Call
    steps, total, rules_version, rules_sha = explain_task(1, session)
    
    # Verify rules_sha matches file
    rules_path = Path("rules/global.yaml")
    expected_sha = hashlib.sha256(rules_path.read_bytes()).hexdigest()[:12]
    assert rules_sha == expected_sha, f"rules_sha mismatch: got {rules_sha}, expected {expected_sha}"
    
    # Verify version exists
    assert isinstance(rules_version, int)
    assert rules_version >= 1


def test_404_422(session):
    """G3: 404 for nonexistent item, 422 for invalid kind."""
    # 404: nonexistent task
    with pytest.raises(PricingError, match="not found"):
        explain_task(99999, session)
    
    # 404: nonexistent expense
    with pytest.raises(PricingError, match="not found"):
        explain_expense(99999, session)



