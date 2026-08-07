FROM python:3.12-slim

WORKDIR /app

# ติดตั้ง dependency ก่อน เพื่อให้ Docker cache layer นี้ไว้ (build รอบถัดไปเร็วขึ้น)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
