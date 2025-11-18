"""Metrics rollup engine for Admin Dashboard.

Reads api.jsonl tail, computes aggregations by kind within time window.
Supports p50/p95 percentiles, error rates, idempotent rates.

Architecture: Date-rotated metrics (LOGS_DIR/metrics/YYYY-MM-DD/api.jsonl)
with backward compatibility fallback to flat structure.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _resolve_metrics_file() -> Path:
    """Resolve metrics file path with date rotation support.
    
    Strategy:
    1. Check LOGS_DIR/metrics/YYYY-MM-DD/api.jsonl (newest date first)
    2. Fallback to LOGS_DIR/metrics/api.jsonl (backward compatibility)
    3. Fallback to /app/logs/api.jsonl (legacy)
    
    Returns:
        Path to most recent api.jsonl file
    """
    base = Path(os.getenv("LOGS_DIR", "/app/logs"))
    
    # Primary: date-rotated structure
    metrics_root = base / "metrics"
    if metrics_root.exists():
        # Find dated directories (YYYY-MM-DD format)
        dated_dirs = sorted(
            [p for p in metrics_root.iterdir() 
             if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)],
            key=lambda p: p.name,
            reverse=True  # Newest first
        )
        
        # Return first existing api.jsonl in dated directories
        for dated_dir in dated_dirs:
            candidate = dated_dir / "api.jsonl"
            if candidate.exists():
                return candidate
        
        # Fallback: flat structure in metrics/
        flat_metrics = metrics_root / "api.jsonl"
        if flat_metrics.exists():
            return flat_metrics
    
    # Final fallback: legacy location
    legacy = base / "api.jsonl"
    return legacy


def read_tail(file_path: Path, max_lines: int = 20000) -> list[dict[str, Any]]:
    """Read last N lines from JSONL file with error handling.
    
    Args:
        file_path: Path to JSONL file
        max_lines: Maximum lines to read from tail
        
    Returns:
        List of parsed JSON objects (skips invalid lines)
    """
    if not file_path.exists():
        return []
    
    lines = []
    skipped = 0
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            # Read last max_lines efficiently
            all_lines = f.readlines()
            tail_lines = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
            
            for line in tail_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    lines.append(obj)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
    except Exception:
        # File read error, return empty
        return []
    
    return lines


def compute_rollup(
    metrics_file: Path | None = None,
    window: str = "1h",
    max_tail_lines: int = 20000,
) -> dict[str, Any]:
    """Compute metrics rollup for given time window.
    
    Args:
        metrics_file: Path to api.jsonl (auto-resolved if None)
        window: Time window ('15m', '1h', '24h')
        max_tail_lines: Maximum lines to scan from tail
        
    Returns:
        Dictionary with rollup data:
        {
            "window": "1h",
            "generated_at": "2025-11-13T10:22:00Z",
            "rows": [
                {
                    "kind": "invoice.preview",
                    "count": 42,
                    "error_rate": 0.0,
                    "idempotent_rate": 0.17,
                    "p50_ms": 38,
                    "p95_ms": 120,
                    "last_ts": "2025-11-13T10:21:45Z"
                },
                ...
            ]
        }
    """
    # Auto-resolve metrics file if not provided
    if metrics_file is None:
        metrics_file = _resolve_metrics_file()
    
    # Parse window duration
    window_duration = _parse_window(window)
    now = datetime.now(timezone.utc)
    cutoff = now - window_duration
    
    # Read tail
    events = read_tail(metrics_file, max_tail_lines)
    
    # Filter by time window
    filtered = []
    for event in events:
        ts_str = event.get("ts")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                filtered.append(event)
        except (ValueError, AttributeError):
            continue
    
    # Aggregate by kind
    by_kind: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "errors": 0,
            "idempotent_count": 0,
            "latencies": [],
            "last_ts": None,
        }
    )
    
    for event in filtered:
        kind = event.get("kind")
        if not kind:
            continue
        
        agg = by_kind[kind]
        agg["count"] += 1
        
        # Error tracking
        outcome = event.get("outcome", "").lower()
        if outcome in {"error", "failed", "rejected"}:
            agg["errors"] += 1
        
        # Idempotent tracking
        fields = event.get("fields", {})
        if isinstance(fields, dict) and fields.get("idempotent") is True:
            agg["idempotent_count"] += 1
        
        # Latency tracking
        latency_ms = event.get("latency_ms")
        if isinstance(latency_ms, (int, float)) and latency_ms >= 0:
            agg["latencies"].append(latency_ms)
        
        # Last timestamp
        ts_str = event.get("ts")
        if ts_str:
            if agg["last_ts"] is None or ts_str > agg["last_ts"]:
                agg["last_ts"] = ts_str
    
    # Compute percentiles and rates
    rows = []
    for kind, agg in sorted(by_kind.items()):
        count = agg["count"]
        error_rate = round(agg["errors"] / count, 2) if count > 0 else 0.0
        idempotent_rate = round(agg["idempotent_count"] / count, 2) if count > 0 else 0.0
        
        # Percentiles only if count >= 10
        p50_ms = None
        p95_ms = None
        if count >= 10 and agg["latencies"]:
            sorted_latencies = sorted(agg["latencies"])
            p50_ms = _percentile(sorted_latencies, 50)
            p95_ms = _percentile(sorted_latencies, 95)
        
        rows.append({
            "kind": kind,
            "count": count,
            "error_rate": error_rate,
            "idempotent_rate": idempotent_rate,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "last_ts": agg["last_ts"],
        })
    
    return {
        "window": window,
        "generated_at": now.isoformat(),
        "rows": rows,
    }


def _parse_window(window: str) -> timedelta:
    """Parse window string to timedelta."""
    if window == "15m":
        return timedelta(minutes=15)
    elif window == "1h":
        return timedelta(hours=1)
    elif window == "24h":
        return timedelta(hours=24)
    else:
        # Default to 1h
        return timedelta(hours=1)


def _percentile(sorted_values: list[float], p: int) -> int:
    """Compute percentile from sorted values.
    
    Args:
        sorted_values: Sorted list of values
        p: Percentile (0-100)
        
    Returns:
        Percentile value rounded to integer
    """
    if not sorted_values:
        return 0
    
    k = (len(sorted_values) - 1) * p / 100
    f = int(k)
    c = f + 1
    
    if c >= len(sorted_values):
        return int(sorted_values[-1])
    
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return int(d0 + d1)
