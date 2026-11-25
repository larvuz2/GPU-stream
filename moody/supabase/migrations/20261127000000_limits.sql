-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.

-- What one turn of the agent may cost is the person's own setting.
--
-- A turn stops when it has spent a number of dollars on the model, or taken a
-- number of steps. Both are settings of the account: the person who pays for
-- the work decides how far a turn may run before it comes back to them. Null
-- is an account that has not set one, which runs on the deployment's default;
-- the control plane also holds the ceiling no account's setting goes above,
-- so neither number is written here.
--
-- `moody_ensure_profile` returns the whole row, these columns with it. The
-- rule of the first migration holds: only the control plane reads or writes
-- the table, with the service role.

alter table public.profiles
    -- What one turn may spend on the model, in dollars as the agent's loop prices it
    add column turn_budget_usd numeric check (turn_budget_usd > 0),
    -- The most steps one turn may take
    add column turn_limit integer check (turn_limit > 0);
