"""
Pytest Configuration and Shared Fixtures for API Tests

This conftest.py provides:
- test_db_path: Temporary DB file for each test session
- app: FastAPI app instance with test DB
- db_session: Database session for seed/test data
- client: FastAPI TestClient for HTTP requests
- seed_admin: Admin user for auth tests
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add /app to Python path (for imports like 'from models import ...')
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """
    Create a temporary database file for the entire test session.
    
    CRITICAL: This fixture runs BEFORE any imports of api.main or api.db,
    ensuring DB_PATH is set before SQLAlchemy engine is created.
    """
    # Create temp DB file
    tmp_dir = tmp_path_factory.mktemp("test_db")
    db_file = tmp_dir / "test_workledger.db"
    
    # Set DB_PATH environment variable
    os.environ["DB_PATH"] = str(db_file)
    
    # Ensure PYTEST_DISABLE_PLUGIN_AUTOLOAD is set (from ci.yml)
    if "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in os.environ:
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    
    yield str(db_file)
    
    # Cleanup: remove DB file after session
    # Note: SQLAlchemy may keep file locked, so ignore errors
    if db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            pass  # File still in use by SQLAlchemy engine


@pytest.fixture(scope="session")
def app(test_db_path):
    """
    FastAPI app instance with test database.
    
    Imports main:app AFTER test_db_path has set DB_PATH,
    ensuring db.engine uses the test database.
    
    CRITICAL FIX (CI-13): Force reload ALL api modules to pick up new DB_PATH.
    Pydantic Settings and SQLAlchemy engine are cached on first import.
    """
    import sys
    
    # Delete all api-related modules to force fresh import with new DB_PATH
    modules_to_delete = [k for k in sys.modules.keys() if k in ('config', 'db', 'models', 'main') or k.startswith('api.')]
    for mod in modules_to_delete:
        del sys.modules[mod]
    
    # Now import main (which will import freshly reloaded config + db + models)
    from main import app
    return app


@pytest.fixture(scope="session")
def db_engine_and_session(app, test_db_path):
    """
    Database engine and SessionLocal from db module.
    
    Creates schema once for entire test session.
    Returns tuple: (engine, SessionLocal, Base)
    
    CRITICAL FIX (CI-13): Force re-import of BOTH db AND models modules AFTER test_db_path is set.
    This ensures Base.metadata uses the correct test engine, not the production engine.
    """
    import sys
    
    # STEP 1: Delete BOTH db and models modules if cached
    # CRITICAL: models.Base.metadata can cache references to old db.engine
    for mod in ['db', 'models', 'models_users']:
        if mod in sys.modules:
            del sys.modules[mod]
    
    # STEP 2: Import NEW engine (will use test DB_PATH from environment)
    from db import engine, SessionLocal
    
    # STEP 3: Import Base AFTER db reload (ensures metadata uses NEW engine)
    from models import Base
    
    print(f"[CI-13] db_engine_and_session CALLED (once per session)")
    print(f"[CI-13] Engine URL: {engine.url}")
    
    # STEP 4: Drop all existing tables/indexes (clean slate for test session)
    print(f"[CI-13] Dropping all tables/indexes...")
    Base.metadata.drop_all(bind=engine)
    
    # STEP 5: Create all tables/indexes from Base.metadata
    # NOTE: index=True on models_users.User.telegram_id creates ix_users_telegram_id
    print(f"[CI-13] Creating all tables/indexes...")
    Base.metadata.create_all(bind=engine)
    print(f"[CI-13] Schema ready")
    
    return engine, SessionLocal, Base


@pytest.fixture
def db_session(db_engine_and_session):
    """
    Database session for each test.
    
    Provides clean session with automatic rollback after test.
    """
    engine, SessionLocal, Base = db_engine_and_session
    session = SessionLocal()
    
    yield session
    
    # Rollback any uncommitted changes
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def client(app):
    """
    FastAPI TestClient for HTTP requests.
    
    Uses the same app instance as db fixtures (same DB).
    """
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="session")
def seed_admin(db_engine_and_session):
    """
    Seed admin user for authentication tests.
    
    Creates:
    - Employee (id=1, name="Admin", daily_salary=0)
    - AuthCredential (username="admin", password_hash=bcrypt("admin123"))
    
    Returns: tuple (employee_id, username, plaintext_password)
    """
    engine, SessionLocal, Base = db_engine_and_session
    from models import Employee, AuthCredential  # Changed from api.models_users
    import bcrypt  # Use bcrypt directly instead of passlib (compat issue with bcrypt 5.x)
    
    session = SessionLocal()
    
    try:
        # Check if admin already exists
        existing = session.query(Employee).filter(Employee.id == 1).first()
        if existing:
            return (1, "admin", "admin123")
        
        # Create admin employee
        admin = Employee(
            id=1,
            name="Admin",  # F14: Changed from 'full_name' to 'name' (schema alignment)
            role="admin",
            active=True  # F14: Changed from 'is_active' to 'active'
        )
        session.add(admin)
        session.flush()  # Get ID
        
        # Hash password with bcrypt directly
        password_hash = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create admin credentials
        cred = AuthCredential(
            username="admin",
            password_hash=password_hash,
            employee_id=admin.id  # Changed from 'user_id' to 'employee_id'
        )
        session.add(cred)
        session.commit()
        
        return (1, "admin", "admin123")
    
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def admin_token(client, seed_admin):
    """
    Get admin JWT token for authenticated requests.
    
    Uses seed_admin fixture to ensure admin user exists,
    then logs in via /api/auth/login.
    
    Returns: JWT access token string
    """
    user_id, username, password = seed_admin
    
    response = client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })
    
    if response.status_code != 200:
        raise RuntimeError(f"Admin login failed: {response.status_code} {response.text}")
    
    data = response.json()
    return data["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    """
    Authorization headers with admin JWT token.
    
    Returns: dict {"Authorization": "Bearer <token>"}
    """
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture(scope="session")
def seed_telegram_admin(db_engine_and_session):
    """
    Seed TelegramUser admin for INFRA smoke tests.

    Creates:
    - TelegramUser (telegram_id=8473812812, user_id="admin_8473812812", role="admin")

    Returns: tuple (telegram_id, user_id, role)
    """
    engine, SessionLocal, Base = db_engine_and_session
    from models import TelegramUser
    
    session = SessionLocal()
    try:
        # Check if admin TelegramUser already exists
        existing = session.query(TelegramUser).filter_by(telegram_id=8473812812).first()
        if existing:
            return (8473812812, "admin_8473812812", "admin")

        # Create admin TelegramUser
        admin = TelegramUser(
            telegram_id=8473812812,
            user_id="admin_8473812812",
            role="admin",
            display_name="Test Admin",
            is_active=1
        )
        session.add(admin)
        session.commit()

        return (8473812812, "admin_8473812812", "admin")

    finally:
        session.close()



@pytest.fixture(scope="session", autouse=True)
def pricing_rules_env():
    """
    CI-8A: Set PRICING_RULES_PATH for test suite.
    Ensures all pricing tests use rules/global.yaml (test config).
    Production deployments should set this to production pricing file.
    """
    import os
    from pathlib import Path
    
    # Set test pricing rules path
    test_rules_path = Path("rules/global.yaml")
    os.environ["PRICING_RULES_PATH"] = str(test_rules_path)
    
    yield
    
    # Cleanup (optional - env vars typically reset between test runs)
    if "PRICING_RULES_PATH" in os.environ:
        del os.environ["PRICING_RULES_PATH"]

