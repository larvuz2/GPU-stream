-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- Moody Studio's data: a user's projects, each project's library, the events
-- its page polls, the conversation its agent keeps, and the GitHub account a
-- user connected.
--
-- The rule of the first migration holds for every table here: only the control
-- plane reads or writes them, with the service role, and row-level security is
-- on with no policy for a signed-in user. Which user owns a project is a column
-- the control plane filters on for every request; the functions below check it
-- again where they take a user.
--
-- A project runs one agent turn at a time. The turn is a column of the project
-- (`turn_id`) claimed and released by functions, so two messages sent at once
-- cannot both start one, and a turn whose worker died (it stopped calling
-- `moody_turn_alive`) is closed by the next message rather than holding the
-- project forever.

create table public.projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles (id) on delete cascade,
    name text not null check (char_length(name) between 1 and 120),
    -- A discipline of the catalog (`catalog.json`, `disciplines`) and one of its formats
    discipline text not null,
    format text not null default '',
    pinned boolean not null default false,
    -- The library's sections, in order: the project's own, never a fixed list
    library_sections jsonb not null default '[]'::jsonb check (jsonb_typeof(library_sections) = 'array'),
    -- The agent's tasks: [{id, title, status}]
    plan jsonb not null default '[]'::jsonb check (jsonb_typeof(plan) = 'array'),
    -- The repository the project is linked to, `owner/name`
    github_repo text,
    -- The agent turn running now, when its worker last said it was alive, and whether it was asked to stop
    turn_id uuid,
    turn_seen_at timestamptz,
    stop_requested boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index projects_user_updated on public.projects (user_id, updated_at desc);

-- An engine is a session of a project, started in that project's folder
alter table public.sessions add column project_id uuid references public.projects (id) on delete set null;

create index sessions_project on public.sessions (project_id, created_at desc) where project_id is not null;

