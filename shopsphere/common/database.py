"""
ShopSphere Database Client (PostgreSQL with SQLite local fallback)
Manages database connection with query tracing, latency measurement,
and controlled failure injection (latency injection and connection exhaustion) for Phase 11.
"""

import os
import time
import asyncio
import sqlite3
from typing import Optional, List, Dict, Any
from decimal import Decimal

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "shopsphere")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "shopsphere_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "shopsphere_db")

# Global pool / connection
_pool = None
_sqlite_conn: Optional[sqlite3.Connection] = None
_is_sqlite: bool = False

# Chaos / Failure injection state for Phase 11 testing
_injected_latency_ms: float = 0.0
_exhaust_connections: bool = False
_exhaustion_lock = asyncio.Lock()
_exhausted_holders: List[Any] = []


class SqliteRecord(dict):
    """Dictionary subclass providing asyncpg.Record compatibility."""
    def __getitem__(self, item):
        return super().__getitem__(item)


def _init_sqlite_db():
    global _sqlite_conn, _is_sqlite
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db"))
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "shopsphere_local.db")
    
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 100,
        reserved INTEGER NOT NULL DEFAULT 0,
        price REAL NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        transaction_ref TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        recipient TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed catalog if empty
    cursor.execute("SELECT count(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        seed_items = [
            ('SKU-LAPTOP-01', 'ProBook 16-inch M3', 500, 0, 1299.99),
            ('SKU-PHONE-02', 'AegisPhone Ultra 5G', 800, 0, 899.99),
            ('SKU-HEADSET-03', 'Studio Noise Cancelling Headphones', 1200, 0, 199.50),
            ('SKU-KEYBOARD-04', 'Mechanical Wireless Keyboard', 650, 0, 129.00),
            ('SKU-MONITOR-05', 'UltraWide 34-inch 144Hz Monitor', 300, 0, 499.00),
            ('SKU-MOUSE-06', 'Ergonomic Precision Mouse', 1500, 0, 69.99),
            ('SKU-SMARTWATCH-07', 'Fitness Smartwatch Pro', 750, 0, 249.99),
            ('SKU-CHARGER-08', '100W GaN Fast Charger', 2000, 0, 45.00),
            ('SKU-STAND-09', 'Aluminum Laptop Stand', 900, 0, 39.99),
            ('SKU-CABLE-10', 'Thunderbolt 4 Cable 2m', 2500, 0, 29.99)
        ]
        cursor.executemany("INSERT OR IGNORE INTO inventory (sku, name, quantity, reserved, price) VALUES (?, ?, ?, ?, ?)", seed_items)
        conn.commit()

    _sqlite_conn = conn
    _is_sqlite = True
    return conn


async def init_db_pool(min_size: int = 5, max_size: int = 20):
    """Initializes asyncpg connection pool or falls back to SQLite."""
    global _pool, _is_sqlite
    if _pool is not None or _sqlite_conn is not None:
        return _pool or _sqlite_conn

    try:
        import asyncpg
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                database=POSTGRES_DB,
                min_size=min_size,
                max_size=max_size,
                command_timeout=15.0
            ),
            timeout=2.0
        )
        _is_sqlite = False
        return _pool
    except Exception:
        # Fall back to SQLite
        return _init_sqlite_db()


async def close_db_pool():
    global _pool, _sqlite_conn
    if _pool:
        await _pool.close()
        _pool = None
    if _sqlite_conn:
        _sqlite_conn.close()
        _sqlite_conn = None


_target_service: Optional[str] = None


def set_failure_simulation(latency_ms: float = 0.0, exhaust_connections: bool = False, target_service: Optional[str] = None):
    """Configures simulated database failure for Phase 11."""
    global _injected_latency_ms, _exhaust_connections, _target_service
    _injected_latency_ms = latency_ms
    _exhaust_connections = exhaust_connections
    _target_service = target_service


def get_failure_status() -> Dict[str, Any]:
    return {
        "injected_latency_ms": _injected_latency_ms,
        "exhaust_connections": _exhaust_connections,
        "target_service": _target_service,
        "active_exhausted_conns": len(_exhausted_holders)
    }


def _convert_sql(query: str, args: tuple):
    """Converts PostgreSQL $1, $2 placeholders to SQLite ? placeholders and formats params."""
    import re
    cleaned = re.sub(r'\$\d+', '?', query)
    cleaned = cleaned.replace("FOR UPDATE", "")
    conv_args = []
    for a in args:
        if isinstance(a, Decimal):
            conv_args.append(float(a))
        else:
            conv_args.append(a)
    return cleaned, tuple(conv_args)


async def execute_query(query: str, *args, timeout: float = 5.0, service: Optional[str] = None) -> str:
    """Executes non-returning SQL query with latency injection if active."""
    global _injected_latency_ms, _pool, _is_sqlite, _sqlite_conn, _target_service
    if _injected_latency_ms > 0:
        if _target_service is None or service is None or _target_service == service:
            await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _pool and not _is_sqlite:
        async with _pool.acquire(timeout=timeout) as conn:
            return await conn.execute(query, *args)

    if _sqlite_conn is None:
        _init_sqlite_db()

    q, a = _convert_sql(query, args)
    cursor = _sqlite_conn.cursor()
    cursor.execute(q, a)
    _sqlite_conn.commit()
    return f"OK {cursor.rowcount}"


async def fetch_row(query: str, *args, timeout: float = 5.0, service: Optional[str] = None) -> Optional[Any]:
    """Fetches single row with latency injection if active."""
    global _injected_latency_ms, _pool, _is_sqlite, _sqlite_conn, _target_service
    if _injected_latency_ms > 0:
        if _target_service is None or service is None or _target_service == service:
            await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _pool and not _is_sqlite:
        async with _pool.acquire(timeout=timeout) as conn:
            return await conn.fetchrow(query, *args)

    if _sqlite_conn is None:
        _init_sqlite_db()

    q, a = _convert_sql(query, args)
    cursor = _sqlite_conn.cursor()
    cursor.execute(q, a)
    row = cursor.fetchone()
    if row:
        return SqliteRecord(dict(row))
    return None


async def fetch_rows(query: str, *args, timeout: float = 5.0) -> List[Any]:
    """Fetches multiple rows with latency injection if active."""
    global _injected_latency_ms, _pool, _is_sqlite, _sqlite_conn
    if _injected_latency_ms > 0:
        await asyncio.sleep(_injected_latency_ms / 1000.0)

    if _pool and not _is_sqlite:
        async with _pool.acquire(timeout=timeout) as conn:
            return await conn.fetch(query, *args)

    if _sqlite_conn is None:
        _init_sqlite_db()

    q, a = _convert_sql(query, args)
    cursor = _sqlite_conn.cursor()
    cursor.execute(q, a)
    rows = cursor.fetchall()
    return [SqliteRecord(dict(r)) for r in rows]


async def check_db_health() -> Dict[str, Any]:
    start = time.time()
    try:
        row = await fetch_row("SELECT 1 AS alive", timeout=2.0)
        latency = round((time.time() - start) * 1000, 2)
        engine = "sqlite" if _is_sqlite else "postgresql"
        return {"status": "HEALTHY", "engine": engine, "latency_ms": latency}
    except Exception as e:
        latency = round((time.time() - start) * 1000, 2)
        return {"status": "UNHEALTHY", "error": str(e), "latency_ms": latency}
