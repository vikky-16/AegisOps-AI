"""
FinCore Database Client (PostgreSQL with SQLite local fallback)
Manages financial database connections with query tracing, latency measurement,
and controlled failure injection for testing.
"""

import os
import time
import asyncio
import sqlite3
from typing import Optional, List, Dict, Any, Tuple

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "fincore")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "fincore_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "fincore_db")

_pool = None
_sqlite_conn: Optional[sqlite3.Connection] = None
_is_sqlite: bool = False

_injected_latency_ms: float = 0.0
_exhaust_connections: bool = False


class SqliteRecord(dict):
    """Dictionary subclass providing asyncpg.Record compatibility."""
    def __getitem__(self, item):
        return super().__getitem__(item)


def _init_sqlite_db():
    global _sqlite_conn, _is_sqlite
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "fincore_local.db")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
        account_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        account_type TEXT NOT NULL DEFAULT 'CHECKING',
        balance REAL NOT NULL DEFAULT 5000.0,
        currency TEXT NOT NULL DEFAULT 'USD',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        from_account TEXT NOT NULL,
        to_account TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        type TEXT NOT NULL DEFAULT 'TRANSFER',
        status TEXT NOT NULL DEFAULT 'COMPLETED',
        fraud_score REAL NOT NULL DEFAULT 0.05,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        gateway_ref TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        status TEXT NOT NULL DEFAULT 'SETTLED',
        payment_method TEXT NOT NULL DEFAULT 'ACH',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fraud_checks (
        check_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        risk_score REAL NOT NULL,
        action TEXT NOT NULL,
        rules_triggered TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        recipient TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed baseline accounts if table empty
    cursor.execute("SELECT count(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        seed_accounts = [
            (f"acc-{1000 + i}", f"cust-{2000 + i}", "CHECKING" if i % 2 == 0 else "SAVINGS", 10000.0 + (i * 2500.0), "USD", "ACTIVE")
            for i in range(25)
        ]
        cursor.executemany(
            "INSERT INTO accounts (account_id, customer_id, account_type, balance, currency, status) VALUES (?, ?, ?, ?, ?, ?)",
            seed_accounts
        )
        conn.commit()

    _sqlite_conn = conn
    _is_sqlite = True


async def init_db_pool():
    global _pool, _is_sqlite
    try:
        import asyncpg
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                database=POSTGRES_DB,
                min_size=2,
                max_size=15,
                command_timeout=10.0
            ),
            timeout=2.0
        )
        _is_sqlite = False
    except Exception:
        _init_sqlite_db()


async def close_db_pool():
    global _pool, _sqlite_conn
    if _pool:
        await _pool.close()
        _pool = None
    if _sqlite_conn:
        _sqlite_conn.close()
        _sqlite_conn = None


def set_failure_simulation(latency_ms: float = 0.0, exhaust_connections: bool = False):
    global _injected_latency_ms, _exhaust_connections
    _injected_latency_ms = latency_ms
    _exhaust_connections = exhaust_connections


def get_failure_status() -> Dict[str, Any]:
    return {
        "injected_latency_ms": _injected_latency_ms,
        "exhaust_connections": _exhaust_connections
    }


def _translate_sql(query: str, args: tuple = ()) -> Tuple[str, tuple]:
    """Translates Postgres $1, $2 placeholders to SQLite ? and correctly aligns argument order."""
    import re
    matches = list(re.finditer(r'\$(\d+)', query))
    if not matches:
        return query, args
    new_args = []
    for m in matches:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(args):
            new_args.append(args[idx])
        else:
            new_args.append(None)
    new_query = re.sub(r'\$\d+', '?', query)
    return new_query, tuple(new_args)


async def execute_query(query: str, *args) -> str:
    start = time.time()
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - remaining connection slots are reserved for non-replication superuser connections")

    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _exec():
            q, a = _translate_sql(query, args)
            cur = _sqlite_conn.cursor()
            cur.execute(q, a)
            _sqlite_conn.commit()
            return f"EXEC {cur.rowcount}"
        return await asyncio.to_thread(_exec)

    async with _pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_row(query: str, *args) -> Optional[Dict[str, Any]]:
    start = time.time()
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - remaining connection slots are reserved")

    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _fetch():
            q, a = _translate_sql(query, args)
            cur = _sqlite_conn.cursor()
            cur.execute(q, a)
            row = cur.fetchone()
            return SqliteRecord(dict(row)) if row else None
        return await asyncio.to_thread(_fetch)

    async with _pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_rows(query: str, *args) -> List[Dict[str, Any]]:
    start = time.time()
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - remaining connection slots are reserved")

    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _fetch_all():
            q, a = _translate_sql(query, args)
            cur = _sqlite_conn.cursor()
            cur.execute(q, a)
            return [SqliteRecord(dict(r)) for r in cur.fetchall()]
        return await asyncio.to_thread(_fetch_all)

    async with _pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def check_db_health() -> Dict[str, Any]:
    start = time.time()
    try:
        if _is_sqlite:
            res = await fetch_row("SELECT 1 AS alive")
            lat = round((time.time() - start) * 1000, 2)
            return {"status": "HEALTHY", "latency_ms": lat, "engine": "sqlite_local"}
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            lat = round((time.time() - start) * 1000, 2)
            return {"status": "HEALTHY", "latency_ms": lat, "engine": "postgresql"}
    except Exception as e:
        lat = round((time.time() - start) * 1000, 2)
        return {"status": "UNHEALTHY", "latency_ms": lat, "error": str(e)}
