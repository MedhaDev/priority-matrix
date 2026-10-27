-- 1. Move the old app's tables out of the API-exposed schema into a private one.
create schema if not exists archive;
revoke all on schema archive from public, anon, authenticated;
alter table public.tasks_v1 set schema archive;
alter table public.sessions_v1 set schema archive;
alter sequence if exists public.sessions_id_seq set schema archive;

-- 2. The app talks to the REST API only. Turning GraphQL off means the
--    /graphql/v1 endpoint can't reveal table structure to anyone.
drop extension if exists pg_graphql;
