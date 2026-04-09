-- Set passwords for Supabase service roles to match POSTGRES_PASSWORD.
-- The supabase/postgres image creates these roles but with random passwords;
-- GoTrue and PostgREST need to connect with a known password.

ALTER ROLE supabase_auth_admin WITH PASSWORD 'postgres';
ALTER ROLE authenticator WITH PASSWORD 'postgres';

-- Ensure supabase_auth_admin owns the auth schema
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON ALL TABLES IN SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON ALL ROUTINES IN SCHEMA auth TO supabase_auth_admin;
