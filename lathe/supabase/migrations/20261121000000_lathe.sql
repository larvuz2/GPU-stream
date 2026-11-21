-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- Lathe's data: who has how many credits, which sessions they ran, and the keys
-- their agents present.
--
-- Only the control plane reads or writes these tables, with the service role.
-- Row-level security is on with no policy for a signed-in user, so the keys a
-- browser holds reach nothing here, and every rule about who may see what is
-- one place, the control plane, which answers each request for the user its
-- token names.
--
-- Everything that moves credits or changes a session's state is a function, so
-- it is one transaction whatever the caller does next: a request that dies
-- halfway leaves a session `starting`, which the control plane's reconciler
-- ends and refunds, and never a debit without its ledger row. Credits are whole
-- numbers; what one is worth is the catalog's to say.

create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text not null default '',
    credits integer not null default 0 check (credits >= 0),
    max_sessions integer not null default 1 check (max_sessions >= 0),
    created_at timestamptz not null default now()
);

create table public.sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles (id) on delete cascade,
    app text not null,
    tier text not null,
    region text not null default 'auto',
    status text not null check (status in ('queued', 'starting', 'running', 'ended', 'failed')),
    -- The Modal Sandbox, once there is one
    sandbox_id text,
    credits_per_minute integer not null check (credits_per_minute >= 0),
    credits_used integer not null default 0,
    created_at timestamptz not null default now(),
    -- When it left the queue to be started, which a session that is never started is timed from
    claimed_at timestamptz,
    started_at timestamptz,
    -- Usage is charged up to here; the next charge starts from it
    charged_until timestamptz,
    ended_at timestamptz,
    end_reason text
);

create index sessions_user_created on public.sessions (user_id, created_at desc);
create index sessions_open on public.sessions (status, created_at)
    where status in ('queued', 'starting', 'running');

create table public.credit_ledger (
    id bigint generated always as identity primary key,
    user_id uuid not null references public.profiles (id) on delete cascade,
    delta integer not null,
    reason text not null check (reason in ('signup', 'usage', 'purchase', 'refund', 'grant')),
    session_id uuid references public.sessions (id) on delete set null,
    -- What a purchase was paid by, so a payment delivered twice is credited once
    reference text unique,
    created_at timestamptz not null default now()
);

create index credit_ledger_user on public.credit_ledger (user_id, created_at desc);

create table public.api_keys (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles (id) on delete cascade,
    name text not null,
    -- The first characters of the secret, to tell keys apart in a list
    prefix text not null,
    -- SHA-256 of the secret, hex; the secret itself is never stored
    key_hash text not null unique,
    created_at timestamptz not null default now(),
    last_used_at timestamptz,
    revoked_at timestamptz
);

create index api_keys_user on public.api_keys (user_id, created_at desc);

create table public.session_events (
    id bigint generated always as identity primary key,
    session_id uuid not null references public.sessions (id) on delete cascade,
    kind text not null,
    detail text not null default '',
    created_at timestamptz not null default now()
);

create index session_events_session on public.session_events (session_id, created_at);

alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.api_keys enable row level security;
alter table public.session_events enable row level security;

-- The profile of a user, made with its sign-up credits the first time it is
-- asked for.
create function public.lathe_ensure_profile(p_user uuid, p_email text, p_signup_credits integer)
returns public.profiles
language plpgsql
security definer
set search_path = public
as $$
declare
    profile public.profiles;
begin
    insert into profiles (id, email, credits)
    values (p_user, coalesce(p_email, ''), p_signup_credits)
    on conflict (id) do nothing
    returning * into profile;
    if found then
        if p_signup_credits > 0 then
            insert into credit_ledger (user_id, delta, reason) values (p_user, p_signup_credits, 'signup');
        end if;
        return profile;
    end if;
    select * into profile from profiles where id = p_user;
    return profile;
end;
$$;

