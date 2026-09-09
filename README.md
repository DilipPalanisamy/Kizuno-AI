# KizunaX (Kizuna-AI) — Evidence-Based Citizen Grievance Tracking Engine

KizunaX is an evidence-based citizen grievance tracking system styled after modern e-commerce delivery trackers (Amazon / Flipkart). It brings unprecedented transparency to public grievance redressal by establishing an immutable audit stream for government actions and separating official administrative records from algorithmic predictions.

---

## 🛡️ Core Integrity Principles

1. **No Synthetic Timeline Steps**:
   - Zero synthetic steps are generated based on elapsed calendar days.
   - Every step either represents a verified administrative event or explicitly records an inactive period.
2. **Strict Verification Hierarchy**:
   - **Verified Government Events**: Official administrative milestones backed by API references, timestamps, and department actors.
   - **Stationary / No Event Logged**: Transparently documents days where government portals logged zero activity.
   - **AI Audit Inferences**: Algorithmic delay warnings, bottleneck detections, and SLA breach probability flags clearly labeled (`NOT A GOV RECORD`).
3. **E-Commerce Tracking Experience**:
   - Dynamic horizontal stage stepper (`Lodged` → `Assigned` → `Inspection` → `Work Order` → `Resolved`).
   - Real-time progress line interpolation.
   - Interactive citizen action drawer (Escalation Notices, RTI Dossiers, Resolution Certificates).

---

## 🚀 Quick Start

Open `index.html` in any modern web browser. No external dependencies, build tools, or package managers required.

```bash
# Clone the repository
git clone https://github.com/DilipPalanisamy/Kisuna-AI.git

# Navigate to project directory
cd Kisuna-AI

# Open in default browser (Windows)
start index.html
```

---

## 🧪 Included Test Scenarios

The engine includes two built-in scenarios accessible via the search bar or demo chips:

| Case Ref ID | Subject & Node | State | Highlights |
| :--- | :--- | :--- | :--- |
| **`TN-2026-839274`** | TWAD Board — Water Contamination (Coimbatore Zone 4) | Active / Delayed | 28-hour stationary gap following inspection, triggering an **AI Audit Inactivity Warning** and SLA risk flag. |
| **`KA-2026-419082`** | BESCOM — Transformer Sparking (Indiranagar) | Resolved | Fast-track resolution in 32 hours (16 hours ahead of SLA) with **100% verified compliance** and citizen OTP sign-off. |

---

## 📄 License
MIT License. Created by [Dilip Palanisamy](https://github.com/DilipPalanisamy).
