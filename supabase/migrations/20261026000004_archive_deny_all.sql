-- Make "no access" explicit on the archived tables (RLS was already on with no grants).
create policy "No access through the API" on archive.tasks_v1 as restrictive for all to public using (false) with check (false);
create policy "No access through the API" on archive.sessions_v1 as restrictive for all to public using (false) with check (false);
