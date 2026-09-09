# 📱 CivicTrack (Kizuna-AI) — Citizen Complaint Tracking & Accountability System

> **"Submit your complaint and follow its entire journey until resolution."**  
> *A transparent, evidence-based grievance redressal platform combining day-wise audit journals, bi-directional officer workflows, and automated delay detection.*

---

## 1. Executive Summary & The Real-World Problem

Across municipalities, citizens encounter recurring civic failures daily:
- Broken streetlights casting neighborhoods into darkness
- Potholes and damaged asphalt causing road hazards
- Contaminated water pipelines and underground valve leaks
- Overflowing garbage bins and neglected municipal waste
- Blocked stormwater drainages leading to monsoon inundation

### The Core Frustration
In traditional grievance portals (e.g. municipal web forms, toll-free lines), citizen frustration does not arise primarily from the submission process. It arises from the opaque black box that follows:

> *“I submitted a complaint 10 days ago. What happened after that? Did anyone read it? Which department holds it? Is it stuck on someone’s desk? Has anyone even visited the site?”*

Existing portals display a static label: **`Status: Pending`**. This tells the citizen nothing about operational reality, department handoffs, or administrative neglect.

---

## 2. The CivicTrack Solution

CivicTrack replaces static status labels with a **dynamic, evidence-based tracking journey** styled after modern e-commerce logistics (Amazon/Flipkart delivery tracking).

```
                 👤 CITIZEN
                     │
                     ▼
              📱 CIVICTRACK
                     │
              Submit Complaint (Form + Photo)
                     │
                     ▼
             Generate Unique Identifiers
          ┌──────────┴──────────┐
          ▼                     ▼
   CIV-2026-1042        TN-GOV-X7K92P4M
   Internal ID          Tracking Key (Public Access)
          │                     │
          └──────────┬──────────┘
                     ▼
              🏢 Department Auto-Routing
              (Electrical Department / TWAD / BBMP)
                     │
                     ▼
             👨‍💼 Officer Dashboard
              (Assign • Start Work • Update • Resolve)
                     │
                     ▼
              📊 Verifiable Day-Wise Timeline
                     │
                     ▼
                👤 Citizen View
              (Real-Time Transparent Audit Trail)
```

---

## 3. Core Architectural Principles: Evidence vs Inference

To maintain absolute credibility, CivicTrack enforces a strict **Three-Tier Verification Hierarchy**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. VERIFIED GOVERNMENT EVENTS (Hard Administrative Facts)                   │
│    - Backed by official API responses, officer sign-offs, or dispatch logs. │
│    - Includes timestamps, acting officer, and official department node.     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. STATIONARY / NO EVENT LOGGED (Transparent Administrative Silence)        │
│    - Days elapsed where zero activity was registered on government servers. │
│    - Never creates fake progress steps based on elapsed calendar time.      │
│    - Explicitly marks administrative silence to establish accountability.   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. AI AUDIT INFERENCES (Predictive Intelligence & Delay Detection)          │
│    - Algorithmic analysis of elapsed time against category SLAs.             │
│    - Labels: "Delayed (>48h Inactive)", "Escalation Recommended (Level 1)".  │
│    - Explicitly disclaimed: "AI ASSESSMENT — NOT AN OFFICIAL GOV RECORD".   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. End-to-End System Workflow

### Step 1: Citizen Submits Complaint
The citizen enters:
- **Category**: Streetlight, Water Leak, Garbage, Road Damage, Drainage
- **Issue Title & Description**: Contextual details
- **Location**: Geotagged address (e.g. *Gandhipuram, Coimbatore*)
- **Photo Upload**: Photographic evidence of the failure
- **Priority**: System auto-assigns priority based on safety risk (Low, Medium, High, Critical)

### Step 2: Dual Identifier Generation
Upon submission, the system generates two decoupled keys:
1. **Internal Complaint ID (`CIV-2026-1042`)**: System primary key linking citizen records, backend logs, and officer assignments.
2. **Public Tracking Key (`TN-GOV-X7K92P4M`)**: Cryptographically random key that grants public read access to the grievance journey.

### Step 3: Privacy by Design
Anyone possessing `TN-GOV-X7K92P4M` can audit the progress, location, photo, priority, and timeline. However, all citizen **Personally Identifiable Information (PII)** — phone number, personal email, and identity — is strictly redacted (`Submitted by: Citizen (Anonymous)`).

### Step 4: Department Dispatch & Officer Dashboard
The grievance is automatically categorized and dispatched to the designated municipal agency (e.g. *Coimbatore Corporation Electrical Wing*). 

The Officer Dashboard provides:
- **Executive KPIs**: Total Complaints (248), Pending (71), In Progress (43), Resolved (134), Delayed (18), Escalations (6).
- **Interactive Action Console**:
  - `Assign to Officer`: Allocates field engineers.
  - `Start Work`: Formally logs initiation of physical repairs.
  - `Update Progress`: Logs procurement or parts requisition.
  - `Mark as Resolved`: Requires citizen OTP verification or photographic proof.

