"""Seed initial admin user for authentication"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Employee, AuthCredential, Base
from auth import hash_password

# Database URL (from environment or default)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:////data/workledger.db')

def seed_admin():
    """Create initial admin user"""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(Employee).filter(Employee.role == 'admin').first()
        if existing_admin:
            print(f"⚠️  Admin user already exists: {existing_admin.full_name}")
            print(f"   Employee ID: {existing_admin.id}")
            
            # Check if credentials exist
            existing_cred = db.query(AuthCredential).filter(
                AuthCredential.employee_id == existing_admin.id
            ).first()
            if existing_cred:
                print(f"   Username: {existing_cred.username}")
                print("   Password: (already set)")
            else:
                print("   Warning: No credentials found for this admin")
            
            return
        
        # Create admin employee
        admin = Employee(
            full_name="System Administrator",
            role="admin",
            is_active=True,
            telegram_id=None  # No Telegram binding initially
        )
        db.add(admin)
        db.flush()  # Get admin.id
        
        # Create password credentials
        credentials = AuthCredential(
            employee_id=admin.id,
            username="admin",
            password_hash=hash_password("admin123"),
            failed_attempts=0
        )
        db.add(credentials)
        
        db.commit()
        
        print("✅ Admin user created successfully")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Employee ID: {admin.id}")
        print("")
        print("⚠️  IMPORTANT: Change password after first login!")
        print("")
        print("Next steps:")
        print("  1. Open http://localhost:8088/login.html")
        print("  2. Login with admin/admin123")
        print("  3. Go to /employees.html to manage users")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
