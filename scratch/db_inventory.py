import sqlite3

conn = sqlite3.connect('aegisops.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]

print(f"Total tables in aegisops.db: {len(tables)}")
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}";')
    cnt = cur.fetchone()[0]
    cur.execute(f'PRAGMA table_info("{t}");')
    cols = [col[1] for col in cur.fetchall()]
    print(f"  {t:32} | Rows: {cnt:6} | Cols ({len(cols)}): {', '.join(cols[:6])}")

