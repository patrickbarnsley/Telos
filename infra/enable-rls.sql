-- Telos: close the PostgREST exposure on the public schema.
--
-- Why this shape. Every Telos table is keyed on tester_name, not on a Supabase
-- auth.uid(), and the application reaches Postgres directly with psycopg2 as the
-- table owner. It never uses the Supabase data API. So the correct policy set is
-- the empty one: enable RLS with no permissive policies, and each table becomes
-- unreachable for every role EXCEPT the owner, which bypasses RLS by design.
--
-- Effect on the running app: none. The owner bypass means Streamlit and the
-- FastAPI service keep full access. What changes is that a request arriving at
-- https://<project>.supabase.co/rest/v1/<table> carrying the anon key gets
-- nothing back.
--
-- Run this in the Supabase SQL editor. It is idempotent; re-running is safe.

-- Without this, one bad statement aborts the transaction and every following
-- statement is skipped, while the session still reports success. That failure
-- mode was hit while writing this file: it looked applied and protected nothing.
\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.ai_spend ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.career_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.critical_path ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guide_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_preps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.waitlist ENABLE ROW LEVEL SECURITY;

-- Belt and braces. RLS alone is sufficient, but revoking the grants means the
-- tables are not even surfaced by PostgREST's schema introspection.
REVOKE ALL ON public.ai_spend FROM anon, authenticated;
REVOKE ALL ON public.career_paths FROM anon, authenticated;
REVOKE ALL ON public.critical_path FROM anon, authenticated;
REVOKE ALL ON public.guide_progress FROM anon, authenticated;
REVOKE ALL ON public.interview_preps FROM anon, authenticated;
REVOKE ALL ON public.jobs FROM anon, authenticated;
REVOKE ALL ON public.match_results FROM anon, authenticated;
REVOKE ALL ON public.profile FROM anon, authenticated;
REVOKE ALL ON public.resume_versions FROM anon, authenticated;
REVOKE ALL ON public.usage_events FROM anon, authenticated;
REVOKE ALL ON public.user_plans FROM anon, authenticated;
REVOKE ALL ON public.user_sessions FROM anon, authenticated;
REVOKE ALL ON public.waitlist FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

COMMIT;

-- Verification. Both of these should return zero rows.
--
--   SELECT tablename FROM pg_tables
--    WHERE schemaname = 'public' AND rowsecurity = false;
--
--   SELECT table_name, privilege_type FROM information_schema.role_table_grants
--    WHERE table_schema = 'public' AND grantee IN ('anon','authenticated');
--
-- IMPORTANT, for whoever changes the connection string later: this design
-- depends on the application connecting as the table OWNER. If the app is moved
-- to a non-owner role, every query starts returning zero rows, because there are
-- no permissive policies. That is the safe direction to fail in, but it will
-- look like the database has been wiped. It has not. Add policies at that point.
