"""Clear all optimization records from the database."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "data/promptforge.db"
conn = sqlite3.connect(db_path)
conn.execute("DELETE FROM optimizations")
conn.commit()
count = conn.execute("SELECT COUNT(*) FROM optimizations").fetchone()[0]
print(f"Cleared database. Remaining records: {count}")
conn.close()
