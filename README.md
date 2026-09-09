# 📱 Kizuno-AI — Evidence-Based Citizen Grievance Tracking Engine

> **"Submit your complaint and follow its entire journey until resolution."**  
> An ultra-premium, dark cyber-aesthetic civic grievance platform connecting citizens with municipal departments through day-wise audit journals, bi-directional officer workflows, automated delay detection, a **Skiper68 interactive authentication enclave**, a **Python FastAPI backend**, and a **real SQL database (SQLite)**.

---

## 🏗️ Technology & Design Stack

- **Design Aesthetic**: Cyber Dark Enclave (`#08080a`), floating atmospheric radial orbs (cyan, indigo, purple), isometric grid, translucent glass cards with 24px backdrop blur, and luminous neon telemetry indicators.
- **Authentication**: Skiper68 animated digit/passcode transitions, tactile Web Audio sound synthesis, Google OAuth, GitHub, FIDO2 Passkeys, and role switcher.
- **Backend**: Python 3.12, **FastAPI**, **Uvicorn**
- **Database (SQL)**: **SQLite** with **SQLAlchemy ORM** (`civictrack.db`)
- **Frontend**: Responsive Single-Page Application (HTML5, Vanilla CSS, Modern JavaScript)
- **API Architecture**: RESTful endpoints with JSON payloads and real-time SQL state synchronization

---

## 🌟 Key Features (12-Module System)

1. **Home / Landing Portal**: Clean modern landing page with hero action cards for instant complaint submission, tracking, and personal history.
2. **Submit Complaint Form**: Structured intake with category selection (Streetlight, Water, Garbage, Roads, Drainage), description, geotagged location, photographic proof upload, and AI priority auto-calculation.
3. **Dual-Identifier Generation**: Decouples internal database reference (`CIV-2026-1042`) from the public cryptographic tracking key (`TN-GOV-X7K92P4M`).
4. **Public Complaint Tracker**: Enter any tracking key to inspect the live day-wise audit journal while citizen personal identity (PII) remains strictly protected.
5. **Day-Wise Verifiable Timeline**:
   - 🟢 **Verified Government Events**: Real administrative milestones backed by official timestamps and department actors.
   - ⚪ **Stationary / No Event Logged**: Transparently marks inactive days where zero municipal progress was recorded — strictly avoiding synthetic progress bars.
   - 🟡 **AI Inactivity / Delay Detection**: Automatic detection of inactivity exceeding standard SLAs (>48 hours).
   - 🔴 **Multi-Tier Escalation Flag**: Surfaces automated recommendations for higher-level officer review.
6. **Officer / Government Dashboard**:
   - Real-time municipal KPIs: Total Complaints (248), Pending (71), In Progress (43), Resolved (134), Delayed (18), Escalations (6) — computed via SQL `COUNT(*)`.
   - Interactive complaints management table with status filtering.
7. **Officer Action Console**:
   - Operational tools for municipal engineers (`Assign to Officer`, `Start Work`, `Update Progress`, `Mark as Resolved`).
   - Adding notes or updates directly inserts into SQL and appends new verified milestones (e.g. Day 8 "Work Started", Day 10 "Resolved") to the citizen's public timeline in real time!
8. **My Complaints (Citizen View)**: Filter tabs (`All`, `Pending`, `In Progress`, `Resolved`) with status pills and active day counters.
9. **Role-Based Authentication**: Modal supporting Citizen, Municipal Officer (`officer@gov.in`), and Admin perspectives.

---

## 📂 Project Structure

```
├── civictrack.db        # Real SQL Database (SQLite) storing complaints & timeline events
├── database.py          # SQLAlchemy models (Complaint, TimelineEvent, Officer) & Seeder
├── server.py            # FastAPI REST API endpoints & static frontend server
├── run.py               # One-command launcher (starts server & opens browser)
├── index.html           # 12-Screen responsive frontend application
├── PROJECT_CONCEPT.md   # Academic & architectural specification dossier
└── README.md            # Project overview & execution guide
```

---

## 🚀 Quick Start (Running with Python & SQL)

### Option 1: One-Command Launcher (Recommended)
```bash
python run.py
```
This automatically initializes the SQLite database (`civictrack.db`), starts the FastAPI server on `http://127.0.0.1:8000`, and opens your web browser.

### Option 2: Run Server Directly
```bash
# Start FastAPI backend
python server.py
```
Open **http://127.0.0.1:8000** in your browser.

### Option 3: Standalone Client Mode
You can also double-click `index.html` to run in browser standalone mode. The frontend will automatically detect the Python backend on `http://127.0.0.1:8000` when running, or provide an offline fallback if the server is stopped.

---

## 📡 REST API Documentation

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/health` | `GET` | Validates API & SQLite database health and table record counts |
| `/api/kpis` | `GET` | Live SQL `COUNT(*)` KPI metrics (Pending, In Progress, Resolved, Delayed, Escalations) |
| `/api/complaints` | `GET` | Queries complaints from SQL with optional `?status=` or `?category=` filters |
| `/api/complaints/{key_or_id}` | `GET` | Retrieves full grievance and foreign-key joined day-wise timeline records |
| `/api/complaints` | `POST` | Registers a new citizen complaint and inserts Day 0 milestone into SQL |
| `/api/officer/update` | `POST` | Updates complaint status and appends verified audit event into SQL |
| `/api/auth/config` | `GET` | Returns configured Google OAuth 2.0 client ID and auth capabilities |
| `/api/auth/google` | `POST` | Ingests Google JWT token, validates identity, and creates/updates user in SQLite |
| `/api/auth/users` | `GET` | Retrieves all registered/authenticated users from SQLite `users` table |

Interactive OpenAPI documentation is available at **http://127.0.0.1:8000/docs**.

---

## 🔐 Google OAuth 2.0 Configuration

Kizuno-AI is configured with official Google Identity Services (GIS):
- **Client ID**: `485227555296-5jqikr8c4ruddifkp7uj2k3h82sfivd1.apps.googleusercontent.com`
- **Authorized JavaScript Origins** (Google Cloud Console):
  - `http://127.0.0.1:8000`
  - `http://localhost:8000`
  - `http://localhost`
- **Features**: One-click Google Identity popup, JWT verification, real SQL user persistence in `civictrack.db`, profile photo and name synchronization, session recovery from `localStorage`, and instant local dev bypass.

---

## 📄 License
MIT License. Created by [Dilip Palanisamy](https://github.com/DilipPalanisamy).