create table public.assets (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references public.projects (id) on delete cascade,
    section text not null,
    name text not null check (char_length(name) between 1 and 120),
    -- How prompts name the entry (`@mara`); unique within a project where there is one
    tag text,
    description text not null default '',
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    -- The entry's files in the `library` bucket, newest first: [{kind, path, name, content_type}]
    media jsonb not null default '[]'::jsonb check (jsonb_typeof(media) = 'array'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (project_id, tag)
);

create index assets_project on public.assets (project_id, section, created_at);

create table public.project_events (
    id bigint generated always as identity primary key,
    project_id uuid not null references public.projects (id) on delete cascade,
    turn_id uuid,
    kind text not null check (kind in (
        'user_message', 'text', 'tool_start', 'tool_end', 'ask', 'plan', 'library', 'engine', 'turn_end', 'error'
    )),
    data jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index project_events_project on public.project_events (project_id, id);

-- The agent's conversation, in the Anthropic Messages format, one message per row in order. It is
-- replayed to the model as it was sent, which is what keeps the model's earlier reasoning valid,
-- so a row is appended and never rewritten once the model has answered past it.
create table public.agent_messages (
    id bigint generated always as identity primary key,
    project_id uuid not null references public.projects (id) on delete cascade,
    turn_id uuid,
    role text not null check (role in ('user', 'assistant', 'system')),
    content jsonb not null,
    created_at timestamptz not null default now()
);

create index agent_messages_project on public.agent_messages (project_id, id);

create table public.github_connections (
    user_id uuid primary key references public.profiles (id) on delete cascade,
    login text not null,
    avatar_url text not null default '',
    -- The OAuth token, Fernet-encrypted under a key derived from MOODY_SECRET_KEY; never stored in the clear
    token_encrypted text not null,
    scope text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.projects enable row level security;
alter table public.assets enable row level security;
alter table public.project_events enable row level security;
alter table public.agent_messages enable row level security;
alter table public.github_connections enable row level security;

-- A new session, as the first migration's function, for a project where one is
-- named and with a cap on how many sessions of the app may be open at once
-- where `p_app_seats` gives one (an app licensed per seat). Refused with
-- `no_project` for a project that is not the user's and `no_seats` when every
-- seat is taken; the seats are counted under the capacity lock, so two
-- requests cannot both take the last.
drop function public.moody_request_session(uuid, text, text, text, integer, integer);

create function public.moody_request_session(
    p_user uuid, p_app text, p_tier text, p_region text, p_credits_per_minute integer, p_capacity integer,
    p_project uuid default null, p_app_seats integer default null
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
    seated integer;
begin
    select * into profile from profiles where id = p_user for update;
    if not found then
        raise exception 'no_profile' using errcode = 'P0001';
    end if;
    if p_project is not null and not exists (select 1 from projects where id = p_project and user_id = p_user) then
        raise exception 'no_project' using errcode = 'P0001';
    end if;
    if profile.credits < greatest(p_credits_per_minute, 1) then
        raise exception 'insufficient_credits' using errcode = 'P0001';
    end if;
    select count(*) into open_sessions from sessions
    where user_id = p_user and status in ('queued', 'starting', 'running');
    if open_sessions >= profile.max_sessions then
        raise exception 'session_limit' using errcode = 'P0001';
    end if;
    -- One at a time across users, or two requests could both take the last place or seat
    perform pg_advisory_xact_lock(hashtext('moody_capacity'));
    if p_app_seats is not null then
        select count(*) into seated from sessions
        where app = p_app and status in ('queued', 'starting', 'running');
        if seated >= p_app_seats then
            raise exception 'no_seats' using errcode = 'P0001';
        end if;
    end if;
    select count(*) into running from sessions where status in ('starting', 'running');
    insert into sessions (user_id, app, tier, region, status, claimed_at, credits_per_minute, project_id)
    values (p_user, p_app, p_tier, p_region,
            case when running < p_capacity then 'starting' else 'queued' end,
            case when running < p_capacity then now() end, p_credits_per_minute, p_project)
    returning * into session;
    insert into session_events (session_id, kind) values (session.id, session.status);
    return session;
end;
$$;

-- Starts an agent turn on the user's project with the message that starts it,
-- recorded as the turn's first event, and returns the turn's ID. Refused with
-- `no_project` for a project that is not the user's and `turn_running` while
-- another turn is alive. A turn not heard from in `p_stale_seconds` has lost
-- its worker: it is closed here, with an error and its end, and the new one
-- starts.
create function public.moody_begin_turn(p_project uuid, p_user uuid, p_text text, p_stale_seconds integer)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    project public.projects;
    turn uuid;
begin
    select * into project from projects where id = p_project and user_id = p_user for update;
    if not found then
        raise exception 'no_project' using errcode = 'P0001';
    end if;
    if project.turn_id is not null then
        if project.turn_seen_at > now() - make_interval(secs => p_stale_seconds) then
            raise exception 'turn_running' using errcode = 'P0001';
        end if;
        insert into project_events (project_id, turn_id, kind, data) values
            (p_project, project.turn_id, 'error', jsonb_build_object('message', 'The previous turn stopped answering.')),
            (p_project, project.turn_id, 'turn_end', '{}'::jsonb);
    end if;
    turn := gen_random_uuid();
    update projects
    set turn_id = turn, turn_seen_at = now(), stop_requested = false, updated_at = now()
    where id = p_project;
    insert into project_events (project_id, turn_id, kind, data)
    values (p_project, turn, 'user_message', jsonb_build_object('text', p_text));
    return turn;
end;
$$;

-- The running turn's heartbeat: marks it alive and answers whether it should
-- go on, which it should not once it was asked to stop or is no longer the
-- project's turn.
create function public.moody_turn_alive(p_project uuid, p_turn uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    update projects set turn_seen_at = now()
    where id = p_project and turn_id = p_turn and not stop_requested;
    return found;
end;
$$;

-- Ends a turn that is still the project's, with its `turn_end` event in the
-- same transaction, so a page that sees the turn over has every event of it.
create function public.moody_end_turn(p_project uuid, p_turn uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    update projects set turn_id = null, turn_seen_at = null, stop_requested = false
    where id = p_project and turn_id = p_turn;
    if not found then
        return false;
    end if;
    insert into project_events (project_id, turn_id, kind) values (p_project, p_turn, 'turn_end');
    return true;
end;
$$;

-- Asks the user's running turn to stop, which it does at its next heartbeat; a
-- turn not heard from in `p_stale_seconds` is ended at once. Returns whether a
-- turn was running.
create function public.moody_stop_turn(p_project uuid, p_user uuid, p_stale_seconds integer)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    project public.projects;
begin
    select * into project from projects where id = p_project and user_id = p_user for update;
    if not found or project.turn_id is null then
        return false;
    end if;
    if project.turn_seen_at < now() - make_interval(secs => p_stale_seconds) then
        perform moody_end_turn(p_project, project.turn_id);
    else
        update projects set stop_requested = true where id = p_project;
    end if;
    return true;
end;
$$;

revoke execute on function public.moody_request_session(uuid, text, text, text, integer, integer, uuid, integer) from public, anon, authenticated;
grant execute on function public.moody_request_session(uuid, text, text, text, integer, integer, uuid, integer) to service_role;
revoke execute on function public.moody_begin_turn(uuid, uuid, text, integer) from public, anon, authenticated;
grant execute on function public.moody_begin_turn(uuid, uuid, text, integer) to service_role;
revoke execute on function public.moody_turn_alive(uuid, uuid) from public, anon, authenticated;
grant execute on function public.moody_turn_alive(uuid, uuid) to service_role;
revoke execute on function public.moody_end_turn(uuid, uuid) from public, anon, authenticated;
grant execute on function public.moody_end_turn(uuid, uuid) to service_role;
revoke execute on function public.moody_stop_turn(uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.moody_stop_turn(uuid, uuid, integer) to service_role;

-- The library's media: a private bucket, reached only with the secret key and
-- handed to a page or a model as signed links that expire. A database without
-- Supabase Storage (the migration's own checks) has no storage schema, and
-- skips this.
do $$
begin
    if exists (select 1 from information_schema.tables where table_schema = 'storage' and table_name = 'buckets') then
        insert into storage.buckets (id, name, public) values ('library', 'library', false)
        on conflict (id) do update set public = false;
    end if;
end;
$$;
