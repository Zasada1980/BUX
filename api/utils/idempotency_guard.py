"""Idempotency guard for G4 bulk operations.

Provides scope_hash() for canonical payload representation and 
ensure_idempotent() guard with 409 HTTPException on duplicate keys.
"""
import hashlib
import json
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text


def scope_hash(payload: Dict[str, Any]) -> str:
    """Compute SHA256 hash of canonical JSON payload for scope validation.
    
    Args:
        payload: Request payload (dict)
        
    Returns:
        SHA256 hex digest (64 chars) of sorted canonical JSON
        
    Example:
        >>> scope_hash({"ids": [3, 1, 2], "user": "bob"})
        'a1b2c3...' (64 chars)
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_idempotent(
    session: Session, key: str, scope: str
) -> None:
    """Guard against duplicate idempotency key.
    
    Raises HTTPException 409 if key exists (regardless of scope).
    Otherwise, inserts new idempotency_keys record with status='applied'.
    
    Args:
        session: SQLAlchemy session
        key: X-Idempotency-Key header value (max 80 chars, unique)
        scope: SHA256 scope_hash of request payload
        
    Raises:
        HTTPException: 409 if key already exists
        
    Example:
        ensure_idempotent(session, "req-123", scope_hash(payload))
    
    Note:
        Key is PRIMARY KEY - no reuse allowed. Clients must use unique keys.
    """
    # Check existing key
    existing = session.execute(
        text("SELECT scope_hash FROM idempotency_keys WHERE key=:k"),
        {"k": key}
    ).fetchone()
    
    if existing:
        # Key exists - always 409 (scope match or not)
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate_idempotency_key",
                "message": f"Request with key '{key}' already processed",
                "scope_hash": existing[0],
            },
        )
    
    # Insert new key
    session.execute(
        text("INSERT INTO idempotency_keys(key, scope_hash, status) VALUES(:k, :s, 'applied')"),
        {"k": key, "s": scope}
    )

