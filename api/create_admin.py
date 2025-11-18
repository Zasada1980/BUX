"""Create admin user with credentials."""
import sys
sys.path.insert(0, '/app/api')
from db import SessionLocal
from models_users import User
from models import AuthCredential
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
db = SessionLocal()

try:
    # Check if admin exists
    admin = db.query(User).filter(User.role == 'admin', User.name != 'Unknown').first()
    if not admin:
        admin = User(name='Admin', role='admin', active=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f'✅ Admin user created: ID={admin.id}')
    else:
        print(f'✅ Admin user exists: ID={admin.id}, Name={admin.name}')

    # Check if auth credential exists
    auth = db.query(AuthCredential).filter(AuthCredential.username == 'admin').first()
    if not auth:
        password_hash = pwd_context.hash('admin123')
        auth = AuthCredential(
            username='admin',
            password_hash=password_hash,
            user_id=admin.id
        )
        db.add(auth)
        db.commit()
        print('✅ Admin credentials created: username=admin, password=admin123')
    else:
        print('✅ Admin credentials exist')

finally:
    db.close()
