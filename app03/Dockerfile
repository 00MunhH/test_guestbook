# 카카오 로그인 방명록 (app03 · ECS + RDS/S3/Redis 확장형)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

# 컨테이너 시작 시 Alembic 마이그레이션 후 서버 기동
CMD ["./entrypoint.sh"]
