"""Idempotency context manager for G4 gate (NOOP ≤100ms)."""
from contextlib import contextmanager
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Any, Dict, Generator
import json
import hashlib


def scope_hash_dict(payload: Dict[str, Any]) -> str:
    """Calculate SHA256 hash of canonical JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@contextmanager
def idempotent_operation(
    session: Session,
    key: str | None,
    scope: str,
    payload: Dict[str, Any]
) -> Generator[Dict[str, Any] | None, None, None]:
    """Context manager for idempotent operations with result caching.
    
    If key exists:
      - Returns cached result (NOOP, ≤100ms)
      - Validates scope_hash matches (409 if different payload)
    
    If key is new:
      - Yields None (execute operation)
      - Caches result in idempotency_keys.result_json
    
    Usage:
        with idempotent_operation(s, key, scope, payload) as cached:
            if cached:
                return cached  # NOOP path
            # Execute operation
            result = {...}
            return result
    
    Args:
        session: Database session
        key: X-Idempotency-Key header (optional)
        scope: Scope identifier (e.g., "invoice.build")
        payload: Request payload dict
        
    Yields:
        Dict with cached result if key exists, None otherwise
        
    Raises:
        HTTPException: 409 if key exists with different payload
    """
    if not key:
        # No idempotency key - just execute
        yield None
        return
    
    payload_hash = scope_hash_dict(payload)
    
    # Check for existing key
    existing = session.execute(
        text("SELECT scope_hash, result_json FROM idempotency_keys WHERE key=:k"),
        {"k": key}
    ).fetchone()
    
    if existing:
        stored_hash, result_json = existing
        
        # Validate scope_hash matches (prevent key reuse with different payload)
        if stored_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "idempotency_key_conflict",
                    "message": f"Key '{key}' exists with different payload",
                    "expected_hash": stored_hash,
                    "actual_hash": payload_hash
                }
            )
        
        # Return cached result (NOOP path)
        cached = json.loads(result_json) if result_json else {}
        yield cached
        return
    
    # New key - execute operation and cache result
    result_holder = {}
    
    try:
        yield result_holder  # Will be populated by caller
    finally:
        # Cache result after operation completes
        if result_holder:
            session.execute(
                text("""
                    INSERT INTO idempotency_keys(key, scope_hash, status, result_json)
                    VALUES(:k, :h, 'applied', :res)
                """),
                {
                    "k": key,
                    "h": payload_hash,
                    "res": json.dumps(result_holder, ensure_ascii=False)
                }
            )
            session.commit()
