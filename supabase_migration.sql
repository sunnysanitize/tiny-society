-- Run this in the Supabase SQL editor (Dashboard → SQL Editor → New query)

create table if not exists saves (
  id           uuid        default gen_random_uuid() primary key,
  user_id      uuid        references auth.users not null,
  name         text        not null default 'Untitled World',
  world_data   jsonb       not null,
  result_data  jsonb,
  day_count    int         not null default 0,
  agent_count  int         not null default 0,
  world_prompt text        not null default '',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

alter table saves enable row level security;

create policy "Users can manage their own saves"
  on saves for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);
