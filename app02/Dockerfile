# 카카오 로그인 방명록 (app02 · ECS + EFS 최소 구성)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# EFS가 마운트될 지점. DB/업로드는 이 경로(= EFS)에 저장한다.
# 로컬 컨테이너 단독 실행 시에도 깨지지 않도록 디렉터리를 미리 만든다.
RUN mkdir -p /mnt/data/uploads
ENV DATABASE_URL=sqlite:////mnt/data/guestbook.db \
    UPLOAD_DIR=/mnt/data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
