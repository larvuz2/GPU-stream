/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Checks of the migrations, on a Postgres that runs in this process (PGlite).
 *
 * The migrations' functions are where credits move, sessions change state, and
 * a project's agent turn is claimed and released, so this applies every
 * migration in order to an empty database made to look like a Supabase project
 * (the `auth.users` table, the three roles a project has, and Storage's bucket
 * table) and calls every function: what a new profile gets, what is refused and
 * by which name, how a minute is charged and that a balance never goes below
 * zero, that a payment delivered twice is credited once, that an engine starts
 * only in its user's project and a seat-capped app stops at its seats, that a
 * project runs one turn at a time and a dead turn does not hold it, and that
 * the keys a browser holds reach no row and no function. The migrations also
 * apply to a database with no Storage at all, as the first did, and moving to
 * the GitHub App drops the OAuth App's grants a database already held. `npm
 * test` runs it; it exits non-zero on a failure.
 * @module
 */
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';

const MIGRATIONS = new URL('./migrations/', import.meta.url);
/** Every migration's SQL, in the order Supabase applies them: by file name. */
const migrations = fs.readdirSync(MIGRATIONS).filter((name) => name.endsWith('.sql')).sort()
  .map((name) => fs.readFileSync(new URL(name, MIGRATIONS), 'utf8'));

/** A row as a query returns it. */
type Row = Record<string, unknown>;

// What a Supabase project has before any migration of ours runs.
const SUPABASE = `
  create schema auth;
  create table auth.users (id uuid primary key, email text);
  create role anon; create role authenticated; create role service_role;
