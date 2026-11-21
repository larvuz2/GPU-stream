/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Checks of the migration, on a Postgres that runs in this process (PGlite).
 *
 * The migration's functions are where credits move and sessions change state,
 * so this applies it to an empty database made to look like a Supabase
 * project (the `auth.users` table and the three roles a project has) and calls
 * every one: what a new profile gets, what is refused and by which name, how a
 * minute is charged and that a balance never goes below zero, that a payment
 * delivered twice is credited once, and that the keys a browser holds reach no
 * row and no function. `npm test` runs it; it exits non-zero on a failure.
 * @module
 */
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';

const MIGRATION = new URL('./migrations/20261121000000_lathe.sql', import.meta.url);

/** A row as a query returns it. */
type Row = Record<string, unknown>;

const db = new PGlite();
// What a Supabase project has before any migration of ours runs.
await db.exec(`
  create schema auth;
  create table auth.users (id uuid primary key, email text);
  create role anon; create role authenticated; create role service_role;
`);
await db.exec(fs.readFileSync(MIGRATION, 'utf8'));

let failures = 0;

/**
 * Records one check and prints it.
 * @param name What is being held.
 * @param ok Whether it held.
 * @param got What was there instead, printed when it did not.
 */
const check = (name: string, ok: boolean, got?: unknown): void => {
  if (!ok) failures += 1;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}${ok ? '' : ` -> ${JSON.stringify(got)}`}`);
};

/**
 * The first row of a query.
 * @param sql The statement.
 * @param params Its parameters.
 * @returns The row, which a statement that returns none leaves empty.
 */
const one = async (sql: string, params: unknown[] = []): Promise<Row> =>
  (await db.query<Row>(sql, params)).rows[0] ?? {};

/**
 * Runs a statement that is expected to be refused.
 * @param sql The statement.
 * @param params Its parameters.
 * @returns The refusal's message, or `null` where the statement went through.
 */
const refused = async (sql: string, params: unknown[] = []): Promise<string | null> => {
  try {
    await db.query(sql, params);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
};

const A = "00000000-0000-0000-0000-00000000000a", B = "00000000-0000-0000-0000-00000000000b", C = "00000000-0000-0000-0000-00000000000c";
await db.exec(`insert into auth.users values ('${A}','a@x.test'),('${B}','b@x.test'),('${C}','c@x.test')`);

let p = await one("select * from lathe_ensure_profile($1,$2,$3)", [A, "a@x.test", 60]);
check("a new profile gets its sign-up credits", p.credits === 60 && p.max_sessions === 1, p);
p = await one("select * from lathe_ensure_profile($1,$2,$3)", [A, "a@x.test", 60]);
check("asking again grants nothing more", p.credits === 60, p);
check("one ledger row for the sign-up", (await one("select count(*)::int n from credit_ledger where user_id=$1", [A])).n === 1);
await one("select * from lathe_ensure_profile($1,$2,$3)", [B, "b@x.test", 60]);
await one("select * from lathe_ensure_profile($1,$2,$3)", [C, "c@x.test", 0]);

check("no credits, no session", (await refused("select * from lathe_request_session($1,'blender','cpu','auto',1,2)", [C])) === "insufficient_credits");
check("no profile, no session", (await refused("select * from lathe_request_session($1,'blender','cpu','auto',1,2)", ["00000000-0000-0000-0000-0000000000ff"])) === "no_profile");

const s1 = await one("select * from lathe_request_session($1,'blender','cpu','auto',1,1)", [A]);
check("the first session starts, and says when it was claimed", s1.status === "starting" && s1.claimed_at !== null, s1);
check("a second for the same user is refused", (await refused("select * from lathe_request_session($1,'blender','cpu','auto',1,1)", [A])) === "session_limit");
const s2 = await one("select * from lathe_request_session($1,'blender','t4','eu',3,1)", [B]);
check("past capacity, another user's session queues unclaimed", s2.status === "queued" && s2.claimed_at === null, s2);
check("its queue position is 1", (await one("select lathe_queue_position($1) n", [s2.id])).n === 1);
check("a session that is not queued has no position", (await one("select lathe_queue_position($1) n", [s1.id])).n === 0);
check("nothing is claimed while capacity is full", (await db.query("select * from lathe_claim_queued(1)")).rows.length === 0);

const started = await one("select * from lathe_session_started($1,'sb-1')", [s1.id]);
check("a started session runs", started.status === "running" && started.sandbox_id === "sb-1" && started.charged_until !== null, started);
check("starting it twice changes nothing", (await one("select * from lathe_session_started($1,'sb-2')", [s1.id])).id === null);

check("under a minute, nothing is charged", (await one("select lathe_charge_session($1,false) n", [s1.id])).n === 60);
await db.exec(`update sessions set charged_until = now() - interval '3 minutes 30 seconds' where id='${s1.id}'`);
check("three whole minutes are charged", (await one("select lathe_charge_session($1,false) n", [s1.id])).n === 57);
check("charging again at once charges nothing", (await one("select lathe_charge_session($1,false) n", [s1.id])).n === 57);
const ended = await one("select * from lathe_end_session($1,'idle',false)", [s1.id]);
check("ending charges the minute in progress", ended.status === "ended" && ended.credits_used === 4 && ended.end_reason === "idle", ended);
check("the user has 56 left", (await one("select credits from profiles where id=$1", [A])).credits === 56);
check("ending twice changes nothing", (await one("select * from lathe_end_session($1,'again',false)", [s1.id])).end_reason === "idle");
check("usage is in the ledger", (await one("select sum(delta)::int n from credit_ledger where user_id=$1 and reason='usage'", [A])).n === -4);

const claimed = (await db.query<Row>("select * from lathe_claim_queued(1)")).rows;
const first = claimed[0] ?? {};
check("room again: the queued session is claimed", claimed.length === 1 && first.id === s2.id && first.status === "starting" && first.claimed_at !== null, claimed);
const failed = await one("select * from lathe_end_session($1,'start_failed',true)", [s2.id]);
check("a session that never ran fails uncharged", failed.status === "failed" && failed.credits_used === 0, failed);

// A user who runs out: charged to zero and no further.
await db.exec(`update profiles set credits = 5 where id='${B}'`);
const s3 = await one("select * from lathe_request_session($1,'blender','t4','auto',3,5)", [B]);
await one("select * from lathe_session_started($1,'sb-3')", [s3.id]);
await db.exec(`update sessions set charged_until = now() - interval '10 minutes' where id='${s3.id}'`);
check("charged to zero, never below", (await one("select lathe_charge_session($1,false) n", [s3.id])).n === 0);
check("only what was there was taken", (await one("select credits_used from sessions where id=$1", [s3.id])).credits_used === 5);
await one("select * from lathe_end_session($1,'out_of_credits',false)", [s3.id]);

check("a purchase adds credits", (await one("select lathe_add_credits($1,1000,'purchase','cs_1') n", [B])).n === 1000);
check("the same payment again adds nothing", (await one("select lathe_add_credits($1,1000,'purchase','cs_1') n", [B])).n === 1000);

await db.exec(`insert into api_keys (user_id,name,prefix,key_hash) values ('${A}','laptop','lathe_ab','h1'),('${A}','old','lathe_cd','h2')`);
await db.exec(`update api_keys set revoked_at = now() where key_hash='h2'`);
check("a key names its user", (await one("select lathe_use_api_key('h1') u")).u === A);
check("and is marked used", (await one("select last_used_at from api_keys where key_hash='h1'")).last_used_at !== null);
check("a revoked key names nobody", (await one("select lathe_use_api_key('h2') u")).u === null);
check("an unknown key names nobody", (await one("select lathe_use_api_key('nope') u")).u === null);

// What a browser's keys can reach: nothing.
for (const role of ["anon", "authenticated"]) {
  await db.exec(`grant usage on schema public to ${role}; grant select, insert, update, delete on all tables in schema public to ${role}; set role ${role}`);
  check(`${role} sees no profile rows`, (await one("select count(*)::int n from profiles")).n === 0);
  check(`${role} sees no session rows`, (await one("select count(*)::int n from sessions")).n === 0);
  check(`${role} sees no api key rows`, (await one("select count(*)::int n from api_keys")).n === 0);
  check(`${role} cannot grant itself credits`, /permission denied/.test(await refused("select lathe_add_credits($1,999,'grant',null)", [A]) ?? ""));
  check(`${role} cannot insert a profile`, /row-level security/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "") || /duplicate/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "x") === false);
  await db.exec("reset role");
}
await db.exec("set role service_role");
check("the service role may call the functions", (await refused("select lathe_queue_position($1)", [s1.id])) === null);
await db.exec("reset role");

console.log(failures === 0 ? "\nall checks passed" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
