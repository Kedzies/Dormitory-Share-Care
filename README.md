# Dormitory Share & Care

ระบบเว็บสำหรับนักศึกษาหอพัก เพื่อช่วยแบ่งปันสิ่งของ ฝากของ และติดตามของหายภายในหอพัก

โปรเจกต์นี้ประกอบด้วย frontend แบบ HTML/CSS/JavaScript และ REST API ที่พัฒนาด้วย FastAPI, PostgreSQL และ Docker Compose

## Features

### Frontend

- หน้าเข้าสู่ระบบและสมัครสมาชิก
- เก็บ JWT access token สำหรับ session ของผู้ใช้
- แสดงข้อมูลผู้ใช้จาก API หลัง login
- หน้าหลักสำหรับแต้มความดีและกิจกรรมล่าสุด
- หน้ายืม-คืนของส่วนกลาง
- หน้าฝากของ
- หน้าของหายและของที่พบ
- หน้าโปรไฟล์และการแจ้งเตือน

### Backend API

- สมัครสมาชิกและเข้าสู่ระบบด้วย JWT
- ออกจากระบบและ revoke token
- เปลี่ยนรหัสผ่าน
- ดึงข้อมูลผู้ใช้ปัจจุบัน
- แสดงรายการผู้ใช้แบบ pagination
- แก้ไขหรือลบบัญชีของตัวเอง
- ตรวจสอบ username ว่าว่างหรือไม่
- Swagger UI สำหรับทดสอบ API

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** FastAPI, Python 3.12
- **Database:** PostgreSQL 16
- **ORM:** SQLAlchemy
- **Authentication:** JWT, python-jose, bcrypt
- **Database Admin:** pgAdmin 4
- **Container:** Docker, Docker Compose

## Project Structure

```text
.
├── .env.example
├── docker-compose.yml
├── README.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py        # FastAPI entrypoint และ CORS
│       ├── database.py    # การเชื่อมต่อฐานข้อมูล
│       ├── models.py      # SQLAlchemy models
│       ├── schemas.py     # Pydantic schemas
│       ├── security.py    # Password hashing และ JWT
│       ├── deps.py        # Authentication dependencies
│       └── routers/
│           ├── auth.py    # Authentication endpoints
│           └── users.py   # User management endpoints
└── ../index.html          # Frontend หลักของระบบ
```

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git
- Web browser
- VS Code และ extension **Five Server** หรือ **Live Server** สำหรับเปิด frontend

## Installation

Clone repository:

```bash
git clone https://github.com/Kedzies/Dormitory-Share-Care.git
cd Dormitory-Share-Care
```

สร้างไฟล์ environment จากตัวอย่าง:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS / Linux / Git Bash

```bash
cp .env.example .env
```

ก่อนใช้งานจริง ควรแก้ค่า `SECRET_KEY` ในไฟล์ `.env` ให้เป็นค่าสุ่มที่คาดเดาได้ยาก

## Run Backend

เปิด Docker Desktop ก่อน จากนั้นรันคำสั่งจากโฟลเดอร์ repository:

```bash
docker compose up -d --build
```

ตรวจสอบสถานะ services:

```bash
docker compose ps
```

ถ้าทำงานปกติจะมี services ต่อไปนี้:

| Service | URL / Port | รายละเอียด |
|---|---|---|
| API | http://localhost:8000 | FastAPI backend |
| Swagger UI | http://localhost:8000/docs | เอกสารและหน้าทดสอบ API |
| ReDoc | http://localhost:8000/redoc | เอกสาร API แบบ ReDoc |
| Health check | http://localhost:8000/health | ตรวจสอบสถานะ API |
| PostgreSQL | localhost:5432 | ฐานข้อมูล |
| pgAdmin | http://localhost:5050 | จัดการฐานข้อมูลผ่านเว็บ |

ทดสอบ health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

ผลลัพธ์ที่คาดหวัง:

```text
status
------
ok
```

## Run Frontend

ไฟล์ frontend อยู่ที่ `../index.html` เมื่อมองจากโฟลเดอร์ `project` หรืออยู่ที่ root ของ repository ที่ clone มาด้วยโครงสร้างปัจจุบัน

