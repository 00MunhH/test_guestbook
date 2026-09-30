"""SQLite 방명록 DB 내용 조회 스크립트."""
import sqlite3

con = sqlite3.connect("guestbook.db")
cur = con.cursor()

tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()]
print("TABLES:", tables)

print("\n== USERS ==")
for row in cur.execute("SELECT id, kakao_id, nickname, created_at FROM users").fetchall():
    print(row)

print("\n== GUESTBOOK ENTRIES ==")
for row in cur.execute(
    "SELECT id, author_id, message, created_at FROM guestbook_entries ORDER BY id"
).fetchall():
    print(row)

con.close()
