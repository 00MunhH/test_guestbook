# 카카오 로그인 방명록 - FastAPI 애플리케이션 이미지
FROM python:3.11-slim

# 파이썬 로그 즉시 출력 및 .pyc 미생성
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY app ./app

# 마이그레이션 스크립트 복사 (기존 DB 업그레이드용)
COPY migrate_v4.py .

# SQLite DB + 업로드 파일이 저장될 디렉터리 (볼륨 마운트 지점)
RUN mkdir -p /data /data/uploads
ENV DATABASE_URL=sqlite:////data/guestbook.db \
    UPLOAD_DIR=/data/uploads

# 컨테이너가 노출하는 포트
EXPOSE 8000

# 0.0.0.0 바인딩으로 컨테이너 외부에서 접속 가능
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
