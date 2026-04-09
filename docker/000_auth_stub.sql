-- Local development stub for Supabase auth schema.
-- Runs before 001_initial.sql so that references to auth.uid() and
-- auth.users resolve against plain Postgres.

CREATE SCHEMA IF NOT EXISTS auth;

-- Minimal auth.users table — only the columns the migration trigger reads.
CREATE TABLE auth.users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT,
    raw_user_meta_data JSONB DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- auth.uid() returns the current session user id.
-- Set per-connection with:  SET app.current_user_id = '<uuid>';
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS UUID
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(
        nullif(current_setting('app.current_user_id', true), ''),
        '00000000-0000-0000-0000-000000000000'
    )::UUID;
$$;
