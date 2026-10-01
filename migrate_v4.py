"""v4.0 마이그레이션: 기존 guestbook.db의 users 테이블에 신규 컬럼 추가.

기존에 운영 중이던 DB(= v3.0 이하)에는 display_name, bio, is_admin 컬럼이
없으므로, 이 스크립트로 안전하게 추가한다. 신규 DB에는 실행할 필요가 없다.

사용법:
    python migrate_v4.py            # 기본 guestbook.db
    DATABASE_URL=... python migrate_v4.py   # URL 지정 시 해당 sqlite 파일
"""
import os
import re
import sqlite3
import sys


def resolve_sqlite_path() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./guestbook.db")
    m = re.match(r"sqlite:/{2,}(.*)", url)
    if not m:
        print(f"SQLite URL이 아닙니다: {url}")
        sys.exit(1)
    path = m.group(1)
    # sqlite:////data/x.db -> /data/x.db, sqlite:///./x.db -> ./x.db
    return path


# 추가할 컬럼: (이름, SQL 타입, 기본값)
NEW_COLUMNS = [
    ("display_name", "VARCHAR(128)", "''"),
    ("bio", "TEXT", "''"),
    ("is_admin", "BOOLEAN", "0"),
]


def main() -> None:
    db_path = resolve_sqlite_path()
    if not os.path.exists(db_path):
        print(f"DB 파일이 없습니다. 새로 실행하면 자동 생성됩니다: {db_path}")
        return

    con = sqlite3.connect(db_path)
    try:
        existing = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}
        if not existing:
            print("users 테이블이 없습니다. 앱을 먼저 실행하세요.")
            return

        added = []
        for name, sqltype, default in NEW_COLUMNS:
            if name not in existing:
                con.execute(
                    f"ALTER TABLE users ADD COLUMN {name} {sqltype} NOT NULL DEFAULT {default}"
                )
                added.append(name)
        con.commit()

        if added:
            print(f"추가된 컬럼: {', '.join(added)}")
        else:
            print("이미 최신 스키마입니다. 변경 없음.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
