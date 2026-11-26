-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- A person's name, and the settings they changed.
--
-- The app's Settings hold what is the person's to choose. What a setting is
-- (its label, its kind, what it may be, its default) is the catalog's
-- (`catalog.json`, `settings`), so that adding one is an entry there. Here is
-- only what a person changed, by the setting's id: an account that changed
-- nothing has an empty object and runs on every default, and a default the
-- catalog changes reaches everyone who did not choose otherwise. The control
-- plane checks an id and a value against the catalog before it writes one, so
-- the column is checked for nothing but being an object.
--
-- `moody_ensure_profile` returns the whole row, these columns with it. The
-- rule of the first migration holds: only the control plane reads or writes
-- the table, with the service role.

alter table public.profiles
    -- What the person is called, where they said; the app shows the email otherwise
    add column name text not null default '',
    -- What the person changed of the catalog's settings: {id: value}
    add column settings jsonb not null default '{}'::jsonb check (jsonb_typeof(settings) = 'object');
