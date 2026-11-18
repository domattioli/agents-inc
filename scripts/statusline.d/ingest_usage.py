#!/usr/bin/env python3
"""
Ingest Claude, delegated, and native guest usage into a single SQLite database.
Incremental & idempotent via (mtime, size) tracking on source files.

Sources:
  A) ~/.claude/projects/**/*.jsonl — Claude API transcripts (backend='claude')
  B) ~/.codex-bridge/usage.jsonl — Delegated usage
  C) ~/.local/state/agents-inc/native-runs/**/events.jsonl — Native guest steps

Schema: usage(uid, ts, day, backend, model, input/output/cache_read/cache_write/reasoning tokens)
CLI: python3 usage_db.py [--rebuild] [--db PATH]
"""
import sqlite3
import json
import glob
import os
import sys
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path

def get_db_path(custom_path=None):
    """Return path to usage.db, creating ~/.codex-bridge if needed."""
    if custom_path:
        return custom_path
    db_dir = Path.home() / '.codex-bridge'
    db_dir.mkdir(exist_ok=True, mode=0o700)
    return str(db_dir / 'usage.db')

def init_db(db_path):
    """Create schema if not exists."""
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usage(
            uid TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            day TEXT NOT NULL,
            backend TEXT NOT NULL,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read INTEGER DEFAULT 0,
            cache_write INTEGER DEFAULT 0,
            reasoning INTEGER DEFAULT 0
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS ix_day ON usage(day)')
    conn.execute('CREATE INDEX IF NOT EXISTS ix_model ON usage(backend,model)')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ingest_state(
            path TEXT PRIMARY KEY,
            mtime REAL,
            size INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def rebuild_db(db_path):
    """Drop all tables and rebuild."""
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)

def ingest_claude_transcripts(db_path):
    """Load Claude transcripts, dedupe by message.id, return count of new rows."""
    pattern = os.path.expanduser('~/.claude/projects/**/*.jsonl')
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    count_new = 0

    for filepath in sorted(glob.glob(pattern, recursive=True)):
        try:
            stat = os.stat(filepath)
            mtime = stat.st_mtime
            size = stat.st_size

            # Check if already ingested
            row = conn.execute(
                'SELECT mtime, size FROM ingest_state WHERE path = ?',
                (filepath,)
            ).fetchone()
            if row and row[0] == mtime and row[1] == size:
                continue  # Already ingested, skip

            # Read and ingest
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if 'message' not in obj:
                            continue
                        msg = obj['message']
                        if 'usage' not in msg:
                            continue

                        ts_str = obj.get('timestamp', '')
                        model = msg.get('model')
                        usage = msg.get('usage', {})
                        message_id = msg.get('id')

                        # Skip synthetic or empty models
                        if not model or model == '<synthetic>' or model == '' or not usage:
                            continue

                        # Parse timestamp in UTC, convert to local time for day bucketing
                        try:
                            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            ts_iso = ts.isoformat()
                            # Convert UTC to local timezone to get the local calendar day
                            ts_local = ts.astimezone()
                            day = ts_local.date().isoformat()
                        except (ValueError, AttributeError):
                            continue

                        # Dedupe by message_id
                        if message_id:
                            uid = message_id
                        else:
                            # Fallback uid if no message_id
                            uid = hashlib.sha1(f"{ts_iso}|claude|{model}|{usage}".encode(), usedforsecurity=False).hexdigest()  # nosec B324 — non-security dedup uid

                        input_tok = usage.get('input_tokens', 0)
                        output_tok = usage.get('output_tokens', 0)
                        cache_read = usage.get('cache_read_input_tokens', 0)
                        cache_write = usage.get('cache_creation_input_tokens', 0)

                        cursor = conn.execute('''
                            INSERT OR IGNORE INTO usage
                            (uid, ts, day, backend, model, input_tokens, output_tokens, cache_read, cache_write)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (uid, ts_iso, day, 'claude', model, input_tok, output_tok, cache_read, cache_write))
                        count_new += cursor.rowcount
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            # Update ingest state
            conn.execute(
                'INSERT OR REPLACE INTO ingest_state (path, mtime, size) VALUES (?, ?, ?)',
                (filepath, mtime, size)
            )
            conn.commit()

        except (IOError, OSError):
            continue

    conn.close()
    return count_new

def ingest_delegated_usage(db_path):
    """Load ~/.codex-bridge/usage.jsonl, return count of new rows."""
    path = os.path.expanduser('~/.codex-bridge/usage.jsonl')
    if not os.path.exists(path):
        return 0

    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    count_new = 0

    try:
        stat = os.stat(path)
        mtime = stat.st_mtime
        size = stat.st_size

        # Check if already fully ingested
        row = conn.execute(
            'SELECT mtime, size FROM ingest_state WHERE path = ?',
            (path,)
        ).fetchone()
        if row and row[0] == mtime and row[1] == size:
            conn.close()
            return 0

        # Read and ingest
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    ts_str = obj.get('ts')
                    backend = obj.get('backend')
                    model = obj.get('model')
                    input_tokens = obj.get('input_tokens', 0)
                    output_tokens = obj.get('output_tokens', 0)
                    reasoning_tokens = obj.get('reasoning_tokens', 0)

                    # Skip if no ts or backend
                    if not ts_str or not backend:
                        continue

                    # Skip if model is empty string (but allow null)
                    if model == '':
                        continue

                    try:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        ts_iso = ts.isoformat()
                        # Convert UTC to local timezone to get the local calendar day
                        ts_local = ts.astimezone()
                        day = ts_local.date().isoformat()
                    except (ValueError, AttributeError):
                        continue

                    # Generate uid: sha1(ts|backend|model|in|out)
                    uid = hashlib.sha1(
                        f"{ts_iso}|{backend}|{model}|{input_tokens}|{output_tokens}".encode(), usedforsecurity=False  # nosec B324 — non-security dedup uid
                    ).hexdigest()

                    cursor = conn.execute('''
                        INSERT OR IGNORE INTO usage
                        (uid, ts, day, backend, model, input_tokens, output_tokens, reasoning)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (uid, ts_iso, day, backend, model, input_tokens, output_tokens, reasoning_tokens))
                    count_new += cursor.rowcount
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        # Update ingest state
        conn.execute(
            'INSERT OR REPLACE INTO ingest_state (path, mtime, size) VALUES (?, ?, ?)',
            (path, mtime, size)
        )
        conn.commit()

    except (IOError, OSError):
        pass

    conn.close()
    return count_new

def ingest_native_usage(db_path):
    """Ingest each guest step once; run.end totals repeat the same usage."""
    pattern = os.path.expanduser('~/.local/state/agents-inc/native-runs/*/*/*/events.jsonl')
    conn = sqlite3.connect(db_path)
    count = 0
    for path in sorted(glob.glob(pattern)):
        try:
            stat = os.stat(path)
            state = conn.execute('SELECT mtime, size FROM ingest_state WHERE path = ?', (path,)).fetchone()
            if state == (stat.st_mtime, stat.st_size):
                continue
            backend = model = None
            with open(path, encoding='utf-8') as stream:
                for index, line in enumerate(stream):
                    try:
                        envelope = json.loads(line)
                        event = envelope['event']
                        if event.get('type') == 'run.start':
                            backend, model = event.get('provider'), event.get('slug')
                        elif event.get('type') == 'step' and backend in ('gemini', 'mistral', 'openrouter') and model:
                            usage = event.get('usage')
                            if not isinstance(usage, dict):
                                continue
                            ts = datetime.fromisoformat(envelope['ts'].replace('Z', '+00:00'))
                            total = int(usage.get('input_tokens') or 0)
                            cached = int(usage.get('cached_input_tokens') or 0)
                            output = int(usage.get('output_tokens') or 0)
                            if min(total, cached, output) < 0 or cached > total:
                                continue
                            uid = 'native:' + hashlib.sha256(f'{path}|{index}'.encode()).hexdigest()
                            cursor = conn.execute(
                                'INSERT OR IGNORE INTO usage (uid, ts, day, backend, model, input_tokens, output_tokens, cache_read) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                (uid, ts.isoformat(), ts.astimezone().date().isoformat(), backend, model, total - cached, output, cached))
                            count += cursor.rowcount
                    except (ValueError, TypeError, KeyError, AttributeError):
                        continue
            conn.execute('INSERT OR REPLACE INTO ingest_state (path, mtime, size) VALUES (?, ?, ?)',
                         (path, stat.st_mtime, stat.st_size))
            conn.commit()
        except OSError:
            continue
    conn.close()
    return count

def main():
    parser = argparse.ArgumentParser(description='Ingest usage data into SQLite')
    parser.add_argument('--rebuild', action='store_true', help='Drop and rebuild DB')
    parser.add_argument('--db', help='Custom DB path')
    args = parser.parse_args()

    db_path = get_db_path(args.db)

    if args.rebuild:
        rebuild_db(db_path)
    else:
        init_db(db_path)

    # Ingest all sources
    count_claude = ingest_claude_transcripts(db_path)
    count_delegated = ingest_delegated_usage(db_path)
    count_new = count_claude + count_delegated + ingest_native_usage(db_path)

    # Count total rows and files
    conn = sqlite3.connect(db_path)
    total_rows = conn.execute('SELECT COUNT(*) FROM usage').fetchone()[0]
    total_files = conn.execute('SELECT COUNT(*) FROM ingest_state').fetchone()[0]
    conn.close()

    print(f"ingested {count_new} new rows, {total_files} files scanned, total rows {total_rows}")

if __name__ == '__main__':
    main()
