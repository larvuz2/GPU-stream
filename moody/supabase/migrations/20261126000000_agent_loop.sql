-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- The agent on the Claude Agent SDK's loop: where its conversation is kept,
-- what the person no longer wants to be asked about, and the events it writes.
--
-- A project's conversation is one session of the loop (`projects.agent_session`),
-- whose transcript the loop writes as entries, one JSON object each, in the
-- order they happen. They are kept here, in `agent_transcripts`, so the next
-- turn resumes the session on whichever machine runs it. A transcript is
-- addressed as the loop addresses it: by a project key (the turn's working
-- directory, in the loop's own spelling), the session's id, and a subpath that
-- is empty for the session's own transcript and names a subagent's otherwise.
-- Every row also carries the project it belongs to, which is what the control
-- plane filters on and what deletes a project's transcripts with it.
--
-- `agent_messages`, the conversation the control plane's own loop replayed to
-- the Messages API, is dropped: nothing reads it, its rows are in a format the
-- loop's sessions do not take, and what was said in a project is still its
-- event log (`project_events`), from which a project that has no session yet
-- starts its first one with a recap of what came before.
--
-- A tool the person approves each time (starting an engine, generating video)
-- writes an `approval` event and waits; the answer is recorded by
-- `moody_resolve_approval`, once, whoever is first: the person, or the turn
-- when it has waited long enough. "Always" is kept for that tool in
-- `projects.permissions`.
--
-- The rule of the first migration holds: only the control plane reaches these
-- tables and functions, with the service role.

alter table public.projects
    -- The loop's session that is this project's conversation; null until its first turn
    add column agent_session uuid,
    -- What the person no longer wants to be asked about: {tool: "always"}
    add column permissions jsonb not null default '{}'::jsonb check (jsonb_typeof(permissions) = 'object');

-- Every kind of event the agent writes. `screen` and `preview` were written
-- before this migration and refused by the check the table was made with.
alter table public.project_events drop constraint project_events_kind_check;
alter table public.project_events add constraint project_events_kind_check check (kind in (
    'user_message', 'text', 'thinking', 'tool_start', 'tool_end', 'ask', 'plan', 'library', 'engine', 'screen',
    'preview', 'agent', 'approval', 'approval_result', 'ui', 'usage', 'turn_end', 'error'
));

drop table public.agent_messages;

create table public.agent_transcripts (
    id bigint generated always as identity primary key,
    project_id uuid not null references public.projects (id) on delete cascade,
    project_key text not null,
    session_id text not null,
    -- Empty for the session's own transcript; `subagents/agent-<id>` for a subagent's
    subpath text not null default '',
    -- The entry's own id where it has one, by which a batch sent twice is kept once
    uuid text,
    entry jsonb not null,
    created_at timestamptz not null default now()
);

create index agent_transcripts_key on public.agent_transcripts (project_id, project_key, session_id, subpath, id);
create unique index agent_transcripts_entry on public.agent_transcripts (project_id, project_key, session_id, subpath, uuid)
    where uuid is not null;

alter table public.agent_transcripts enable row level security;

-- Appends a batch of entries to a transcript, in the order given, and returns
-- how many were written. An entry whose `uuid` the transcript already has is
-- left out, so a batch delivered twice is kept once; an entry without a
-- `uuid` is always written.
create function public.moody_append_transcript(
    p_project uuid, p_project_key text, p_session text, p_subpath text, p_entries jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    written integer;
begin
    insert into agent_transcripts (project_id, project_key, session_id, subpath, uuid, entry)
    select p_project, p_project_key, p_session, p_subpath, batch.entry ->> 'uuid', batch.entry
    from jsonb_array_elements(p_entries) with ordinality as batch (entry, place)
    order by batch.place
    on conflict (project_id, project_key, session_id, subpath, uuid) where uuid is not null do nothing;
    get diagnostics written = row_count;
    return written;
end;
$$;

-- The sessions written under a project key, each with when it was last
-- written, in milliseconds since the epoch. A subagent's transcript is not a
-- session.
create function public.moody_transcript_sessions(p_project uuid, p_project_key text)
returns table (session_id text, mtime bigint)
language sql
security definer
set search_path = public
as $$
    select t.session_id, (extract(epoch from max(t.created_at)) * 1000)::bigint
    from agent_transcripts t
    where t.project_id = p_project and t.project_key = p_project_key and t.subpath = ''
    group by t.session_id;
$$;

-- The subpaths written under a session: its subagents' transcripts.
create function public.moody_transcript_subkeys(p_project uuid, p_project_key text, p_session text)
returns table (subpath text)
language sql
security definer
set search_path = public
as $$
    select distinct t.subpath
    from agent_transcripts t
    where t.project_id = p_project and t.project_key = p_project_key and t.session_id = p_session and t.subpath <> '';
$$;

-- A turn's first event may carry the interactive card the message locks in
-- (`p_ui`: {ui_id, value}), which the control plane has checked is a card of
-- the project. Otherwise as the function it replaces.
drop function public.moody_begin_turn(uuid, uuid, text, integer);

create function public.moody_begin_turn(
    p_project uuid, p_user uuid, p_text text, p_stale_seconds integer, p_ui jsonb default null
)
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
    values (p_project, turn, 'user_message',
            jsonb_build_object('text', p_text) || case when p_ui is null then '{}'::jsonb else jsonb_build_object('ui', p_ui) end);
    return turn;
end;
$$;

-- Records the answer to an approval the agent is waiting on, and returns the
-- decision that stands: the one given, or the one recorded before it, since an
-- approval is answered once. `always` also keeps the tool in the project's
-- permissions. Refused with `no_approval` where the project has no such
-- approval.
create function public.moody_resolve_approval(p_project uuid, p_approval text, p_decision text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    asked public.project_events;
    standing text;
begin
    -- One at a time per project, or the person's answer and the turn's expiry could both be recorded
    perform 1 from projects where id = p_project for update;
    select * into asked from project_events
    where project_id = p_project and kind = 'approval' and data ->> 'approval_id' = p_approval
    order by id limit 1;
    if not found then
        raise exception 'no_approval' using errcode = 'P0001';
    end if;
    select data ->> 'decision' into standing from project_events
    where project_id = p_project and kind = 'approval_result' and data ->> 'approval_id' = p_approval
    order by id limit 1;
    if standing is not null then
        return standing;
    end if;
    insert into project_events (project_id, turn_id, kind, data)
    values (p_project, asked.turn_id, 'approval_result',
            jsonb_build_object('approval_id', p_approval, 'decision', p_decision)
            || case when asked.data ? 'agent_id' then jsonb_build_object('agent_id', asked.data -> 'agent_id') else '{}'::jsonb end);
    if p_decision = 'always' then
        update projects
        set permissions = permissions || jsonb_build_object(asked.data ->> 'tool', 'always')
        where id = p_project;
    end if;
    return p_decision;
end;
$$;

revoke execute on function public.moody_append_transcript(uuid, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.moody_append_transcript(uuid, text, text, text, jsonb) to service_role;
revoke execute on function public.moody_transcript_sessions(uuid, text) from public, anon, authenticated;
grant execute on function public.moody_transcript_sessions(uuid, text) to service_role;
revoke execute on function public.moody_transcript_subkeys(uuid, text, text) from public, anon, authenticated;
grant execute on function public.moody_transcript_subkeys(uuid, text, text) to service_role;
revoke execute on function public.moody_begin_turn(uuid, uuid, text, integer, jsonb) from public, anon, authenticated;
grant execute on function public.moody_begin_turn(uuid, uuid, text, integer, jsonb) to service_role;
revoke execute on function public.moody_resolve_approval(uuid, text, text) from public, anon, authenticated;
grant execute on function public.moody_resolve_approval(uuid, text, text) to service_role;
