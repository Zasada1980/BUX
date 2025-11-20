#!/usr/bin/env python
"""Reset admin password to admin123"""
from models_users import User
from db import get_db_session
from passlib.context import CryptContext

session = next(get_db_session())
admin = session.query(User).filter(User.role=='admin').first()
pwd_context = CryptContext(schemes=['bcrypt'])
admin.password_hash = pwd_context.hash('admin123')
session.commit()
print('✅ Admin password reset to: admin123')
