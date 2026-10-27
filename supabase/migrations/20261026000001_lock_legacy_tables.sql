-- The original app synced to two tables with Row Level Security off.
-- They hold real history (Dec 2025 - Mar 2026), so they're kept, renamed,
-- and locked away from the API: RLS on with no policies, no grants.
-- Only the database owner (and the Supabase connector) can read them.

alter table public.tasks rename to tasks_v1;
alter table public.sessions rename to sessions_v1;

alter table public.tasks_v1 enable row level security;
alter table public.sessions_v1 enable row level security;

revoke all on public.tasks_v1, public.sessions_v1 from anon, authenticated;

comment on table public.tasks_v1 is
  'Read-only history from the original app (Dec 2025 - Mar 2026). Not used by the current app. Columns: text, quadrant, date (YYYY-MM-DD), done, completed_at.';
comment on table public.sessions_v1 is
  'Read-only focus-session history from the original app. Not used by the current app.';
