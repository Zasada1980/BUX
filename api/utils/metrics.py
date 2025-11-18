"""
JSON metrics utility for channel operations and general telemetry.

Usage:
    from api.utils.metrics import log_metric
    
    log_metric("channel.posted", key="expense:123", msg_id=456)
    log_metric("channel.edited", key="task:789", msg_id=101)
    log_metric("channel.noop", key="expense:111", msg_id=222)
"""
import os
import json
import time
from pathlib import Path

LOG_DIR = Path(os.getenv("METRICS_DIR", "logs/metrics"))


def log_metric(name: str, **fields):
    """
    Log a metric event to JSONL.
    
    Args:
        name: Metric name (e.g., "channel.posted", "dm.sent")
        **fields: Additional metric fields (key=value pairs)
    
    Creates logs/metrics/metrics.jsonl with:
        {"ts": <timestamp>, "name": <name>, ...fields}
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    rec = {"ts": time.time(), "name": name, **fields}
    
    metrics_file = LOG_DIR / "metrics.jsonl"
    
    # Create file if doesn't exist
    if not metrics_file.exists():
        metrics_file.write_text("", encoding="utf-8")
    
    # Append metric
    with open(metrics_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
