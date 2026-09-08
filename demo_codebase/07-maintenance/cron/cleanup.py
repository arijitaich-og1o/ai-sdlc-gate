"""Nightly cleanup: remove inactive accounts and their data (demo, intentionally defective)."""
import sqlite3
from datetime import datetime, timedelta


def run():
    conn = sqlite3.connect("accounts.db")
    cur = conn.cursor()
    cutoff = datetime.now() - timedelta(days=365)
    ids = [r[0] for r in cur.execute("SELECT id FROM users WHERE last_login < ?", (cutoff,))]
    for user_id in ids:
        cur.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    cur.execute("INSERT INTO audit (message) VALUES (?)", (f"deleted {len(ids)} users",))
    conn.commit()


if __name__ == "__main__":
    run()