`;
const db = new PGlite();
await db.exec(SUPABASE);
await db.exec("create schema storage; create table storage.buckets (id text primary key, name text not null, public boolean default false)");
for (const sql of migrations) await db.exec(sql);

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

let p = await one("select * from moody_ensure_profile($1,$2,$3)", [A, "a@x.test", 60]);
check("a new profile gets its sign-up credits", p.credits === 60 && p.max_sessions === 1, p);
p = await one("select * from moody_ensure_profile($1,$2,$3)", [A, "a@x.test", 60]);
check("asking again grants nothing more", p.credits === 60, p);
check("one ledger row for the sign-up", (await one("select count(*)::int n from credit_ledger where user_id=$1", [A])).n === 1);
await one("select * from moody_ensure_profile($1,$2,$3)", [B, "b@x.test", 60]);
await one("select * from moody_ensure_profile($1,$2,$3)", [C, "c@x.test", 0]);

check("no credits, no session", (await refused("select * from moody_request_session($1,'blender','cpu','auto',1,2)", [C])) === "insufficient_credits");
check("no profile, no session", (await refused("select * from moody_request_session($1,'blender','cpu','auto',1,2)", ["00000000-0000-0000-0000-0000000000ff"])) === "no_profile");

const s1 = await one("select * from moody_request_session($1,'blender','cpu','auto',1,1)", [A]);
check("the first session starts, and says when it was claimed", s1.status === "starting" && s1.claimed_at !== null, s1);
check("a second for the same user is refused", (await refused("select * from moody_request_session($1,'blender','cpu','auto',1,1)", [A])) === "session_limit");
const s2 = await one("select * from moody_request_session($1,'blender','t4','eu',3,1)", [B]);
check("past capacity, another user's session queues unclaimed", s2.status === "queued" && s2.claimed_at === null, s2);
check("its queue position is 1", (await one("select moody_queue_position($1) n", [s2.id])).n === 1);
check("a session that is not queued has no position", (await one("select moody_queue_position($1) n", [s1.id])).n === 0);
check("nothing is claimed while capacity is full", (await db.query("select * from moody_claim_queued(1)")).rows.length === 0);

const started = await one("select * from moody_session_started($1,'sb-1')", [s1.id]);
check("a started session runs", started.status === "running" && started.sandbox_id === "sb-1" && started.charged_until !== null, started);
check("starting it twice changes nothing", (await one("select * from moody_session_started($1,'sb-2')", [s1.id])).id === null);

check("under a minute, nothing is charged", (await one("select moody_charge_session($1,false) n", [s1.id])).n === 60);
await db.exec(`update sessions set charged_until = now() - interval '3 minutes 30 seconds' where id='${s1.id}'`);
check("three whole minutes are charged", (await one("select moody_charge_session($1,false) n", [s1.id])).n === 57);
check("charging again at once charges nothing", (await one("select moody_charge_session($1,false) n", [s1.id])).n === 57);
const ended = await one("select * from moody_end_session($1,'idle',false)", [s1.id]);
check("ending charges the minute in progress", ended.status === "ended" && ended.credits_used === 4 && ended.end_reason === "idle", ended);
check("the user has 56 left", (await one("select credits from profiles where id=$1", [A])).credits === 56);
check("ending twice changes nothing", (await one("select * from moody_end_session($1,'again',false)", [s1.id])).end_reason === "idle");
check("usage is in the ledger", (await one("select sum(delta)::int n from credit_ledger where user_id=$1 and reason='usage'", [A])).n === -4);

const claimed = (await db.query<Row>("select * from moody_claim_queued(1)")).rows;
const first = claimed[0] ?? {};
check("room again: the queued session is claimed", claimed.length === 1 && first.id === s2.id && first.status === "starting" && first.claimed_at !== null, claimed);
const failed = await one("select * from moody_end_session($1,'start_failed',true)", [s2.id]);
check("a session that never ran fails uncharged", failed.status === "failed" && failed.credits_used === 0, failed);

// A user who runs out: charged to zero and no further.
await db.exec(`update profiles set credits = 5 where id='${B}'`);
const s3 = await one("select * from moody_request_session($1,'blender','t4','auto',3,5)", [B]);
await one("select * from moody_session_started($1,'sb-3')", [s3.id]);
await db.exec(`update sessions set charged_until = now() - interval '10 minutes' where id='${s3.id}'`);
check("charged to zero, never below", (await one("select moody_charge_session($1,false) n", [s3.id])).n === 0);
check("only what was there was taken", (await one("select credits_used from sessions where id=$1", [s3.id])).credits_used === 5);
await one("select * from moody_end_session($1,'out_of_credits',false)", [s3.id]);

check("a purchase adds credits", (await one("select moody_add_credits($1,1000,'purchase','cs_1') n", [B])).n === 1000);
check("the same payment again adds nothing", (await one("select moody_add_credits($1,1000,'purchase','cs_1') n", [B])).n === 1000);

await db.exec(`insert into api_keys (user_id,name,prefix,key_hash) values ('${A}','laptop','moody_ab','h1'),('${A}','old','moody_cd','h2')`);
await db.exec(`update api_keys set revoked_at = now() where key_hash='h2'`);
check("a key names its user", (await one("select moody_use_api_key('h1') u")).u === A);
check("and is marked used", (await one("select last_used_at from api_keys where key_hash='h1'")).last_used_at !== null);
check("a revoked key names nobody", (await one("select moody_use_api_key('h2') u")).u === null);
check("an unknown key names nobody", (await one("select moody_use_api_key('nope') u")).u === null);

// Projects, and the engines started in them.
const pa = await one(`insert into projects (user_id,name,discipline,format,library_sections) values ($1,'Mara','media','Movie','["Characters"]') returning *`, [A]);
const pb = await one("insert into projects (user_id,name,discipline) values ($1,'Other','music') returning *", [B]);
check("a project starts with an empty plan and no turn", JSON.stringify(pa.plan) === "[]" && pa.turn_id === null && pa.pinned === false, pa);
check("an engine in another user's project is refused", (await refused("select * from moody_request_session($1,'filmcraft','cpu','auto',1,5,$2)", [A, pb.id])) === "no_project");
const e1 = await one("select * from moody_request_session($1,'filmcraft','cpu','auto',1,5,$2)", [A, pa.id]);
check("an engine in the user's own project records it", e1.project_id === pa.id && e1.status === "starting", e1);
await one("select * from moody_end_session($1,'stopped',false)", [e1.id]);

// An app licensed per seat: no more open at once than its seats, across users.
const n1 = await one("select * from moody_request_session($1,'nuke','cpu','auto',1,5,null,1)", [A]);
check("a seat-capped app takes its seat", n1.status === "starting", n1);
check("past its seats the next is refused, whoever asks", (await refused("select * from moody_request_session($1,'nuke','cpu','auto',1,5,null,1)", [B])) === "no_seats");
const other = await one("select * from moody_request_session($1,'blender','cpu','auto',1,5,null,null)", [B]);
check("another app is not held by those seats", other.status === "starting", other);
await one("select * from moody_end_session($1,'stopped',false)", [n1.id]);
await one("select * from moody_end_session($1,'stopped',false)", [other.id]);
check("a freed seat can be taken again", (await refused("select * from moody_request_session($1,'nuke','cpu','auto',1,5,null,1)", [B])) === null);
await db.exec("update sessions set status = 'ended' where status in ('queued','starting','running')");

// One agent turn at a time per project.
/**
 * The events of one turn, in order.
 * @param turn The turn's ID.
 * @returns Each event's kind and data.
 */
const turnEvents = async (turn: unknown): Promise<Row[]> =>
  (await db.query<Row>("select kind, data from project_events where turn_id=$1 order by id", [turn])).rows;
const t1 = (await one("select moody_begin_turn($1,$2,'hello',120) t", [pa.id, A])).t;
const opening = (await turnEvents(t1))[0] ?? {};
check("a turn starts with its message as its first event", opening.kind === "user_message" && (opening.data as Row).text === "hello", opening);
check("a second turn while one is alive is refused", (await refused("select moody_begin_turn($1,$2,'again',120)", [pa.id, A])) === "turn_running");
check("another user cannot start a turn on the project", (await refused("select moody_begin_turn($1,$2,'mine',120)", [pa.id, B])) === "no_project");
check("the running turn is alive", (await one("select moody_turn_alive($1,$2) ok", [pa.id, t1])).ok === true);
check("another user cannot stop it", (await one("select moody_stop_turn($1,$2,120) ok", [pa.id, B])).ok === false);
check("its user can", (await one("select moody_stop_turn($1,$2,120) ok", [pa.id, A])).ok === true);
check("a turn asked to stop is told so at its heartbeat", (await one("select moody_turn_alive($1,$2) ok", [pa.id, t1])).ok === false);
check("ending it frees the project", (await one("select moody_end_turn($1,$2) ok", [pa.id, t1])).ok === true
  && (await one("select turn_id from projects where id=$1", [pa.id])).turn_id === null);
check("ending it again writes nothing", (await one("select moody_end_turn($1,$2) ok", [pa.id, t1])).ok === false
  && (await turnEvents(t1)).map((e) => e.kind).join() === "user_message,turn_end");
const t2 = (await one("select moody_begin_turn($1,$2,'second',120) t", [pa.id, A])).t;
await db.exec(`update projects set turn_seen_at = now() - interval '10 minutes' where id='${pa.id}'`);
const t3 = (await one("select moody_begin_turn($1,$2,'third',120) t", [pa.id, A])).t;
check("a turn whose worker died is closed by the next message", t3 !== t2 && (await turnEvents(t2)).map((e) => e.kind).join() === "user_message,error,turn_end");
check("and is no longer alive", (await one("select moody_turn_alive($1,$2) ok", [pa.id, t2])).ok === false);
await db.exec(`update projects set turn_seen_at = now() - interval '10 minutes' where id='${pa.id}'`);
check("stopping a dead turn ends it at once", (await one("select moody_stop_turn($1,$2,120) ok", [pa.id, A])).ok === true
  && (await one("select turn_id from projects where id=$1", [pa.id])).turn_id === null
  && (await turnEvents(t3)).map((e) => e.kind).join() === "user_message,turn_end");
check("with no turn running there is nothing to stop", (await one("select moody_stop_turn($1,$2,120) ok", [pa.id, A])).ok === false);

// The library, the conversation, and the GitHub connection, and what deleting a project takes with it.
await db.exec(`insert into assets (project_id,section,name,tag) values ('${pa.id}','Characters','Mara','@mara')`);
check("a tag names one entry of a project", /duplicate key/.test(await refused(`insert into assets (project_id,section,name,tag) values ('${pa.id}','Props','Mara again','@mara')`) ?? ""));
check("the same tag in another project is its own", (await refused(`insert into assets (project_id,section,name,tag) values ('${pb.id}','Songs','Mara','@mara')`)) === null);
check("untagged entries do not collide", (await refused(`insert into assets (project_id,section,name) values ('${pa.id}','Props','Cup'),('${pa.id}','Props','Plate')`)) === null);
await db.exec(`insert into agent_messages (project_id,role,content) values ('${pa.id}','user','"hello"')`);
await db.exec(`insert into github_connections (user_id,login,token_encrypted,refresh_token_encrypted,token_expires_at,github_id,name)
  values ('${A}','mara-films','gAAAA-sealed','gAAAA-refresh',now() + interval '8 hours',1001,'Mara')`);
await db.exec(`insert into epic_connections (user_id,login,token_encrypted,scope) values ('${A}','mara-films','gAAAA-epic','read:packages')`);
check("a project names no branch until it chooses one", (await one("select github_branch from projects where id=$1", [pa.id])).github_branch === null);
check("one Epic connection per user", /duplicate key/.test(await refused(`insert into epic_connections (user_id,login,token_encrypted) values ('${A}','x','y')`) ?? ""));
const pc = await one("insert into projects (user_id,name,discipline) values ($1,'Gone','media') returning *", [A]);
const ec = await one("select * from moody_request_session($1,'blender','cpu','auto',1,5,$2)", [A, pc.id]);
await db.exec(`insert into assets (project_id,section,name) values ('${pc.id}','Props','Hat'); insert into agent_messages (project_id,role,content) values ('${pc.id}','user','"bye"')`);
await one("select moody_begin_turn($1,$2,'bye',120)", [pc.id, A]);
await db.exec(`delete from projects where id='${pc.id}'`);
check("deleting a project deletes its library, events, and conversation", (await one(
  "select ((select count(*) from assets where project_id=$1) + (select count(*) from project_events where project_id=$1) + (select count(*) from agent_messages where project_id=$1))::int n",
  [pc.id])).n === 0);
check("and keeps its engines' sessions, unlinked", (await one("select project_id from sessions where id=$1", [ec.id])).project_id === null);
await one("select * from moody_end_session($1,'stopped',false)", [ec.id]);

const bucket = await one("select * from storage.buckets where id='library'");
check("the library bucket exists and is private", bucket.public === false, bucket);
const upgraded = new PGlite();
await upgraded.exec(SUPABASE);
for (const sql of migrations.slice(0, -1)) await upgraded.exec(sql);
await upgraded.exec(`insert into auth.users values ('${A}','a@x.test'); select moody_ensure_profile('${A}','a@x.test',60)`);
await upgraded.exec(`insert into github_connections (user_id,login,token_encrypted,scope) values ('${A}','mara-films','gAAAA-oauth','repo,read:packages')`);
await upgraded.exec(migrations[migrations.length - 1] ?? "");
check("moving to the GitHub App drops the OAuth App's grants", ((await upgraded.query<Row>("select count(*)::int n from github_connections")).rows[0] ?? {}).n === 0);
const bare = new PGlite();
await bare.exec(SUPABASE);
check("the migrations apply where there is no Storage", await (async () => {
  try {
    for (const sql of migrations) await bare.exec(sql);
    return true;
  } catch {
    return false;
  }
})());

// What a browser's keys can reach: nothing.
for (const role of ["anon", "authenticated"]) {
  await db.exec(`grant usage on schema public to ${role}; grant select, insert, update, delete on all tables in schema public to ${role}; set role ${role}`);
  check(`${role} sees no profile rows`, (await one("select count(*)::int n from profiles")).n === 0);
  check(`${role} sees no session rows`, (await one("select count(*)::int n from sessions")).n === 0);
  check(`${role} sees no api key rows`, (await one("select count(*)::int n from api_keys")).n === 0);
  for (const table of ["projects", "assets", "project_events", "agent_messages", "github_connections", "epic_connections"]) {
    check(`${role} sees no ${table} rows`, (await one(`select count(*)::int n from ${table}`)).n === 0);
  }
  check(`${role} cannot start a turn`, /permission denied/.test(await refused("select moody_begin_turn($1,$2,'x',120)", [pa.id, A]) ?? ""));
  check(`${role} cannot start an engine`, /permission denied/.test(await refused("select * from moody_request_session($1,'blender','cpu','auto',1,5,$2)", [A, pa.id]) ?? ""));
  check(`${role} cannot grant itself credits`, /permission denied/.test(await refused("select moody_add_credits($1,999,'grant',null)", [A]) ?? ""));
  check(`${role} cannot insert a profile`, /row-level security/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "") || /duplicate/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "x") === false);
  await db.exec("reset role");
}
await db.exec("set role service_role");
check("the service role may call the functions", (await refused("select moody_queue_position($1)", [s1.id])) === null
  && (await refused("select moody_turn_alive($1,$2)", [pa.id, A])) === null);
await db.exec("reset role");

console.log(failures === 0 ? "\nall checks passed" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
