"""
Kizuno-AI - SQL Database Layer
PostgreSQL & SQLite + SQLAlchemy ORM implementation for real SQL storage of grievances,
day-wise timeline audit events, and municipal officer actions.
"""

import os
import shutil
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
    text,
    Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render and Supabase provide postgres:// which SQLAlchemy 1.4+ requires as postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )
    DB_DIALECT = "PostgreSQL"
else:
    # Standardize on kizuno.db as primary database; sync with civictrack.db if present
    if os.path.exists("civictrack.db") and not os.path.exists("kizuno.db"):
        try:
            shutil.copyfile("civictrack.db", "kizuno.db")
        except Exception:
            pass
    db_file = "./kizuno.db"
    DATABASE_URL = f"sqlite:///{db_file}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
    DB_DIALECT = "SQLite"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Complaint(Base):
    """
    SQL Table: complaints
    Stores official grievance records with dual-key architecture:
    - id: Internal departmental reference ID (e.g. CIV-2026-1042)
    - tracking_key: Public citizen tracking key (e.g. TN-GOV-X7K92P4M)
    """
    __tablename__ = "complaints"

    id = Column(String(32), primary_key=True, index=True)
    tracking_key = Column(String(32), unique=True, index=True, nullable=False)
    category = Column(String(64), nullable=False)
    category_icon = Column(String(16), default="📋")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(255), nullable=False)
    photo_url = Column(Text, nullable=True)
    priority = Column(String(32), default="Medium")  # Low, Medium, High, Critical
    status = Column(String(32), default="Pending")    # Pending, In Progress, Delayed, Resolved, Escalated
    day_label = Column(String(32), default="Day 0")
    last_updated = Column(String(64), nullable=False)
    department = Column(String(128), default="Coimbatore Municipal Corporation")
    assigned_officer = Column(String(128), nullable=True)
    citizen_email = Column(String(128), nullable=True, default="")
    citizen_name = Column(String(128), nullable=True, default="Citizen")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relational link to day-wise timeline audit events
    timeline_events = relationship(
        "TimelineEvent",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="TimelineEvent.id"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "trackingKey": self.tracking_key,
            "category": self.category,
            "categoryIcon": self.category_icon,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "photoUrl": self.photo_url,
            "priority": self.priority,
            "status": self.status,
            "dayLabel": self.day_label,
            "lastUpdated": self.last_updated,
            "department": self.department,
            "assignedOfficer": self.assigned_officer,
            "citizenEmail": self.citizen_email or "",
            "citizenName": self.citizen_name or "Citizen",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "timeline": [event.to_dict() for event in self.timeline_events]
        }


class TimelineEvent(Base):
    """
    SQL Table: timeline_events
    Stores day-wise chronological audit events.
    Strictly separates:
    - verified (Real administrative events)
    - stationary (Audit-verified gaps with 0 government updates)
    - delayed / escalated (AI Rule-based inferences)
    """
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.id"), nullable=False, index=True)
    day_index = Column(String(32), nullable=False)   # e.g. Day 0, Day 1
    event_date = Column(String(64), nullable=False)  # e.g. Apr 10, 2026
    status_type = Column(String(32), nullable=False) # submitted, forwarded, stationary, delayed, escalated, work-started, resolved
    tag_type = Column(String(32), nullable=False)    # tag-verified, tag-stationary, tag-ai-inference, tag-escalated
    tag_text = Column(String(64), nullable=False)    # Verified Event, No Event Logged, AI Assessment
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    official_node = Column(String(128), nullable=True)
    evidence_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("Complaint", back_populates="timeline_events")

    def to_dict(self):
        return {
            "id": self.id,
            "day": self.day_index,
            "date": self.event_date,
            "statusType": self.status_type,
            "tagType": self.tag_type,
            "tagText": self.tag_text,
            "title": self.title,
            "desc": self.description,
            "officialNode": self.official_node,
            "evidenceRef": self.evidence_ref
        }


class Officer(Base):
    """
    SQL Table: officers
    Stores authorized municipal officers for dispatch and triage.
    """
    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), unique=True, nullable=False)
    department = Column(String(128), nullable=False)
    role = Column(String(64), default="Junior Engineer")


