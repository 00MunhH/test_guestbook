#!/usr/bin/env bash
set -e

# DB 스키마 마이그레이션 (PostgreSQL). 멀티 태스크 환경에서 동시에 실행돼도
# Alembic은 멱등하므로 안전하다.
echo "[entrypoint] running alembic upgrade head ..."
alembic upgrade head || echo "[entrypoint] alembic failed (continuing)"

echo "[entrypoint] starting uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