-- A new session for a user: `starting` while fewer than `p_capacity` sessions
-- run across all users, `queued` beyond that. Refused with `insufficient_credits`
-- when the user cannot pay for a first minute, and with `session_limit` when
-- they already hold as many open sessions as their profile allows. The
-- profile's row is locked first, so two requests at once cannot both pass the
-- limit.
create function public.lathe_request_session(
    p_user uuid, p_app text, p_tier text, p_region text, p_credits_per_minute integer, p_capacity integer
)
returns public.sessions
language plpgsql
security definer
set search_path = public
as $$
declare
    profile public.profiles;
    session public.sessions;
    open_sessions integer;
    running integer;
begin
    select * into profile from profiles where id = p_user for update;
    if not found then
        raise exception 'no_profile' using errcode = 'P0001';
    end if;
    if profile.credits < greatest(p_credits_per_minute, 1) then
        raise exception 'insufficient_credits' using errcode = 'P0001';
    end if;
    select count(*) into open_sessions from sessions
    where user_id = p_user and status in ('queued', 'starting', 'running');
    if open_sessions >= profile.max_sessions then
        raise exception 'session_limit' using errcode = 'P0001';
    end if;
    -- One at a time across users, or two requests could both take the last place
    perform pg_advisory_xact_lock(hashtext('lathe_capacity'));
    select count(*) into running from sessions where status in ('starting', 'running');
    insert into sessions (user_id, app, tier, region, status, claimed_at, credits_per_minute)
    values (p_user, p_app, p_tier, p_region,
            case when running < p_capacity then 'starting' else 'queued' end,
            case when running < p_capacity then now() end, p_credits_per_minute)
    returning * into session;
    insert into session_events (session_id, kind) values (session.id, session.status);
    return session;
end;
$$;

-- The queued sessions there is now room for, oldest first, moved to `starting`
-- for the caller to start.
create function public.lathe_claim_queued(p_capacity integer)
returns setof public.sessions
language plpgsql
security definer
set search_path = public
as $$
declare
    running integer;
begin
    perform pg_advisory_xact_lock(hashtext('lathe_capacity'));
    select count(*) into running from sessions where status in ('starting', 'running');
    return query
    update sessions set status = 'starting', claimed_at = now()
    where id in (
        select id from sessions where status = 'queued'
        order by created_at limit greatest(p_capacity - running, 0)
    )
    returning *;
end;
$$;

-- A session's Sandbox is up: it runs, and is charged from now.
create function public.lathe_session_started(p_session uuid, p_sandbox_id text)
returns public.sessions
language plpgsql
security definer
set search_path = public
as $$
declare
    session public.sessions;
begin
    update sessions
    set status = 'running', sandbox_id = p_sandbox_id, started_at = now(), charged_until = now()
    where id = p_session and status = 'starting'
    returning * into session;
    if found then
        insert into session_events (session_id, kind, detail) values (p_session, 'running', p_sandbox_id);
    end if;
    return session;
end;
$$;

-- Charges a running session for the minutes since it was last charged, whole
-- ones unless `p_final`, which also charges the minute in progress: a session
-- pays for every minute it starts. A user is never charged below zero; what
-- they could not pay is theirs to keep, and the caller ends the session when
-- the answer says the credits are gone. Returns the credits the user has left.
create function public.lathe_charge_session(p_session uuid, p_final boolean)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    session public.sessions;
    elapsed double precision;
    minutes integer;
    due integer;
    left_over integer;
begin
    select * into session from sessions where id = p_session for update;
    if not found or session.charged_until is null then
        return null;
    end if;
    elapsed := extract(epoch from now() - session.charged_until) / 60.0;
    minutes := case when p_final then ceil(elapsed) else floor(elapsed) end;
    select credits into left_over from profiles where id = session.user_id for update;
    if minutes <= 0 then
        return left_over;
    end if;
    due := least(minutes * session.credits_per_minute, left_over);
    update profiles set credits = credits - due where id = session.user_id returning credits into left_over;
    update sessions
    set credits_used = credits_used + due, charged_until = charged_until + make_interval(mins => minutes)
    where id = p_session;
    if due > 0 then
        insert into credit_ledger (user_id, delta, reason, session_id)
        values (session.user_id, -due, 'usage', p_session);
    end if;
    return left_over;
