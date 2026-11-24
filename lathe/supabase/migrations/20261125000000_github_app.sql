-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- GitHub is connected through a GitHub App, and Epic through a connection of
-- its own.
--
-- A GitHub App's user token expires after eight hours and comes with a refresh
-- token that lasts six months. The control plane keeps both sealed under
-- LATHE_SECRET_KEY, with when each expires, and refreshes the token before it
-- uses one about to expire. The account's numeric ID and name are kept beside
-- its login: they are the name and the GitHub-provided noreply address an
-- engine commits under when it clones the project's repository.
--
-- The rows github_connections held are the OAuth App's grants, which reached
-- every repository the account could (`repo`) and are no GitHub App's; they are
-- deleted, and each user connects GitHub again through the GitHub App.
--
-- The Epic connection is the OAuth App that reads packages (`read:packages`),
-- the one thing a GitHub App's token cannot do across GitHub: pull the user's
-- own copy of Unreal Engine from Epic's registry. Its token is sealed the same
-- way and does not expire. Only the control plane reaches either table, as the
-- first migration's rule says: row-level security is on with no policy.
--
-- A project may name the branch an Unreal engine clones (`github_branch`); null
-- is the repository's default branch.

delete from public.github_connections;

alter table public.github_connections
    add column github_id bigint,
    add column name text not null default '',
    -- The refresh token, sealed as the token is; null for a token that does not expire
    add column refresh_token_encrypted text,
    add column token_expires_at timestamptz,
    add column refresh_expires_at timestamptz;

create table public.epic_connections (
    user_id uuid primary key references public.profiles (id) on delete cascade,
    login text not null,
    -- The OAuth token, Fernet-encrypted under a key derived from LATHE_SECRET_KEY; never stored in the clear
    token_encrypted text not null,
    scope text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.epic_connections enable row level security;

alter table public.projects add column github_branch text;
