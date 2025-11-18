#!/usr/bin/env python3
"""
Metrics Rollup — агрегация api.jsonl и bot.jsonl

Читает логи, группирует по kind, считает:
- count (общее число событий)
- err_rate (доля ошибок, если есть поле error/status)
- idempotent_rate (доля повторных вызовов с одинаковыми ID)
- latency_p50, latency_p95 (если есть поле duration_ms)

Выход:
- logs/metrics_rollup.json
- logs/metrics_rollup.txt (human-readable)
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median, quantiles
from typing import Any, Dict, List


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Загрузить JSONL файл."""
    if not path.exists():
        return []
    
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️  Skip malformed line in {path}: {e}", file=sys.stderr)
    
    return records


def compute_percentile(values: List[float], p: float) -> float:
    """Вычислить перцентиль (p ∈ [0,1])."""
    if not values:
        return 0.0
    
    if len(values) == 1:
        return values[0]
    
    # quantiles() требует n≥2; для p50 используем median
    if p == 0.5:
        return median(values)
    
    try:
        # quantiles(data, n=100) → 99 точек [p1, p2, ..., p99]
        # для p95: индекс 94 (0-based)
        n = 100
        qs = quantiles(values, n=n)
        idx = int(p * n) - 1
        return qs[min(idx, len(qs)-1)]
    except Exception:
        return sorted(values)[int(len(values) * p)]


def aggregate_metrics(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Агрегировать метрики по kind."""
    stats = defaultdict(lambda: {
        'count': 0,
        'errors': 0,
        'latencies': [],
        'ids': set()  # для idempotency check
    })
    
    for rec in records:
        kind = rec.get('kind', 'unknown')
        stat = stats[kind]
        
        stat['count'] += 1
        
        # Error rate (если есть поля error/status/outcome)
        if rec.get('error') or rec.get('status') == 'error' or rec.get('outcome') == 'error':
            stat['errors'] += 1
        
        # Latency (duration_ms или latency_ms) — проверяем и в fields
        lat = rec.get('duration_ms') or rec.get('latency_ms')
        if lat is None and 'fields' in rec:
            lat = rec['fields'].get('latency_ms') or rec['fields'].get('duration_ms')
        
        if lat is not None:
            try:
                stat['latencies'].append(float(lat))
            except (ValueError, TypeError):
                pass
        
        # Idempotency check (если есть id/task_id/expense_id)
        item_id = rec.get('id') or rec.get('task_id') or rec.get('expense_id')
        if item_id:
            stat['ids'].add(item_id)
    
    # Финализация
    result = {}
    for kind, stat in stats.items():
        count = stat['count']
        err_rate = stat['errors'] / count if count > 0 else 0.0
        
        # Idempotent rate: доля уникальных ID / count (если < 1, значит были повторы)
        unique_ids = len(stat['ids'])
        idempotent_rate = unique_ids / count if count > 0 and unique_ids > 0 else 1.0
        
        # Compute percentiles (p50, p95) only if latencies ≥10
        lats = stat['latencies']
        p50 = compute_percentile(lats, 0.5) if len(lats) >= 10 else None
        p95 = compute_percentile(lats, 0.95) if len(lats) >= 10 else None
        
        result[kind] = {
            'count': count,
            'err_rate': round(err_rate, 4),
            'idempotent_rate': round(idempotent_rate, 4),
            'latency_p50': round(p50, 2) if p50 is not None else None,
            'latency_p95': round(p95, 2) if p95 is not None else None
        }
    
    return result


def write_outputs(rollup: Dict[str, Dict[str, Any]], out_json: Path, out_txt: Path):
    """Записать результаты в JSON и TXT."""
    # JSON
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(rollup, f, indent=2, ensure_ascii=False)
    
    # TXT
    lines = []
    lines.append("=" * 80)
    lines.append("METRICS ROLLUP")
    lines.append("=" * 80)
    lines.append("")
    
    for kind in sorted(rollup.keys()):
        m = rollup[kind]
        lines.append(f"[{kind}]")
        lines.append(f"  count: {m['count']}")
        lines.append(f"  err_rate: {m['err_rate']:.2%}")
        lines.append(f"  idempotent_rate: {m['idempotent_rate']:.2%}")
        
        if m['latency_p50'] is not None:
            lines.append(f"  latency_p50: {m['latency_p50']:.2f} ms")
        if m['latency_p95'] is not None:
            lines.append(f"  latency_p95: {m['latency_p95']:.2f} ms")
        
        lines.append("")
    
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    """Main entry point."""
    base = Path(__file__).parent.parent / 'api'
    logs_dir = base / 'logs' / 'metrics'
    
    # Auto-detect: flat files OR date-partitioned folders
    api_log = logs_dir / 'api.jsonl'
    bot_log = logs_dir / 'bot.jsonl'
    
    api_records = []
    bot_records = []
    
    # If flat files exist, use them
    if api_log.exists():
        api_records.extend(load_jsonl(api_log))
    if bot_log.exists():
        bot_records.extend(load_jsonl(bot_log))
    
    # Scan date folders (YYYY-MM-DD) for partitioned logs
    if logs_dir.exists():
        for date_dir in sorted(logs_dir.iterdir()):
            if date_dir.is_dir() and len(date_dir.name) == 10:  # YYYY-MM-DD
                api_dated = date_dir / 'api.jsonl'
                bot_dated = date_dir / 'bot.jsonl'
                
                if api_dated.exists():
                    api_records.extend(load_jsonl(api_dated))
                if bot_dated.exists():
                    bot_records.extend(load_jsonl(bot_dated))
    
    print("[Metrics Rollup]")
    print(f"   Base dir: {logs_dir}")
    
    # Load complete (combined flat + dated)
    
    all_records = api_records + bot_records
    
    print(f"   Loaded: {len(api_records)} API + {len(bot_records)} bot = {len(all_records)} total")
    
    if not all_records:
        print("[WARNING] No records found, exiting.")
        sys.exit(0)
    
    # Aggregate
    rollup = aggregate_metrics(all_records)
    
    print(f"   Aggregated {len(rollup)} unique kinds")
    
    # Output
    out_json = base / 'logs' / 'metrics_rollup.json'
    out_txt = base / 'logs' / 'metrics_rollup.txt'
    
    write_outputs(rollup, out_json, out_txt)
    
    print(f"[OK] Output:")
    print(f"   {out_json}")
    print(f"   {out_txt}")
    
    # Quick summary
    kinds_with_p95 = [k for k, m in rollup.items() if m['latency_p95'] is not None and m['count'] >= 10]
    if kinds_with_p95:
        max_p95 = max(rollup[k]['latency_p95'] for k in kinds_with_p95)
        print(f"\n[Metrics] Max p95 (count>=10): {max_p95:.2f} ms")
        
        if max_p95 > 4000:
            print(f"[WARNING] p95 exceeds 4s threshold")
    
    print("\n[PASS] Metrics rollup COMPLETE")


if __name__ == '__main__':
    main()
