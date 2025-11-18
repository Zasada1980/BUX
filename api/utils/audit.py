"""Lightweight metrics/audit helpers for API endpoints.

This module complements DB-level audit logging by writing compact
metrics events to a JSONL file for quick local inspection.
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _logs_dir() -> Path:
    """
    Get logs directory with date-based rotation (TD-B4).
    
    Returns:
        Path to logs/metrics/YYYY-MM-DD/
    """
    base = os.getenv("LOGS_DIR", "logs")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = Path(base) / "metrics" / today
    p.mkdir(parents=True, exist_ok=True)
    return p


def record_metric(
    kind: str,
    fields: Dict[str, Any] | None = None,
    outcome: str | None = None,
    model: str | None = None,
    intent: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: float | None = None,
    confidence: float | None = None,
) -> None:
    """Append a single metric event to logs/metrics/api.jsonl.

    Args:
        kind: Short event kind, e.g. "preview.issue", "suggest.apply", "agent.categorize".
        fields: Arbitrary dict with event fields (ids, versions, sizes, etc.).
        outcome: Optional outcome: accepted|abstained|rejected.
        model: LLM model name (e.g. "llama3.2:3b-instruct-fp16").
        intent: Agent intent/routing (e.g. "expense.categorize", "pricing.explain").
        tokens_in: Input tokens consumed.
        tokens_out: Output tokens generated.
        latency_ms: Agent call latency in milliseconds.
        confidence: Agent confidence score (0.0-1.0).
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "fields": fields or {},
    }
    if outcome:
        entry["outcome"] = outcome
    if model:
        entry["model"] = model
    if intent:
        entry["intent"] = intent
    if tokens_in is not None:
        entry["tokens_in"] = tokens_in
    if tokens_out is not None:
        entry["tokens_out"] = tokens_out
    if latency_ms is not None:
        entry["latency_ms"] = latency_ms
    if confidence is not None:
        entry["confidence"] = confidence
    out = _logs_dir() / "api.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_action(actor: str, action: str, payload: Dict[str, Any] | None = None, outcome: str | None = None) -> None:
    """Optional convenience wrapper for future use.

    Currently proxies to record_metric to keep footprint minimal; DB audit
    is handled separately in API code via _audit().
    """
    record_metric(f"action:{action}", {"actor": actor, **(payload or {})}, outcome=outcome)


def track_agent_call(intent: str, model: str = "ollama-local") -> "AgentCallTracker":
    """Context manager for tracking agent calls with latency and token metrics.
    
    Usage:
        with track_agent_call("expense.categorize", model="llama3.2:3b") as tracker:
            result = call_agent(...)
            tracker.set_tokens(in_tokens=150, out_tokens=50)
            tracker.set_confidence(0.85)
            tracker.set_outcome("accepted")
    """
    return AgentCallTracker(intent, model)


class AgentCallTracker:
    """Helper context manager for tracking agent calls."""
    
    def __init__(self, intent: str, model: str):
        self.intent = intent
        self.model = model
        self.start_time: float | None = None
        self.tokens_in: int | None = None
        self.tokens_out: int | None = None
        self.confidence: float | None = None
        self.outcome: str | None = None
        
    def __enter__(self):
        import time
        self.start_time = time.monotonic()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        latency_ms = (time.monotonic() - (self.start_time or 0)) * 1000
        record_metric(
            kind=f"agent.{self.intent}",
            fields={},
            outcome=self.outcome,
            model=self.model,
            intent=self.intent,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            latency_ms=latency_ms,
            confidence=self.confidence,
        )
        return False  # Don't suppress exceptions
        
    def set_tokens(self, in_tokens: int, out_tokens: int):
        """Set token counts."""
        self.tokens_in = in_tokens
        self.tokens_out = out_tokens
        
    def set_confidence(self, confidence: float):
        """Set confidence score (0.0-1.0)."""
        self.confidence = confidence
        
    def set_outcome(self, outcome: str):
        """Set outcome: accepted|abstained|rejected."""
        self.outcome = outcome

