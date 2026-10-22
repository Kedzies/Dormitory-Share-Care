# สำหรับ deploy (Render ฯลฯ): รวม backend + หน้าเว็บไว้ใน container เดียว → ลิงก์เดียวใช้ได้ทั้งระบบ
# (ตอนพัฒนาในเครื่องใช้ docker-compose.yml ซึ่ง build จาก api/Dockerfile ตามเดิม)
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ .
COPY dormitory-share-care.html static/index.html

# Render กำหนดพอร์ตผ่านตัวแปร PORT — ในเครื่องใช้ 8000
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