end;
$$;

-- Ends an open session with its reason, charging a running one to the minute.
-- `p_failed` marks one that never ran or was lost, which is not charged for the
-- minute in progress.
create function public.lathe_end_session(p_session uuid, p_reason text, p_failed boolean)
returns public.sessions
language plpgsql
security definer
set search_path = public
as $$
declare
    session public.sessions;
begin
    select * into session from sessions where id = p_session for update;
    if not found or session.status in ('ended', 'failed') then
        return session;
    end if;
    if session.status = 'running' then
        perform lathe_charge_session(p_session, not p_failed);
    end if;
    update sessions
    set status = case when p_failed then 'failed' else 'ended' end, ended_at = now(), end_reason = p_reason
    where id = p_session
    returning * into session;
    insert into session_events (session_id, kind, detail) values (p_session, session.status, coalesce(p_reason, ''));
    return session;
end;
$$;

-- Adds credits to a user, once per `p_reference` where one is given: a payment
-- provider delivers a paid checkout more than once, and the second delivery
-- credits nothing. Returns the credits the user then has.
create function public.lathe_add_credits(p_user uuid, p_delta integer, p_reason text, p_reference text)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    balance integer;
begin
    begin
        insert into credit_ledger (user_id, delta, reason, reference) values (p_user, p_delta, p_reason, p_reference);
    exception when unique_violation then
        select credits into balance from profiles where id = p_user;
        return balance;
    end;
    update profiles set credits = credits + p_delta where id = p_user returning credits into balance;
    return balance;
end;
$$;

-- The user an API key belongs to, with the key marked used, or nothing for a
-- key that is unknown or revoked.
create function public.lathe_use_api_key(p_key_hash text)
returns uuid
language sql
security definer
set search_path = public
as $$
    update api_keys set last_used_at = now()
    where key_hash = p_key_hash and revoked_at is null
    returning user_id;
$$;

-- How many queued sessions are ahead of a queued one, itself included.
create function public.lathe_queue_position(p_session uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
    select count(*)::integer from sessions queued, sessions own
    where own.id = p_session and own.status = 'queued'
      and queued.status = 'queued' and queued.created_at <= own.created_at;
$$;

-- The functions are the control plane's alone: PostgREST exposes every function
-- of the schema to whoever may execute it, and these run as their owner.
revoke execute on function public.lathe_ensure_profile(uuid, text, integer) from public, anon, authenticated;
grant execute on function public.lathe_ensure_profile(uuid, text, integer) to service_role;
revoke execute on function public.lathe_request_session(uuid, text, text, text, integer, integer) from public, anon, authenticated;
grant execute on function public.lathe_request_session(uuid, text, text, text, integer, integer) to service_role;
revoke execute on function public.lathe_claim_queued(integer) from public, anon, authenticated;
grant execute on function public.lathe_claim_queued(integer) to service_role;
revoke execute on function public.lathe_session_started(uuid, text) from public, anon, authenticated;
grant execute on function public.lathe_session_started(uuid, text) to service_role;
revoke execute on function public.lathe_charge_session(uuid, boolean) from public, anon, authenticated;
grant execute on function public.lathe_charge_session(uuid, boolean) to service_role;
revoke execute on function public.lathe_end_session(uuid, text, boolean) from public, anon, authenticated;
grant execute on function public.lathe_end_session(uuid, text, boolean) to service_role;
revoke execute on function public.lathe_add_credits(uuid, integer, text, text) from public, anon, authenticated;
grant execute on function public.lathe_add_credits(uuid, integer, text, text) to service_role;
revoke execute on function public.lathe_use_api_key(text) from public, anon, authenticated;
grant execute on function public.lathe_use_api_key(text) to service_role;
revoke execute on function public.lathe_queue_position(uuid) from public, anon, authenticated;
grant execute on function public.lathe_queue_position(uuid) to service_role;
