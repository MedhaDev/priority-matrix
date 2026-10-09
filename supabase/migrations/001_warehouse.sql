-- ─────────────────────────────────────────────────────────────
-- Priority Matrix warehouse on Supabase (synthetic data only).
-- Review, then run it yourself in the Supabase dashboard → SQL Editor.
--
-- What it does:
--   1. Creates the warehouse schemas: raw (loader), staging / intermediate /
--      marts (dbt), reconciliation (dbt seeds = answer key).
--   2. Creates raw.events (the loader also does this "if not exists").
--   3. Locks every one of those schemas away from Supabase's public API roles
--      (anon, authenticated). They are NOT in "Exposed schemas" by default;
--      this makes sure that stays true even if someone adds them later.
--   4. Creates a dedicated login role "pipeline" for the loader and dbt, so
--      you don't have to hand out the postgres password.
--
-- It does not touch the public schema or anything the app uses.
-- Safe to run twice.
-- ─────────────────────────────────────────────────────────────

-- 4. Pipeline role. Replace the password before running, and put the same
--    value in your git-ignored .env as PGPASSWORD. Never commit it.
do $$
begin
  if not exists (select from pg_roles where rolname = 'pipeline') then
    create role pipeline login password 'CHANGE-ME-to-a-long-random-password';
  end if;
end $$;
grant pipeline to postgres;   -- lets the dashboard's postgres user create schemas owned by pipeline
grant create, connect on database postgres to pipeline;

-- 1–2. Schemas and the raw table, owned by the pipeline role.
create schema if not exists raw            authorization pipeline;
create schema if not exists staging        authorization pipeline;
create schema if not exists intermediate   authorization pipeline;
create schema if not exists marts          authorization pipeline;
create schema if not exists reconciliation authorization pipeline;
create schema if not exists analytics      authorization pipeline;

create table if not exists raw.events (
    arrived_on  date        not null,
    line_no     integer     not null,
    body        jsonb       not null,
    source_file text        not null,
    loaded_at   timestamptz not null default now(),
    primary key (arrived_on, line_no)
);
alter table raw.events owner to pipeline;

-- 3. Keep the public API out.
do $$
declare s text;
begin
  foreach s in array array['raw', 'staging', 'intermediate', 'marts', 'reconciliation', 'analytics'] loop
    execute format('revoke all on schema %I from anon, authenticated, public', s);
    execute format('revoke all on all tables in schema %I from anon, authenticated, public', s);
    execute format('alter default privileges for role pipeline in schema %I revoke all on tables from anon, authenticated, public', s);
  end loop;
end $$;

-- Optional, for Tableau or another read-only tool later:
-- create role dashboard_reader login password 'CHANGE-ME';
-- grant usage on schema marts to dashboard_reader;
-- grant select on all tables in schema marts to dashboard_reader;
-- alter default privileges for role pipeline in schema marts grant select on tables to dashboard_reader;
