-- Run this in the Supabase SQL editor (Dashboard → SQL Editor → New query).
-- Creates a no-op function the anon role may call. The GitHub Actions
-- keep-alive workflow calls it every few days so the free-tier project
-- registers DB activity and does not auto-pause. It returns only 'ok' and
-- exposes no data, so it is safe to call with the public anon key.

create or replace function public.keepalive()
returns text
language sql
as $$ select 'ok'::text $$;

grant execute on function public.keepalive() to anon;