### Step 5: Day-Wise Audit Journal Progression
Instead of a static progress bar, the timeline logs a chronological journal:

```
DAY 0  | 🟢 Complaint Submitted
       | Complaint successfully registered in municipal gateway.
       | Verified: YES (Intake API: TN-E-SEVAI)

DAY 1  | 🔵 Forwarded to Department
       | Sent to Electrical Department (Zone 4 Sub-Division).
       | Verified: YES (Routed to AEE Operations)

DAY 2  | ⚪ No Response Recorded
       | Zero administrative or field updates logged on official servers.
       | Verified Record: Inactivity Logged

DAY 3  | ⚪ No Response Recorded
       | Continuous inactivity detected (48 consecutive hours).

DAY 5  | 🟡 DELAYED
       | Inactivity Threshold Exceeded (>48h without status update).
       | AI Rule Engine: SLA Warning Flagged

DAY 7  | 🔴 ESCALATION RECOMMENDED
       | Complaint has remained stationary past the regulatory SLA window.
       | Level 1 Escalation drafted to Superintending Engineer.

DAY 8  | 🔵 Work Started (Post-Officer Action)
       | Junior Engineer R. Selvam deployed with electrical repair unit.
       | Verified: YES (Officer Dashboard Action)

DAY 10 | 🟢 Resolved
       | Replacement LED luminaire fitted; circuit test validated.
       | Verified: YES (Case Closed)
```

---

## 5. Automatic Delay Detection & Escalation Engine

CivicTrack incorporates a category-aware Rule Engine that evaluates complaints daily:

| Category | Normal SLA Window | Delay Warning Threshold | Escalation Trigger | Escalation Target |
| :--- | :--- | :--- | :--- | :--- |
| **Streetlight** | 48 Hours | 48h Inactivity | Day 5 (120h) | Assistant Executive Engineer |
| **Water Contamination** | 24 Hours | 24h Inactivity | Day 3 (72h) | Executive Engineer (TWAD) |
| **Pothole / Road Hazard** | 72 Hours | 72h Inactivity | Day 7 (168h) | Divisional Engineer (Highways) |
| **Garbage Overflow** | 24 Hours | 24h Inactivity | Day 3 (72h) | City Health Officer |
| **Blocked Drainage** | 48 Hours | 48h Inactivity | Day 5 (120h) | Zonal Executive Engineer |

---

## 6. Relational Database Architecture

```
┌─────────────────┐       1:N       ┌─────────────────────────┐
│     USERS       ├─────────────────┤       COMPLAINTS        │
├─────────────────┤                 ├─────────────────────────┤
│ user_id (PK)    │                 │ complaint_id (PK)       │
│ name            │                 │ tracking_key (UNIQUE)   │
│ email           │                 │ category                │
│ phone           │                 │ title                   │
│ role (citizen)  │                 │ description             │
└─────────────────┘                 │ location                │
                                    │ photo_url               │
                                    │ priority (Low-Critical) │
                                    │ status (Pending-Closed) │
                                    │ department_id (FK)      │
                                    │ created_at              │
                                    └───────────┬─────────────┘
                                                │
                                                │ 1:N
                                    ┌───────────┴─────────────┐
                                    │    TIMELINE_EVENTS      │
                                    ├─────────────────────────┤
                                    │ event_id (PK)           │
                                    │ complaint_id (FK)       │
                                    │ day_index (Day 0, 1...) │
                                    │ event_date              │
                                    │ event_type (Enum)       │
                                    │   - verified_gov        │
                                    │   - stationary_gap      │
                                    │   - ai_delay            │
                                    │   - ai_escalation       │
                                    │ title                   │
                                    │ description             │
                                    │ node_or_officer         │
                                    │ evidence_hash           │
                                    └─────────────────────────┘
```

---

## 7. Real-World Integration Blueprint (CPGRAMS & State Portals)

CivicTrack is engineered to interface directly with existing e-Governance platforms:
- **Central Grievance Portals (CPGRAMS)**: Ingests reference IDs and queries authorized status endpoints via secure Webhook or REST APIs.
- **State Gateways (e.g. TN CM Helpline, Karnataka Sahayaa, Spandana AP)**: Connects to municipal dispatch queues.
- **Official Connector Fallback**: When direct government APIs are restricted (e.g. requiring citizen OTP/CAPTCHA), the **CivicTrack Official Data Connector Layer** enables authorized municipal officers to feed verified milestones directly via the Officer Dashboard.

---

## 8. Summary: What Sets CivicTrack Apart

| Traditional Complaint Portals | CivicTrack (Kizuna-AI) |
| :--- | :--- |
| Single opaque label: `Pending` | Full day-wise audit journal from submission to resolution |
| Fake progress bars based on elapsed calendar days | Zero synthetic events; real facts vs explicit stationary gaps |
| Citizens left wondering if action was taken | Automatic delay detection with visible escalation warnings |
| Department actions hidden in closed government intranet | Bi-directional accountability visible to the public |
| Citizen privacy compromised if tracking is shared | Dual-Key architecture decoupling public tracking from PII |
