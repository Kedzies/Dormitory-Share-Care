# 🔐 Project Group API

REST API สำหรับระบบ Project ของกลุ่ม พัฒนาด้วย **FastAPI + PostgreSQL** และจัดการ container ทั้งหมดด้วย **Docker & Docker Compose** ตามที่โจทย์กำหนด ครอบคลุมฟีเจอร์ **Authentication** และ **User Management** ที่ทำเสร็จสมบูรณ์แล้ว

## ✅ ฟีเจอร์ที่ทำเสร็จแล้ว

### 1. Authentication (ล็อกอิน/สมัคร)
| Method | Endpoint | คำอธิบาย |
|---|---|---|
| POST | `/register` | สมัครสมาชิก |
| POST | `/login` | เข้าสู่ระบบ (รับ JWT access token กลับ) |
| POST | `/logout` | ออกจากระบบ (revoke token ปัจจุบัน) |
| POST | `/change-password` | เปลี่ยนรหัสผ่าน (ต้องล็อกอินก่อน) |

### 2. User Management (จัดการข้อมูล)
| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/me` | ดึงข้อมูลตัวเอง |
| GET | `/users/{id}` | ดึงข้อมูล user ตาม id |
| GET | `/users?page=&page_size=` | ดึงข้อมูล user ทั้งหมด (pagination) |
| PUT | `/users/{id}` | แก้ไขข้อมูล user (แก้ได้เฉพาะบัญชีตัวเอง) |
| DELETE | `/users/{id}` | ลบ user (ลบได้เฉพาะบัญชีตัวเอง) |
| GET | `/check-username/{name}` | ตรวจสอบว่า username นี้ว่างไหม |

> 🔒 ทุก endpoint ในหมวด User Management (ยกเว้น `/check-username/{name}`) ต้องแนบ `Authorization: Bearer <token>` ที่ได้จาก `/login`
> 🛡️ `/users/{id}` (PUT/DELETE) จำกัดสิทธิ์ให้แก้ไข/ลบได้เฉพาะบัญชีของตัวเองเท่านั้น เพื่อป้องกันผู้ใช้คนอื่นมาแก้ไขข้อมูลกัน — ถ้าต้องการสิทธิ์ระดับแอดมินในอนาคต แนะนำเพิ่ม field `role`/`is_admin` ใน model แล้วเช็กสิทธิ์เพิ่ม

## 🛠️ Tech Stack

- **FastAPI** — เว็บเฟรมเวิร์กสำหรับสร้าง REST API
- **PostgreSQL 16** — ฐานข้อมูลหลัก
- **SQLAlchemy** — ORM เชื่อมต่อฐานข้อมูล
- **python-jose** — สร้าง/ตรวจสอบ JWT access token
- **passlib (bcrypt)** — เข้ารหัสรหัสผ่าน
- **pgAdmin 4** — เครื่องมือจัดการฐานข้อมูลผ่านหน้าเว็บ
- **Docker & Docker Compose** — จัดการ container ทั้งหมด (db, pgadmin, api)

## 📁 โครงสร้างโปรเจกต์

```
.
├── docker-compose.yml
├── .env.example
└── api/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py         # entrypoint, รวม router + CORS
        ├── database.py     # engine, session, get_db
        ├── models.py       # SQLAlchemy model: User
        ├── schemas.py      # Pydantic schemas (request/response)
        ├── security.py     # hash password, JWT, token blacklist
        ├── deps.py         # dependency: get_current_user
        └── routers/
            ├── auth.py     # /register /login /logout /change-password
            └── users.py    # /me /users /users/{id} /check-username/{name}
