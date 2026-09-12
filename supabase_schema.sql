-- ==============================================================================
-- KIZUNO-AI: SUPABASE POSTGRESQL PRODUCTION DATABASE SCHEMA
-- Evidence-Based Civic Grievance & Real-Time Citizen Account Management
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. USERS TABLE (Primary Live User Registry)
CREATE TABLE IF NOT EXISTS public.users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    registration_method VARCHAR(32) NOT NULL DEFAULT 'email', -- 'google' or 'email'
    email_verified BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash VARCHAR(255) NULL,                          -- PBKDF2-SHA256 salted hash, never plain text
    role VARCHAR(32) NOT NULL DEFAULT 'citizen',             -- 'citizen' or 'officer' or 'admin'
    avatar_url TEXT NULL,
    google_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),           -- Permanent exact creation timestamp (never changed)
    last_login TIMESTAMPTZ NOT NULL DEFAULT NOW()            -- Updated on every login
);

-- Case-insensitive unique constraint on email
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON public.users (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_created_at ON public.users (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_registration_method ON public.users (registration_method);

-- 3. COMPLAINTS TABLE (Relational Civic Grievance Ledger)
CREATE TABLE IF NOT EXISTS public.complaints (
    id VARCHAR(32) PRIMARY KEY,                               -- e.g. CIV-2026-1042
    tracking_key VARCHAR(32) UNIQUE NOT NULL,                 -- e.g. TN-GOV-X7K92P4M
    user_id BIGINT REFERENCES public.users(id) ON DELETE SET NULL, -- Relational link to users table
    category VARCHAR(64) NOT NULL,
    category_icon VARCHAR(16) DEFAULT '📋',
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(255) NOT NULL,
    photo_url TEXT NULL,
    priority VARCHAR(32) DEFAULT 'Medium',                    -- Low, Medium, High, Critical
    status VARCHAR(32) DEFAULT 'Pending',                     -- Pending, In Progress, Delayed, Resolved, Escalated
    day_label VARCHAR(32) DEFAULT 'Day 0',
    last_updated VARCHAR(64) NOT NULL,
    department VARCHAR(128) DEFAULT 'Coimbatore Municipal Corporation',
    assigned_officer VARCHAR(128) NULL,
    citizen_email VARCHAR(128) NULL,
    citizen_name VARCHAR(128) NULL DEFAULT 'Citizen',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_complaints_user_id ON public.complaints (user_id);
CREATE INDEX IF NOT EXISTS idx_complaints_citizen_email ON public.complaints (LOWER(citizen_email));
CREATE INDEX IF NOT EXISTS idx_complaints_status ON public.complaints (status);
CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON public.complaints (created_at DESC);

-- 4. TIMELINE EVENTS TABLE (Cryptographic Day-wise Audit Trail)
CREATE TABLE IF NOT EXISTS public.timeline_events (
    id BIGSERIAL PRIMARY KEY,
    complaint_id VARCHAR(32) REFERENCES public.complaints(id) ON DELETE CASCADE,
    day_index VARCHAR(32) NOT NULL,                           -- e.g. Day 0, Day 1
    event_date VARCHAR(32) NOT NULL,                          -- e.g. Sep 12, 2026
    status_type VARCHAR(32) NOT NULL,                         -- registered, forwarded, work-started, resolved, delayed
    tag_type VARCHAR(32) NOT NULL,                            -- tag-verified, tag-ai-inference, tag-stationary
    tag_text VARCHAR(64) NOT NULL,                            -- Verified Event, AI Inference
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    official_node VARCHAR(255) NULL,
    evidence_ref VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_events_complaint_id ON public.timeline_events (complaint_id);

-- 5. EMAIL VERIFICATIONS TABLE (For Real Gmail OTP Delivery)
CREATE TABLE IF NOT EXISTS public.email_verifications (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(128) NOT NULL,
    code VARCHAR(6) NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '10 minutes')
);

CREATE INDEX IF NOT EXISTS idx_email_verif_email ON public.email_verifications (LOWER(email));

-- 6. ROW LEVEL SECURITY (RLS) POLICIES
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_verifications ENABLE ROW LEVEL SECURITY;

-- Service role full access for backend API operations:
DROP POLICY IF EXISTS service_role_users ON public.users;
CREATE POLICY service_role_users ON public.users
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_complaints ON public.complaints;
CREATE POLICY service_role_complaints ON public.complaints
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_timeline ON public.timeline_events;
CREATE POLICY service_role_timeline ON public.timeline_events
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_email_verif ON public.email_verifications;
CREATE POLICY service_role_email_verif ON public.email_verifications
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Public / Anonymous read access for public tracking of complaints and timelines:
DROP POLICY IF EXISTS public_read_complaints ON public.complaints;
CREATE POLICY public_read_complaints ON public.complaints
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS public_read_timeline ON public.timeline_events;
CREATE POLICY public_read_timeline ON public.timeline_events
    FOR SELECT TO anon, authenticated USING (true);

-- Users table privacy: Public cannot browse complete user registry; citizens only read self:
DROP POLICY IF EXISTS authenticated_read_own_user ON public.users;
CREATE POLICY authenticated_read_own_user ON public.users
    FOR SELECT TO authenticated
    USING (auth.jwt() ->> 'email' = email);

-- 7. ENABLE REALTIME BROADCAST
-- Allows Admin Dashboard to receive instant live notifications when users register or update
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.users;
        ALTER PUBLICATION supabase_realtime ADD TABLE public.complaints;
    END IF;
END $$;
