"""SQLite Backup/Restore with atomic operations and SHA256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path


def _sha256(p: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(db_path: str, out_dir: str) -> Path:
    """Create atomic SQLite backup with manifest entry.
    
    Args:
        db_path: Path to source SQLite database
        out_dir: Output directory for backups
        
    Returns:
        Path to created backup file
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    ts = time.strftime("%Y%m%d-%H%M")
    dst = out / f"{ts}-db.sqlite3"
    
    # Safe SQLite backup API (handles WAL mode correctly)
    con_src = sqlite3.connect(db_path)
    con_dst = sqlite3.connect(dst.as_posix())
    with con_dst:
        con_src.backup(con_dst)
    con_dst.close()
    con_src.close()
    
    sha = _sha256(dst)
    size_bytes = dst.stat().st_size
    
    # Append manifest entry
    manifest_path = out / "manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as mf:
        entry = {
            "ts": ts,
            "file": dst.name,
            "sha256": sha,
            "size_bytes": size_bytes,
            "encrypted": False,
        }
        mf.write(json.dumps(entry) + "\n")
    
    return dst


def restore(db_path: str, backup_file: str) -> None:
    """Restore database from backup with atomic replacement.
    
    Args:
        db_path: Path to target database
        backup_file: Path to backup file
        
    Note:
        Requires API to be stopped for safe restoration.
    """
    b = Path(backup_file)
    if not b.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    
    tmp = Path(db_path + ".restore_tmp")
    shutil.copy2(b, tmp)
    
    # Atomic replacement
    if os.path.exists(db_path):
        os.replace(tmp, db_path)
    else:
        shutil.move(tmp, db_path)


def main():
    ap = argparse.ArgumentParser(description="SQLite backup/restore utility")
    ap.add_argument("cmd", choices=["backup", "restore"], help="Command to execute")
    ap.add_argument("--db", required=True, help="Database path")
    ap.add_argument("--out", default="backups", help="Output directory for backups")
    ap.add_argument("--file", help="Backup file path (required for restore)")
    
    a = ap.parse_args()
    
    if a.cmd == "backup":
        p = backup(a.db, a.out)
        print(json.dumps({"ok": True, "file": p.as_posix()}))
    else:
        if not a.file:
            ap.error("--file required for restore")
        restore(a.db, a.file)
        print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
