"""
CloudDesk Database Client (PostgreSQL with SQLite local fallback)
Manages cloud database connections with query tracing, latency measurement,
and controlled failure injection for testing.
"""

import os
import time
import asyncio
import sqlite3
from typing import Optional, List, Dict, Any

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "clouddesk")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "clouddesk_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "clouddesk_db")

_pool = None
_sqlite_conn: Optional[sqlite3.Connection] = None
_is_sqlite: bool = False

_injected_latency_ms: float = 0.0
_exhaust_connections: bool = False


class SqliteRecord(dict):
    def __getitem__(self, item):
        return super().__getitem__(item)


def _init_sqlite_db():
    global _sqlite_conn, _is_sqlite
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "clouddesk_local.db")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'DEVELOPER',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'TEAM_PRO',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS compute_instances (
        instance_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        instance_type TEXT NOT NULL DEFAULT 'c5.large',
        cpu_cores INTEGER NOT NULL DEFAULT 4,
        memory_gb INTEGER NOT NULL DEFAULT 16,
        status TEXT NOT NULL DEFAULT 'RUNNING',
        ip_address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS billing_records (
        record_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        units_consumed REAL NOT NULL,
        cost REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed baseline users & projects
    cursor.execute("SELECT count(*) FROM users")
    if cursor.fetchone()[0] == 0:
        seed_users = [
            (f"usr-{100 + i}", f"developer_{i}@cloudtech.io", f"Cloud Engineer {i}", f"org-{10 + (i % 3)}", "DEVOPS", "ACTIVE")
            for i in range(15)
        ]
        cursor.executemany(
            "INSERT INTO users (user_id, email, name, organization_id, role, status) VALUES (?, ?, ?, ?, ?, ?)",
            seed_users
        )
        seed_projects = [
            (f"prj-{500 + i}", f"Alpha-Cluster-{i}", f"usr-{100 + (i % 15)}", "ENTERPRISE", "ACTIVE")
            for i in range(10)
        ]
        cursor.executemany(
            "INSERT INTO projects (project_id, name, owner_id, plan, status) VALUES (?, ?, ?, ?, ?)",
            seed_projects
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


def _translate_sql(query: str) -> str:
    import re
    return re.sub(r'\$\d+', '?', query)


async def execute_query(query: str, *args) -> str:
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - connection pool exhausted")
    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _exec():
            cur = _sqlite_conn.cursor()
            cur.execute(_translate_sql(query), args)
            _sqlite_conn.commit()
            return f"EXEC {cur.rowcount}"
        return await asyncio.to_thread(_exec)

    async with _pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_row(query: str, *args) -> Optional[Dict[str, Any]]:
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - connection pool exhausted")
    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _fetch():
            cur = _sqlite_conn.cursor()
            cur.execute(_translate_sql(query), args)
            row = cur.fetchone()
            return SqliteRecord(dict(row)) if row else None
        return await asyncio.to_thread(_fetch)

    async with _pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_rows(query: str, *args) -> List[Dict[str, Any]]:
    if _exhaust_connections:
        raise Exception("OperationalError: FATAL - connection pool exhausted")
    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _is_sqlite:
        def _fetch_all():
            cur = _sqlite_conn.cursor()
            cur.execute(_translate_sql(query), args)
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
