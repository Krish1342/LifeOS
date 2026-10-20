-- LifeOS Supabase PostgreSQL Schema (Free Tier)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    timezone        TEXT NOT NULL DEFAULT 'UTC',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. OAuth Tokens Table (Per-service scoped, encrypted at rest)
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service         TEXT NOT NULL,  -- 'google_calendar', 'gmail', 'google_drive', 'slack'
    access_token    TEXT NOT NULL,  -- Encrypted with AES-256-GCM
    refresh_token   TEXT,           -- Encrypted with AES-256-GCM
    token_type      TEXT NOT NULL DEFAULT 'Bearer',
    scopes          TEXT[] NOT NULL,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, service)
);

CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_service ON oauth_tokens(user_id, service);

-- 3. Tasks Table (Owned exclusively by Task Agent)
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,           -- Summary only, never raw email/file content
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')),
    priority        TEXT NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    due_date        DATE,
    source          TEXT,           -- e.g., 'email:msg_xyz789', 'manual', 'calendar:evt_abc'
    source_ref      TEXT,
    linked_event_id TEXT,
    tags            TEXT[],
    sort_order      INTEGER DEFAULT 0,
    completed_at    TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,    -- Soft delete
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks(user_id, due_date) WHERE status != 'completed' AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source, source_ref);

-- 4. Agent Runs Table (Audit Log)
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    command_text    TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    skill_id        TEXT,
    a2a_task_id     TEXT,
    a2a_context_id  TEXT,
    status          TEXT NOT NULL DEFAULT 'submitted'
                        CHECK (status IN ('submitted', 'working', 'input_required',
                                          'completed', 'failed', 'cancelled')),
    input_params    JSONB,
    output_summary  TEXT,
    output_artifact JSONB,
    error_message   TEXT,
    duration_ms     INTEGER,
    parent_run_id   UUID REFERENCES agent_runs(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_user_created ON agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent ON agent_runs(parent_run_id) WHERE parent_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_runs_context ON agent_runs(a2a_context_id);

-- 5. User Config Table
CREATE TABLE IF NOT EXISTS user_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    config_key      TEXT NOT NULL,
    config_value    JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, config_key)
);

CREATE INDEX IF NOT EXISTS idx_user_config_user ON user_config(user_id);

-- 6. File Cache Table (Short-lived metadata cache)
CREATE TABLE IF NOT EXISTS file_cache (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    drive_file_id   TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    mime_type       TEXT,
    parent_folder_id TEXT,
    size_bytes      BIGINT,
    modified_at     TIMESTAMPTZ,
    cached_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '15 minutes'),
    UNIQUE(user_id, drive_file_id)
);

CREATE INDEX IF NOT EXISTS idx_file_cache_user_parent ON file_cache(user_id, parent_folder_id);
CREATE INDEX IF NOT EXISTS idx_file_cache_expires ON file_cache(expires_at);

-- Inactivity Heartbeat Function
CREATE OR REPLACE FUNCTION heartbeat() RETURNS void AS $$
BEGIN
  PERFORM 1;
END;
$$ LANGUAGE plpgsql;
