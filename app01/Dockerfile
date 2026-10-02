# 카카오 로그인 방명록 (app01 · EC2 + Docker + EFS)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 컨테이너 안의 데이터 경로. 호스트의 EFS 마운트 지점을 여기에 bind mount 한다.
RUN mkdir -p /data/uploads
ENV DATABASE_URL=sqlite:////data/guestbook.db \
    UPLOAD_DIR=/data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