class User(Base):
    """
    SQL Table: users
    Stores authenticated citizens, officers, and administrators (including Google OAuth & verified Gmail accounts).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(128), unique=True, nullable=True, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    avatar_url = Column(Text, nullable=True)
    role = Column(String(32), default="citizen")  # citizen, officer
    auth_provider = Column(String(32), default="google")  # google, email, pin
    password_hash = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "googleId": self.google_id,
            "email": self.email,
            "name": self.name,
            "avatarUrl": self.avatar_url,
            "role": self.role,
            "authProvider": self.auth_provider,
            "isVerified": self.is_verified,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "lastLogin": self.last_login.isoformat() if self.last_login else None
        }


class EmailVerification(Base):
    """
    SQL Table: email_verifications
    Stores real 6-digit verification OTP codes linked to Gmail addresses with expiration.
    """
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(128), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "expiresAt": self.expires_at.isoformat(),
            "isUsed": self.is_used
        }


def get_db():
    """Dependency helper for FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes database tables and populates realistic grievance datasets.
    """
    Base.metadata.create_all(bind=engine)

    # Ensure citizen ownership columns and user auth columns exist for existing databases
    try:
        with engine.connect() as conn:
            if "sqlite" in str(engine.url):
                # Check complaints table
                res = conn.execute(text("PRAGMA table_info(complaints)"))
                existing_cols = [row[1] for row in res.fetchall()]
                if "citizen_email" not in existing_cols:
                    conn.execute(text("ALTER TABLE complaints ADD COLUMN citizen_email VARCHAR(128) DEFAULT 'kumar.citizen@gmail.com'"))
                if "citizen_name" not in existing_cols:
                    conn.execute(text("ALTER TABLE complaints ADD COLUMN citizen_name VARCHAR(128) DEFAULT 'Citizen Kumar'"))

                # Check users table
                u_res = conn.execute(text("PRAGMA table_info(users)"))
                u_cols = [row[1] for row in u_res.fetchall()]
                if "password_hash" not in u_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                if "is_verified" not in u_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0"))

                conn.commit()
    except Exception as e:
        print("Schema migration note:", e)

    db = SessionLocal()

    # Ensure default verified citizen exists in SQL users table
    try:
        default_user = db.query(User).filter(User.email == "kumar.citizen@gmail.com").first()
        if not default_user:
            import hashlib
            salt = "4a8c9b2f1e0d3c5b"
            key = hashlib.pbkdf2_hmac('sha256', b'password123', salt.encode('utf-8'), 100000)
            hashed_pw = f"{salt}${key.hex()}"
            db.add(User(
                email="kumar.citizen@gmail.com",
                name="Citizen Kumar",
                password_hash=hashed_pw,
                is_verified=True,
                role="citizen",
                auth_provider="email"
            ))
            db.commit()
            print("Default citizen seeded in SQL users table: kumar.citizen@gmail.com / password123")
    except Exception as e:
        print("Default user seed note:", e)

    try:
        # Seed default Officer if not exists
        existing_officer = db.query(Officer).first()
        if not existing_officer:
            officer1 = Officer(
                name="DILIP",
                email="dilip.officer@gov.in",
                department="Coimbatore Corporation Electrical Wing",
                role="Junior Engineer"
            )
            db.add(officer1)
            db.commit()
        elif existing_officer.name != "DILIP":
            existing_officer.name = "DILIP"
            existing_officer.email = "dilip.officer@gov.in"
            db.commit()

        # Ensure complaints from civictrack.db are preserved and merged into kizuno.db
        if os.path.exists("civictrack.db") and os.path.exists("kizuno.db"):
            try:
                import sqlite3
                c_conn = sqlite3.connect("civictrack.db")
                c_cur = c_conn.cursor()
                c_cur.execute("SELECT id, tracking_key, category, category_icon, title, description, location, photo_url, priority, status, day_label, last_updated, department, assigned_officer, citizen_email, citizen_name FROM complaints")
                for row in c_cur.fetchall():
                    if not db.query(Complaint).filter(Complaint.id == row[0]).first():
                        db.add(Complaint(
                            id=row[0], tracking_key=row[1], category=row[2], category_icon=row[3],
                            title=row[4], description=row[5], location=row[6], photo_url=row[7],
                            priority=row[8], status=row[9], day_label=row[10], last_updated=row[11],
                            department=row[12], assigned_officer=row[13], citizen_email=row[14], citizen_name=row[15]
                        ))
                db.commit()
                c_conn.close()
            except Exception as ex:
                pass

        print("SQL Database successfully initialized. Complaints count reflects real user submissions.")

    except Exception as e:
        db.rollback()
        print(f"Database initialization note: {e}")
    finally:
        db.close()


def calculate_kpis(db):
    """
    Computes real-time KPI metrics directly from SQL queries.
    Starts at 0 by default. Accurate to submitted citizen grievances.
    """
    total = db.query(func.count(Complaint.id)).scalar() or 0
    pending = db.query(func.count(Complaint.id)).filter(Complaint.status == "Pending").scalar() or 0
    in_progress = db.query(func.count(Complaint.id)).filter(Complaint.status == "In Progress").scalar() or 0
    resolved = db.query(func.count(Complaint.id)).filter(Complaint.status == "Resolved").scalar() or 0
    delayed = db.query(func.count(Complaint.id)).filter(Complaint.status == "Delayed").scalar() or 0
    escalations = db.query(func.count(Complaint.id)).filter(Complaint.status == "Escalated").scalar() or 0

    return {
        "total": total,
        "pending": pending,
        "inProgress": in_progress,
        "resolved": resolved,
        "delayed": delayed,
        "escalations": escalations
    }
