# 🏠 Dormitory Share & Care

ระบบเว็บแอปสำหรับหอพัก — **ยืม-คืนของส่วนกลาง, ฝากของ, ของหายได้คืน และแต้มความดี (Karma Points)** ออกแบบแบบ Mobile-First
ทุกฟีเจอร์ทำงานจริงกับฐานข้อมูล PostgreSQL ผ่าน REST API (FastAPI) — ไม่มี mock data แล้ว และรวม Frontend + Backend ไว้ใน repo เดียว

![status](https://img.shields.io/badge/core%20features-complete-brightgreen) ![progress](https://img.shields.io/badge/overall-%E2%89%8865%25-yellow)

---

## 📊 ความคืบหน้าของโปรเจกต์

**ฟีเจอร์หลักทั้งหมดทำงานจริงแล้ว** · ภาพรวมรวมงานเสริมใน Roadmap ≈ **65%** (10 จาก 16 งาน)

| ส่วน | สถานะ |
|---|---|
| UI ทุกหน้า (Mobile-First) | ✅ เสร็จ |
| สมัครสมาชิก / เข้าสู่ระบบ / ออกจากระบบ (JWT) | ✅ เสร็จ |
| ยืม-คืนของส่วนกลาง + ถ่ายรูปสภาพของตอนคืน | ✅ เสร็จ |
| ฝากของ (รหัส QR, ยืนยันรับของ, ยกเลิก) | ✅ เสร็จ |
| ของหายได้คืน (แจ้งเจอ / ตามหา / ขอรับของ + ผู้พบยืนยัน) | ✅ เสร็จ |
| แต้มความดี + อันดับประจำเดือน | ✅ เสร็จ |
| แจ้งเตือน (รวมเตือนใกล้ครบกำหนดคืน) + ประวัติกิจกรรม | ✅ เสร็จ |
| อัปโหลดรูปภาพจริง (ย่อขนาดอัตโนมัติ) | ✅ เสร็จ |
| ค้นหาของส่วนกลาง | ✅ เสร็จ |
| Docker Compose (db + pgAdmin + api) | ✅ เสร็จ |
| Dashboard นิติบุคคล (Admin role) | ❌ ยังไม่ทำ |
| Database migration ด้วย Alembic | ❌ ยังไม่ทำ |
| Real-time ด้วย WebSocket (ตอนนี้เช็กทุก 30 วินาที) | ❌ ยังไม่ทำ |
| แจ้งเตือนผ่าน LINE / Push Notification | ❌ ยังไม่ทำ |
| เก็บรูปบน Cloud Storage (ตอนนี้เก็บในฐานข้อมูล) | ❌ ยังไม่ทำ |
| Deploy ขึ้นเซิร์ฟเวอร์จริง | ❌ ยังไม่ทำ |

---

## ✨ ฟีเจอร์

- 🔐 **บัญชีผู้ใช้** — สมัครด้วยหมายเลขห้องพัก ตั้งชื่อที่แสดงได้ รีเฟรชหน้าแล้วยังล็อกอินค้างอยู่
- ☂️ **ยืม-คืนของส่วนกลาง** — ดูสถานะของแต่ละชิ้นจากฐานข้อมูลจริง (ว่าง / ถูกยืม / ซ่อม), ค้นหา + กรองหมวดหมู่, เลือกระยะเวลา (1 ชม. / 1 วัน / 3 วัน), ระบบกันยืมซ้อน, แจ้งคืนพร้อมรูปสภาพของและหมายเหตุ, ไฮไลต์รายการที่เลยกำหนด
- 📦 **ฝากของ** — ฝากของให้ห้องอื่นพร้อมรูปและรหัส QR, ผู้รับได้แจ้งเตือนทันที, กดยืนยันรับของได้ทั้งผู้รับและผู้ฝาก (กรณีผู้รับยังไม่มีบัญชี), ยกเลิกได้, แยกรายการ "ฝากถึงฉัน / ที่ฉันฝาก / ประวัติ"
- 🔍 **ของหายได้คืน** — แจ้งเจอของ / ประกาศตามหาของ พร้อมรูป, กด "นี่คือของฉัน" แล้วบอกลักษณะเฉพาะ → **ผู้ที่เก็บได้เป็นคนตรวจสอบและยืนยัน** (ระบบจบในตัวเอง ไม่ต้องรอเจ้าหน้าที่), ระบบจับคู่ชื่อของอัตโนมัติแล้วแจ้งเตือนคนที่ตามหาอยู่, ปิดประกาศให้อัตโนมัติเมื่อได้ของคืน
- 🪙 **แต้มความดี** — คำนวณจริงจากสมุดบัญชีแต้มในฐานข้อมูล + อันดับ "คนดีศรีหอพัก" ประจำเดือน
- 🔔 **แจ้งเตือน + ประวัติ** — แจ้งเตือนจริงเมื่อมีของฝาก/คำขอรับของ/ได้แต้ม/ใกล้ครบกำหนดคืน และบันทึกทุกกิจกรรมไว้ในหน้าโปรไฟล์

### กติกาแต้มความดี

| การกระทำ | แต้ม |
|---|---|
| คืนของส่วนกลางตรงเวลา (ยืมไว้อย่างน้อย 10 นาที กันการปั๊มแต้ม) | +10 |
| ของที่ฝากถูกส่งถึงมือผู้รับ (ผู้ฝากได้แต้ม) | +5 |
| เก็บของหายได้ และคืนถึงเจ้าของสำเร็จ | +20 |

## 🏗️ สถาปัตยกรรมระบบ (Architecture)

### Technology stack

![Technology stack diagram](tech-stack.png)

Frontend เป็น mobile-first SPA (HTML/CSS/JS ล้วน) คุยกับ FastAPI ผ่าน REST/JSON โดยใช้ JWT ยืนยันตัวตน แล้วเก็บข้อมูลใน PostgreSQL — ทั้งหมดรันผ่าน Docker Compose โดย backend แบ่งเป็นโมดูลตามฟีเจอร์ใน `routers/`

### แนวทางขยายระบบในอนาคต

![Microservices evolution diagram](microservices-evolution.png)

ตอนนี้ backend เป็น modular monolith (1 container แบ่งโมดูลผ่าน `routers/`) ถ้าในอนาคตต้องรองรับหลายหอพักหรือผู้ใช้จำนวนมาก สามารถแยกแต่ละโมดูลเป็น microservice พร้อม API Gateway และฐานข้อมูลแยกต่อ service ได้

### ฐานข้อมูล

| ตาราง | เก็บอะไร |
|---|---|
| `users` | บัญชีผู้ใช้ (username = หมายเลขห้อง) |
| `items` / `borrow_records` | ของส่วนกลาง และประวัติการยืม-คืน (รวมรูปตอนคืน) |
| `deposits` | รายการฝากของ + รหัสรับของ |
| `found_items` / `lost_reports` / `claims` | ของที่เก็บได้, ประกาศตามหา, คำขอรับของ |
| `point_transactions` | สมุดบัญชีแต้ม (แต้มรวม = ผลรวมของตารางนี้) |
| `notifications` / `activities` | แจ้งเตือน และประวัติกิจกรรม |

## 🔌 API Endpoints

ดูและทดลองเรียกได้ทุกตัวที่ **http://localhost:8000/docs** (Swagger UI)

| กลุ่ม | Endpoints |
|---|---|
| Auth | `POST /register` `POST /login` `POST /logout` `POST /change-password` |
| Users | `GET /me` `GET /users` `GET/PUT/DELETE /users/{id}` `GET /check-username/{name}` |
| Borrowing | `GET/POST /items` `POST /items/{id}/borrow` `GET /borrow/me` `POST /borrow/{id}/return` |
| Deposits | `GET /deposits/me` `POST /deposits` `POST /deposits/{id}/collect` `POST /deposits/{id}/cancel` |
| Lost & Found | `GET/POST /found` `POST /found/{id}/claims` `GET /claims/incoming` `POST /claims/{id}/approve` `POST /claims/{id}/reject` `GET/POST /lost` `POST /lost/{id}/resolve` |
| Points & Alerts | `GET /summary/me` `GET /points/me` `GET /leaderboard` `GET /notifications` `POST /notifications/read-all` `GET /activity/me` |

## 🛠️ Tech Stack

**Frontend** — Vanilla HTML / CSS / JavaScript ไฟล์เดียว (ไม่มี framework, ไม่ต้อง build) · ฟอนต์ Baloo 2 + Sarabun · QR Code ด้วย [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)

**Backend** — FastAPI · SQLAlchemy ORM · PostgreSQL 16 · JWT (python-jose) + bcrypt · Docker Compose

## 📁 โครงสร้างไฟล์

```
.
├── api/                          # Backend (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py               # entrypoint: รวม router, CORS, สร้างตาราง, ข้อมูลเริ่มต้น
│       ├── database.py
│       ├── models.py             # ตารางทั้งหมด
│       ├── schemas.py            # รูปแบบข้อมูลรับ-ส่ง (Pydantic)
│       ├── security.py           # JWT + hash รหัสผ่าน
│       ├── deps.py               # get_current_user
│       ├── services.py           # ให้แต้ม / แจ้งเตือน / บันทึกกิจกรรม (ใช้ร่วมกันทุกฟีเจอร์)
│       └── routers/
│           ├── auth.py
│           ├── users.py
│           ├── items.py          # ยืม-คืน
│           ├── deposits.py       # ฝากของ
│           ├── lostfound.py      # ของหายได้คืน + คำขอรับของ
│           └── community.py      # แต้ม, อันดับ, แจ้งเตือน, ประวัติ
├── .env.example
├── .gitignore
├── docker-compose.yml
├── dormitory-share-care.html     # Frontend ทั้งหมด
├── tech-stack.png
├── microservices-evolution.png
└── README.md
```

## 🚀 วิธีใช้งาน

### 1. Clone repo

```bash
git clone https://github.com/Kedzies/Dormitory-Share-Care.git
cd Dormitory-Share-Care
```

### 2. ตั้งค่าและรัน Backend

```bash
cp .env.example .env
```

เปิด `.env` แก้ `SECRET_KEY` เป็นค่าสุ่ม (รัน `openssl rand -hex 32` แล้วนำผลลัพธ์ไปใส่) จากนั้น:

```bash
docker compose up -d --build
```

- Swagger UI: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/health**
- pgAdmin: **http://localhost:5050** → login ตามค่าใน `.env` → Add Server → Host `db`, Port `5432`

ครั้งแรกที่รัน ระบบจะสร้างตารางและของส่วนกลางเริ่มต้น 6 ชิ้นให้อัตโนมัติ

### 3. เปิด Frontend

```bash
python3 -m http.server 5500
```

แล้วเข้า **http://localhost:5500/dormitory-share-care.html** (ต้องเปิดผ่าน server — ห้ามดับเบิลคลิกไฟล์ตรงๆ เพราะเบราว์เซอร์จะบล็อกการเชื่อมต่อ backend)

### 4. ลองใช้งานแบบ 2 ห้อง (แนะนำสำหรับเดโม)

ฟีเจอร์ฝากของและของหายเป็นการโต้ตอบระหว่าง 2 คน ให้เปิดเบราว์เซอร์ปกติ 1 หน้าต่าง + หน้าต่างไม่ระบุตัวตน (Incognito) อีก 1 หน้าต่าง แล้วสมัครคนละห้อง เช่น `B-304` กับ `B-201`

1. **B-304** ยืมร่ม → แจ้งคืนพร้อมถ่ายรูป
2. **B-304** ฝากกุญแจให้ `B-201` → **B-201** เห็นแจ้งเตือนและกด "ยืนยันว่ารับของแล้ว" → B-304 ได้ +5
3. **B-201** ประกาศตามหา "หูฟัง" → **B-304** แจ้งเจอ "หูฟังสีขาว" → B-201 ได้แจ้งเตือนว่าอาจเป็นของตัวเอง
4. **B-201** กด "นี่คือของฉัน" → **B-304** ตรวจรายละเอียดแล้วกดยืนยัน → B-304 ได้ +20 และขึ้นอันดับ
5. เปิด pgAdmin ดูข้อมูลในตารางเปลี่ยนตามการใช้งานจริง

### 5. ปิดระบบ

```bash
docker compose down       # หยุด container เก็บข้อมูลไว้
docker compose down -v    # หยุด + ล้างข้อมูลทั้งหมด
```

## ⚠️ ข้อจำกัดที่ทราบ

- รูปภาพเก็บในฐานข้อมูลแบบ base64 (ย่อเหลือด้านยาวสุด 900px ก่อนส่ง) — พอสำหรับต้นแบบ แต่ระบบจริงควรย้ายไป Cloud Storage
- การแจ้งเตือนอัปเดตทุก 30 วินาที ไม่ใช่ real-time
- token ที่ logout แล้วเก็บไว้ในหน่วยความจำ — รีสตาร์ต backend แล้ว token เก่าที่ยังไม่หมดอายุจะใช้ได้อีกครั้ง (ระบบจริงควรใช้ Redis)
- QR Code โหลดไลบรารีจาก CDN — ถ้าออฟไลน์จะแสดงเป็นรหัสตัวอักษรแทน

## 🗺️ Roadmap

- [x] สมัคร / เข้าสู่ระบบ / ออกจากระบบ กับ Backend จริง
- [x] ยืม-คืนของ กับ Backend จริง
- [x] ฝากของ กับ Backend จริง
- [x] ของหายได้คืน กับ Backend จริง
- [x] ระบบแต้มความดี + อันดับ
- [x] แจ้งเตือน + ประวัติกิจกรรม
- [x] อัปโหลดรูปภาพจริง
- [ ] Dashboard สำหรับนิติบุคคล (Admin)
- [ ] Alembic สำหรับ database migration
- [ ] Real-time ด้วย WebSocket
- [ ] แจ้งเตือนผ่าน LINE / Push Notification
- [ ] เก็บรูปบน Cloud Storage
- [ ] Deploy ขึ้นเซิร์ฟเวอร์จริง

## 📄 License

โปรเจกต์นี้จัดทำเพื่อการศึกษา สามารถนำไปต่อยอดพัฒนาได้ตามความเหมาะสม
67160348 บุณยนุช มโนมัยสกุล (AAI)
67160352 ปัณณกร พลเสน (AAI)
