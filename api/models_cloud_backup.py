"""SQLAlchemy models for TelegramOllama API."""
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Date, Numeric, func, Boolean, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Shift(Base):
    """Shift model representing a work shift session."""
    
    __tablename__ = "shifts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    client_id = Column(Integer, nullable=True, index=True)  # FK to clients
    work_address = Column(String(500), nullable=True)  # Work site address (from schedule)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)


class IdempotencyKey(Base):
    """Idempotency key for G4 bulk operations (≤100ms repeat detection)."""
    
    __tablename__ = "idempotency_keys"
    
    key = Column(String(80), primary_key=True)
    scope_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(16), nullable=False, server_default="applied")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    """Invoice model for invoice.build endpoint (Fix 1: proper ID with refresh)."""
    
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    period_from = Column(String, nullable=False)
    period_to = Column(String, nullable=False)
    total = Column(String, nullable=False)  # Stored as string to preserve Decimal precision
    currency = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    pdf_path = Column(String, nullable=True)
    xlsx_path = Column(String, nullable=True)
    current_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    """Task model for worker tasks."""
    
    __tablename__ = "worker_tasks"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    shift_id = Column(Integer, nullable=True, index=True)
    description = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Expense(Base):
    """Expense model for worker expenses."""
    
    __tablename__ = "worker_expenses"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    shift_id = Column(Integer, nullable=True, index=True)
    category = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)  # In cents/agorot
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TelegramUser(Base):
    """
    INFRA-1: Telegram user mapping for dynamic RBAC.
    Replaces hard-coded BOT_ADMINS/FOREMEN/WORKERS env vars.
    """
    
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # Internal user ID
    role = Column(String(16), nullable=False, index=True)  # admin, foreman, worker
    display_name = Column(String(128), nullable=True)  # Optional friendly name
    is_active = Column(Integer, nullable=False, default=1)  # 1=active, 0=disabled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChannelMessage(Base):
    """
    INFRA-2: Channel message persistence for auto-update (edit vs new post).
    Stores Telegram channel message IDs for invoice/shift preview cards.
    """
    
    __tablename__ = "channel_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, nullable=False, index=True)  # Telegram channel ID
    message_id = Column(BigInteger, nullable=False, index=True)  # Telegram message ID
    entity_type = Column(String(32), nullable=False)  # invoice, shift, task
    entity_id = Column(Integer, nullable=False, index=True)  # FK to entity
    content_hash = Column(String(64), nullable=True)  # SHA256 for change detection
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_channel_messages_entity_lookup", "entity_type", "entity_id"),
    )


class Client(Base):
    """
    Client (Заказчик) model for customer management.
    Visible to all workers for shift assignment.
    """
    
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False)  # Название фирмы или имя
    nickname1 = Column(String(100), nullable=False)  # Основной никнейм
    nickname2 = Column(String(100), nullable=True)  # Альтернативный никнейм
    phone = Column(String(20), nullable=True)  # Телефон (только админ)
    daily_rate = Column(Integer, nullable=True)  # Цена за рабочий день в шекелях (только админ)
    is_active = Column(Integer, nullable=False, default=1)  # 1=active, 0=disabled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Schedule(Base):
    """
    Work schedule for next day assignments.
    Parsed from Telegram channel messages.
    """
    
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    client_id = Column(Integer, nullable=False, index=True)  # FK to clients
    worker_ids = Column(String(500), nullable=True)  # Comma-separated user IDs (optional)
    work_address = Column(String(500), nullable=True)  # Work site address (e.g., "Офер тель авив")
    notes = Column(String(500), nullable=True)  # Дополнительные заметки
    created_by = Column(Integer, nullable=False)  # Admin/Foreman user ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Salary(Base):
    """
    Salary payments for workers.
    Source: manual entry, Excel import, or auto-calculation.
    """
    
    __tablename__ = "salaries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, nullable=False, index=True)  # FK to workers/telegram_users
    amount = Column(Numeric(precision=18, scale=2), nullable=False)  # Decimal for precision
    date = Column(Date, nullable=False, index=True)  # Payment date
    source = Column(String(50), nullable=False, default='manual', index=True)  # manual, import, auto
    notes = Column(String(500), nullable=True)  # Optional comments
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Employee(Base):
    """
    Employee model for web interface authentication and management.
    Unified with TelegramUser via telegram_id (optional for password-only users).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)  # Optional (for Telegram OAuth)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # admin, foreman, worker
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    auth_credentials = relationship("AuthCredential", back_populates="employee", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="employee", cascade="all, delete-orphan")


class AuthCredential(Base):
    """
    Password-based authentication credentials.
    One-to-one with Employee (optional, for password fallback).
    """
    
    __tablename__ = "auth_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    employee = relationship("Employee", back_populates="auth_credentials")


class RefreshToken(Base):
    """
    JWT refresh tokens for web interface sessions.
    Allows token renewal without re-authentication.
    """
    
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    employee = relationship("Employee", back_populates="refresh_tokens")



