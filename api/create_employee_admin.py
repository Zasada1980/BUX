"""Create Employee admin for web interface."""
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base as MainBase, Employee, AuthCredential
import bcrypt

DB_URL = "sqlite:////app/data/workledger.db"
engine = create_engine(DB_URL)
MainBase.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

try:
    # Check if employee admin exists
    existing_employee = db.query(Employee).filter(Employee.role == 'admin').first()
    
    if existing_employee:
        print(f"✅ Employee admin exists: ID={existing_employee.id}, name={existing_employee.name}")
    else:
        # Create employee admin
        employee = Employee(
            full_name="Administrator",
            role="admin",
            is_active=True
        )
        db.add(employee)
        db.flush()
        print(f"✅ Employee admin created: ID={employee.id}")
        
        # Check if auth_credential exists for this employee
        existing_cred = db.query(AuthCredential).filter(AuthCredential.employee_id == employee.id).first()
        if not existing_cred:
            # Create auth credential
            cred = AuthCredential(
                username="admin",
                password_hash=hash_password("admin123"),
                employee_id=employee.id
            )
            db.add(cred)
            print(f"✅ Employee auth credential created: username=admin")
        else:
            print(f"✅ Employee auth credential exists: username={existing_cred.username}")
        
        db.commit()
    
    # List all employees
    all_employees = db.query(Employee).all()
    print(f"\n📋 Total employees: {len(all_employees)}")
    for emp in all_employees:
        print(f"  - ID={emp.id}, name={emp.name}, role={emp.role}, active={emp.active}")

except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()
