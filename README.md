# 📱 CivicTrack (Kizuna-AI) — Citizen Complaint Tracking & Accountability System

> **"Submit your complaint and follow its entire journey until resolution."**  
> An evidence-based civic grievance platform connecting citizens with municipal departments through day-wise audit journals, bi-directional officer workflows, and automated delay detection.

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
   - Real-time municipal KPIs: Total Complaints (248), Pending (71), In Progress (43), Resolved (134), Delayed (18), Escalations (6).
   - Interactive complaints management table with status filtering.
7. **Officer Action Console**:
   - Operational tools for municipal engineers (`Assign to Officer`, `Start Work`, `Update Progress`, `Mark as Resolved`).
   - Adding notes or updates instantly modifies the complaint state and appends new verified milestones (e.g. Day 8 "Work Started", Day 10 "Resolved") to the citizen's public timeline in real time!
8. **My Complaints (Citizen View)**: Filter tabs (`All`, `Pending`, `In Progress`, `Resolved`) with status pills and active day counters.
9. **Role-Based Authentication**: Modal supporting Citizen, Municipal Officer (`officer@gov.in`), and Admin perspectives.

---

## 📂 Project Architecture

- [`index.html`](file:///c:/Users/DILIP/OneDrive/Desktop/kizuno-AI/index.html): Complete standalone, responsive single-page web application embodying all 12 mockup screens with zero external runtime build dependencies.
- [`PROJECT_CONCEPT.md`](file:///c:/Users/DILIP/OneDrive/Desktop/kizuno-AI/PROJECT_CONCEPT.md): Comprehensive project design document covering the real-world problem, three-tier verification hierarchy, relational database schema, SLA matrices, and CPGRAMS/state gateway integration strategy.

---

## 🚀 Quick Start

Open `index.html` directly in any modern web browser (Edge, Chrome, Safari, Firefox). No server or npm build required.

```bash
# Clone the repository
git clone https://github.com/DilipPalanisamy/Kisuna-AI.git

# Navigate to project directory
cd Kisuna-AI

# Launch in default browser (Windows)
start index.html
```

---

## 📄 License
MIT License. Created by [Dilip Palanisamy](https://github.com/DilipPalanisamy).