```

## 🚀 วิธีรันโปรเจกต์

### 1. เตรียมไฟล์ environment
```bash
cp .env.example .env
```
แก้ค่าต่างๆ ใน `.env` ตามต้องการ (โดยเฉพาะ `SECRET_KEY` ควรเปลี่ยนเป็นค่าสุ่ม เช่น `openssl rand -hex 32`)

### 2. สั่งรันทุก service ด้วย Docker Compose
```bash
docker compose up -d --build
```
คำสั่งนี้จะสร้าง 3 container พร้อมกัน:
- **db** — PostgreSQL ที่พอร์ต `5432`
- **pgadmin** — pgAdmin ที่พอร์ต `5050`
- **api** — FastAPI ที่พอร์ต `8000`

### 3. ตรวจสอบว่าทำงานสำเร็จ
```bash
docker compose ps
```
ทุก service ควรมีสถานะ running

### 4. เปิดใช้งาน API
- Swagger UI (ทดสอบ API ได้ทันที): **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**
- Health check: **http://localhost:8000/health**

### 5. เปิดใช้งาน pgAdmin
1. เข้า **http://localhost:5050** แล้วล็อกอินด้วยอีเมล/รหัสผ่านที่ตั้งไว้ใน `.env` (ค่าเริ่มต้น: `admin@example.com` / `admin123`)
2. เพิ่ม Server ใหม่ → แท็บ **Connection** กรอก:
   - Host: `db` (ชื่อ service ใน docker-compose ไม่ใช่ `localhost`)
   - Port: `5432`
   - Username / Password: ตามค่าใน `.env` (`POSTGRES_USER` / `POSTGRES_PASSWORD`)

### 6. ปิดการทำงาน
```bash
docker compose down          # หยุดและลบ container/network
docker compose down -v       # หยุดและลบ volume ฐานข้อมูลด้วย (ข้อมูลหายทั้งหมด)
```

## 🧪 ตัวอย่างการทดสอบผ่าน curl

```bash
# 1) สมัครสมาชิก
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"boonj","password":"secret123","email":"boonj@example.com"}'

# 2) เข้าสู่ระบบ (รูปแบบ form-urlencoded ตามมาตรฐาน OAuth2)
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=boonj&password=secret123"
# ตอบกลับ: {"access_token": "...", "token_type": "bearer"}

# 3) ดึงข้อมูลตัวเอง (แนบ token ที่ได้จากขั้นตอนที่ 2)
curl http://localhost:8000/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 4) ตรวจสอบ username ว่าง
curl http://localhost:8000/check-username/boonj
```

## 📌 หมายเหตุด้านความปลอดภัย/ข้อจำกัด (สำหรับพัฒนาต่อ)

- `/logout` ใช้วิธี revoke token เก็บใน memory ของ container — ใช้ได้ดีสำหรับ 1 instance/โปรเจกต์เรียน แต่ถ้า deploy จริงแบบหลาย instance ควรย้ายไปเก็บใน Redis แทน
- ตอนนี้สร้างตารางฐานข้อมูลอัตโนมัติด้วย `Base.metadata.create_all()` ตอน service เริ่มทำงาน เหมาะกับ dev/demo — ถ้าจะทำ production จริงแนะนำใช้ **Alembic** สำหรับจัดการ migration แทน
- ยังไม่มีระบบ role/admin แยกสิทธิ์ ตอนนี้ทุก user แก้ไข/ลบได้เฉพาะบัญชีตัวเอง

## 📋 งานส่วนถัดไป (ยังไม่ได้ทำในรอบนี้)

รายการนี้อยู่ในสเปกของกลุ่มแต่ยังไม่ได้ทำในรอบนี้ (ยังไม่ได้ติ๊ก `[x]`) รอโจทย์/รายละเอียดเพิ่มเติมในรอบถัดไป — ถ้าพร้อมให้ทำต่อแจ้งได้เลย

- [ ] ระบบอื่นๆ ที่กลุ่มจะกำหนดเพิ่มเติมนอกเหนือจาก Authentication และ User Management

---

## ⚠️ หมายเหตุเกี่ยวกับไฟล์ที่แนบมา

ไฟล์ `files_example.rar` ที่แนบมาด้วยไม่สามารถเปิด/แตกไฟล์ได้ในสภาพแวดล้อมนี้ (ไม่มีเครื่องมือแตกไฟล์ .rar และไม่มีการเชื่อมต่ออินเทอร์เน็ตให้ติดตั้งเพิ่ม) โปรเจกต์นี้จึงสร้างขึ้นจากคำอธิบายในข้อความ (Postgres + pgAdmin + FastAPI ผ่าน Docker Compose) และเนื้อหาในเอกสารประกอบการสอน Docker & FastAPI ที่แนบมาแทน ถ้าในไฟล์ rar มีโค้ดตัวอย่างที่ต้องการให้อ้างอิงเพิ่มเติม รบกวนแตกไฟล์แล้วอัปโหลดใหม่เป็น `.zip` หรือคัดลอกโค้ดมาวางในแชทได้เลยค่ะ