เปิดโฟลเดอร์ repository หลักใน VS Code แล้วใช้ Five Server หรือ Live Server เปิด `index.html` จากนั้นเปิด URL ที่ extension แสดงให้ เช่น:

```text
http://127.0.0.1:5500/index.html
```

Frontend จะเชื่อมต่อ API ที่:

```text
http://localhost:8000
```

## Test Authentication

### ผ่านหน้าเว็บ

1. เปิด frontend
2. เลือก **สมัครสมาชิก**
3. กรอก username อย่างน้อย 3 ตัวอักษร
4. กรอกรหัสผ่านอย่างน้อย 6 ตัวอักษร
5. กดสมัครสมาชิก
6. ระบบจะ login และโหลดข้อมูลผู้ใช้จาก `/me` อัตโนมัติ
7. กดออกจากระบบ แล้วทดสอบ login ใหม่

### ผ่าน PowerShell

สมัครสมาชิก:

```powershell
$body = @{
  username = "demo_user"
  password = "secret123"
  full_name = "Demo User"
  email = "demo@example.com"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://localhost:8000/register `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

เข้าสู่ระบบเพื่อรับ token:

```powershell
$login = Invoke-RestMethod `
  -Uri http://localhost:8000/login `
  -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{ username = "demo_user"; password = "secret123" }

$token = $login.access_token
```

เรียกข้อมูลผู้ใช้ปัจจุบัน:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8000/me `
  -Headers @{ Authorization = "Bearer $token" }
```

## API Endpoints

### Authentication

| Method | Endpoint | Auth | รายละเอียด |
|---|---|---:|---|
| POST | `/register` | No | สมัครสมาชิก |
| POST | `/login` | No | เข้าสู่ระบบและรับ JWT |
| POST | `/logout` | Yes | ออกจากระบบ |
| POST | `/change-password` | Yes | เปลี่ยนรหัสผ่าน |

### User Management

| Method | Endpoint | Auth | รายละเอียด |
|---|---|---:|---|
| GET | `/me` | Yes | ดึงข้อมูลผู้ใช้ปัจจุบัน |
| GET | `/users` | Yes | แสดงผู้ใช้แบบ pagination |
| GET | `/users/{id}` | Yes | ดึงข้อมูลผู้ใช้ตาม ID |
| PUT | `/users/{id}` | Yes | แก้ไขข้อมูลบัญชีตัวเอง |
| DELETE | `/users/{id}` | Yes | ลบบัญชีตัวเอง |
| GET | `/check-username/{name}` | No | ตรวจสอบ username |

## Stop Services

หยุด services แต่เก็บข้อมูล PostgreSQL ไว้:

```bash
docker compose down
```

หยุด services และลบข้อมูลฐานข้อมูลทั้งหมด:

```bash
docker compose down -v
```

## Troubleshooting

### Docker Engine ไม่ทำงาน

ถ้าเห็นข้อความ `dockerDesktopLinuxEngine` หรือ `The system cannot find the file specified` ให้เปิด Docker Desktop และรอจนสถานะเป็น **Running** จากนั้นลองใหม่:

```powershell
docker info
docker compose up -d --build
```

### ดู log ของ API

```bash
docker compose logs -f api
```

### Port ถูกใช้งานอยู่

ตรวจสอบว่าพอร์ต `8000`, `5432` หรือ `5050` ถูกใช้งานโดยโปรแกรมอื่นหรือไม่ แล้วหยุดโปรแกรมนั้นก่อนเริ่ม services

## Current Limitations

- ฟีเจอร์ Authentication และ User Management เชื่อมต่อฐานข้อมูลจริงแล้ว
- ข้อมูลยืม-คืน, ฝากของ, ของหาย และการแจ้งเตือนใน frontend ยังเป็น mock data
- การเข้าสู่ระบบด้วย LINE ยังไม่เชื่อมต่อ OAuth จริง
- token revoke ถูกเก็บไว้ใน memory เหมาะสำหรับการเรียนหรือ demo; production ควรใช้ Redis
- การสร้างตารางใช้ `Base.metadata.create_all()`; production ควรใช้ Alembic migrations
- ยังไม่มีระบบ role หรือ admin

## License

โปรเจกต์นี้จัดทำเพื่อการศึกษาและพัฒนาระบบต้นแบบ
