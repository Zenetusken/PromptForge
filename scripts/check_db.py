"""Quick script to check SQLite database schema."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "data/promptforge.db"
conn = sqlite3.connect(db_path)
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor]
print("Tables:", tables)

for table in tables:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor]
    print(f"  {table} columns: {cols}")

conn.close()
