#!/usr/bin/env python3
"""Resolve metrics file path for smoke tests and utilities.

Returns absolute path to the most recent api.jsonl file.
Uses same logic as api/metrics_rollup.py::_resolve_metrics_file()

Exit codes:
    0: Success (path printed to stdout)
    1: No metrics file found
"""
import os
import re
import sys
from pathlib import Path


def resolve_metrics_file() -> Path:
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


if __name__ == "__main__":
    metrics_path = resolve_metrics_file()
    
    if metrics_path.exists():
        print(metrics_path)
        sys.exit(0)
    else:
        print(f"ERROR: Metrics file not found: {metrics_path}", file=sys.stderr)
        sys.exit(1)
