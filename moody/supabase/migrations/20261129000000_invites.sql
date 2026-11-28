-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- Who is invited, while a deployment is open by invitation.
--
-- A deployment that sets `MOODY_INVITE_ONLY` serves an account only while its
-- address is in `invites`: the control plane asks `moody_invited` before it
-- answers anything, so adding a row lets a person in and deleting it keeps
-- them out, with their projects left as they were. A deployment open to
-- everyone never asks, and the table stays empty.
--
-- The list is kept here and not in the deployment's settings because it is
-- what changes: an address is added in the table editor, or by whoever
-- operates the project, without a deploy. An address is kept in lowercase,
-- which is how it is compared, and it is the one the person signs in with:
-- the auth server's word for whose it is, which holds only while the project
-- makes a sign-up prove its address ("Confirm email", which is on unless
-- turned off).
--
-- An invite may also say how many credits its account starts with, where not
-- the sign-up credits everyone gets: a tester is given enough to try the
-- engines without the number a public sign-up gets changing. It is read once,
-- when the profile is made; changing it later moves no balance.
--
-- The rule of the first migration holds: only the control plane reads the
-- table, with the service role.

create table public.invites (
    -- The address the person signs in with, in lowercase
    email text primary key check (email = lower(email) and email <> ''),
    -- The credits the account starts with, where not the sign-up credits of the catalog
    credits integer check (credits >= 0),
    -- Who this is, for whoever keeps the list
    note text not null default '',
    created_at timestamptz not null default now()
);

alter table public.invites enable row level security;

-- Whether an account is on the list: by the address its credential names, or,
-- for an API key, which names none, by the address of its profile.
create function public.moody_invited(p_user uuid, p_email text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1 from invites
        where email = lower(coalesce(nullif(p_email, ''), (select email from profiles where id = p_user), ''))
    );
$$;

-- The profile of a user, made the first time it is asked for with the credits
-- of its invite where that names some, and with the sign-up credits otherwise.
create or replace function public.moody_ensure_profile(p_user uuid, p_email text, p_signup_credits integer)
returns public.profiles
language plpgsql
security definer
set search_path = public
as $$
declare
    profile public.profiles;
    granted integer;
begin
    select coalesce(
        (select credits from invites where email = lower(coalesce(p_email, ''))), p_signup_credits
    ) into granted;
    insert into profiles (id, email, credits)
    values (p_user, coalesce(p_email, ''), granted)
    on conflict (id) do nothing
    returning * into profile;
    if found then
        if granted > 0 then
            insert into credit_ledger (user_id, delta, reason) values (p_user, granted, 'signup');
        end if;
        return profile;
    end if;
    select * into profile from profiles where id = p_user;
    return profile;
end;
$$;

revoke execute on function public.moody_invited(uuid, text) from public, anon, authenticated;
grant execute on function public.moody_invited(uuid, text) to service_role;
