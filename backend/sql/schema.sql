-- Kettu: numbers only, never words someone said.
-- Run once in the Supabase SQL editor (Mumbai region project).

create table if not exists usage_events (
  id bigserial primary key,
  device_id uuid not null,
  kind text not null,              -- note, reply_preview, reply_speak
  audio_seconds numeric,
  tts_chars int,
  llm_tokens int,
  detected_lang text,
  my_lang text,
  latency_ms int,
  status text,                     -- ok, or an error code
  created_at timestamptz default now()
);
create index if not exists usage_events_day on usage_events (created_at);
create index if not exists usage_events_device on usage_events (device_id, created_at);

create table if not exists feedback (
  id bigserial primary key,
  device_id uuid not null,
  kind text not null,              -- note or reply
  rating smallint not null,        -- 1 or -1
  reason text,                     -- wrong_language, wrong_words, bad_translation, ...
  lang text,
  created_at timestamptz default now()
);

create table if not exists daily_budget (
  day date primary key,
  stt_seconds_used numeric default 0,
  tts_chars_used int default 0,
  llm_tokens_used int default 0,
  stt_seconds_cap numeric not null,
  tts_chars_cap int not null
);

-- WhatsApp bot preferences, keyed by sha256(salt + phone). The raw number is never stored.
create table if not exists wa_prefs (
  wa_hash text primary key,
  my_lang text,
  voice text default 'female',
  updated_at timestamptz default now()
);

-- Only the backend (service role) touches these tables.
alter table usage_events enable row level security;
alter table feedback enable row level security;
alter table daily_budget enable row level security;
alter table wa_prefs enable row level security;

-- Handy views for the progress post
create or replace view kettu_stats with (security_invoker = true) as
select
  count(distinct device_id) filter (where kind = 'note' and status = 'ok') as unique_devices,
  count(*) filter (where kind = 'note' and status = 'ok') as notes,
  count(*) filter (where kind = 'reply_speak' and status = 'ok') as voice_replies,
  percentile_cont(0.5) within group (order by latency_ms) filter (where kind = 'note' and status = 'ok') as median_note_ms
from usage_events;

create or replace view kettu_thumbs with (security_invoker = true) as
select lang, kind,
  count(*) filter (where rating = 1) as up,
  count(*) filter (where rating = -1) as down,
  round(100.0 * count(*) filter (where rating = 1) / nullif(count(*), 0), 1) as up_pct
from feedback group by lang, kind order by lang, kind;

-- Views must not bypass RLS or expose aggregate usage through the public API.
revoke all on public.kettu_stats, public.kettu_thumbs from anon, authenticated;
grant select on public.kettu_stats, public.kettu_thumbs to service_role;
