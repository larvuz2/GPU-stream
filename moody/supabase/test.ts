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
 * project runs one turn at a time and a dead turn does not hold it, that the
 * agent's transcript is kept in the order written with a batch sent twice kept
 * once, that an approval is answered once and "always" is remembered, that an
 * account's limits of a turn are unset until it sets them and are never zero,
 * and that the keys a browser holds reach no row and no function. The migrations also
 * apply to a database with no Storage at all, as the first did, moving to the
 * GitHub App drops the OAuth App's grants a database already held, and moving
 * to the agent's loop keeps a project's events while its replayed conversation
 * goes. `npm test` runs it; it exits non-zero on a failure.
 * @module
 */
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';

const MIGRATIONS = new URL('./migrations/', import.meta.url);
/** Every migration's file name, in the order Supabase applies them. */
const names = fs.readdirSync(MIGRATIONS).filter((name) => name.endsWith('.sql')).sort();
/** Every migration's SQL, in that order. */
const migrations = names.map((name) => fs.readFileSync(new URL(name, MIGRATIONS), 'utf8'));

/**
 * Where a migration stands in the order, by the name after its timestamp.
 * @param name The migration's name, as `github_app`.
 * @returns Its index in `migrations`.
 * @throws Where no migration has the name: a check of an upgrade would otherwise test nothing.
 */
const migration = (name: string): number => {
  const index = names.findIndex((file) => file.endsWith(`_${name}.sql`));
  if (index < 0) throw new Error(`no migration is named ${name}`);
  return index;
};

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
check("a profile has set no limit of a turn, which is the deployment's default", p.turn_budget_usd === null && p.turn_limit === null, p);
await db.exec(`update profiles set turn_budget_usd = 40.5, turn_limit = 350 where id='${A}'`);
p = await one("select * from moody_ensure_profile($1,$2,$3)", [A, "a@x.test", 60]);
check("its own limits come back with it", Number(p.turn_budget_usd) === 40.5 && p.turn_limit === 350, p);
check("a limit is never zero or less", /check/.test(await refused(`update profiles set turn_budget_usd = 0 where id='${A}'`) ?? "")
  && /check/.test(await refused(`update profiles set turn_limit = -1 where id='${A}'`) ?? ""));
await db.exec(`update profiles set turn_budget_usd = null, turn_limit = null where id='${A}'`);
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
const pa = await one(`insert into projects (user_id,name,discipline,format,library_sections) values ($1,'Mara','media','Film & TV','["Characters"]') returning *`, [A]);
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
const t4 = (await one("select moody_begin_turn($1,$2,'this one',120,$3) t", [pa.id, A, { ui_id: "card-1", value: { pick: 2 } }])).t;
const locked = ((await turnEvents(t4))[0] ?? {}).data as Row;
check("a turn's message keeps the card it locks in", locked.text === "this one" && JSON.stringify(locked.ui) === '{"ui_id":"card-1","value":{"pick":2}}', locked);
check("every kind of event the agent writes is taken", (await refused(
  `insert into project_events (project_id,turn_id,kind) select '${pa.id}','${String(t4)}',kind from unnest(array[
    'thinking','screen','preview','agent','ui','usage']) kind`)) === null);
check("a kind nothing writes is refused", /project_events_kind_check/.test(await refused(
  `insert into project_events (project_id,turn_id,kind) values ('${pa.id}','${String(t4)}','note')`) ?? ""));

// An approval: answered once, whoever is first, and "always" is remembered for its tool.
await db.exec(`insert into project_events (project_id,turn_id,kind,data) values
  ('${pa.id}','${String(t4)}','approval','{"approval_id":"ap-1","tool":"engine_start","agent_id":"sub-1"}'),
  ('${pa.id}','${String(t4)}','approval','{"approval_id":"ap-2","tool":"generate_video"}')`);
check("a project starts with nothing approved for good", JSON.stringify((await one("select permissions from projects where id=$1", [pa.id])).permissions) === "{}");
check("an approval the project does not have is refused", (await refused("select moody_resolve_approval($1,'nope','once')", [pa.id])) === "no_approval"
  && (await refused("select moody_resolve_approval($1,'ap-1','once')", [pb.id])) === "no_approval");
check("an answer is recorded", (await one("select moody_resolve_approval($1,'ap-1','once') d", [pa.id])).d === "once");
check("a second answer changes nothing and is told the first", (await one("select moody_resolve_approval($1,'ap-1','always') d", [pa.id])).d === "once"
  && JSON.stringify((await one("select permissions from projects where id=$1", [pa.id])).permissions) === "{}");
const answered = (await turnEvents(t4)).filter((e) => e.kind === "approval_result").map((e) => e.data as Row);
check("as one event, in the turn that asked, marked as its subagent's", answered.length === 1
  && answered[0]?.approval_id === "ap-1" && answered[0]?.decision === "once" && answered[0]?.agent_id === "sub-1", answered);
check("always is kept for the tool", (await one("select moody_resolve_approval($1,'ap-2','always') d", [pa.id])).d === "always"
  && JSON.stringify((await one("select permissions from projects where id=$1", [pa.id])).permissions) === '{"generate_video":"always"}');
check("permissions are an object", /check/.test(await refused(`update projects set permissions='[]' where id='${pa.id}'`) ?? ""));
await one("select moody_end_turn($1,$2)", [pa.id, t4]);

// The agent's transcript: entries in the order written, a batch sent twice kept once.
/**
 * A transcript's entries, in order.
 * @param key The project key it was written under.
 * @param subpath Empty for the session's own transcript, a subagent's path otherwise.
 * @returns Each entry's `n`.
 */
const transcript = async (key: string, subpath = ""): Promise<unknown[]> =>
  (await db.query<Row>("select entry from agent_transcripts where project_id=$1 and project_key=$2 and session_id='s-1' and subpath=$3 order by id",
    [pa.id, key, subpath])).rows.map((row) => (row.entry as Row).n);
const batch = [{ uuid: "u-1", n: 1 }, { uuid: "u-2", n: 2 }, { n: 3 }];
check("a batch is written whole", (await one("select moody_append_transcript($1,'-work','s-1','',$2) n", [pa.id, batch])).n === 3);
check("sent again, only its entries without an id are written", (await one("select moody_append_transcript($1,'-work','s-1','',$2) n", [pa.id, batch])).n === 1);
await one("select moody_append_transcript($1,'-work','s-1','',$2)", [pa.id, [{ uuid: "u-4", n: 4 }]]);
check("in the order written", (await transcript("-work")).join() === "1,2,3,3,4", await transcript("-work"));
await one("select moody_append_transcript($1,'-work','s-1','subagents/agent-7',$2)", [pa.id, [{ uuid: "u-1", n: 7 }]]);
await one("select moody_append_transcript($1,'-other','s-1','',$2)", [pa.id, [{ uuid: "u-1", n: 9 }]]);
check("a subagent's transcript and another key's are their own", (await transcript("-work", "subagents/agent-7")).join() === "7"
  && (await transcript("-other")).join() === "9" && (await transcript("-work")).length === 5);
const listed = (await db.query<Row>("select * from moody_transcript_sessions($1,'-work')", [pa.id])).rows;
check("a key lists its sessions and when each was written", listed.length === 1 && listed[0]?.session_id === "s-1" && Number(listed[0]?.mtime) > 1e12, listed);
const under = (await db.query<Row>("select * from moody_transcript_subkeys($1,'-work','s-1')", [pa.id])).rows;
check("a session lists its subagents' transcripts", under.length === 1 && under[0]?.subpath === "subagents/agent-7", under);
check("another project sees none of it", (await db.query("select * from moody_transcript_sessions($1,'-work')", [pb.id])).rows.length === 0);

// The library, the transcript, and the GitHub connection, and what deleting a project takes with it.
await db.exec(`insert into assets (project_id,section,name,tag) values ('${pa.id}','Characters','Mara','@mara')`);
check("a tag names one entry of a project", /duplicate key/.test(await refused(`insert into assets (project_id,section,name,tag) values ('${pa.id}','Props','Mara again','@mara')`) ?? ""));
check("the same tag in another project is its own", (await refused(`insert into assets (project_id,section,name,tag) values ('${pb.id}','Songs','Mara','@mara')`)) === null);
check("untagged entries do not collide", (await refused(`insert into assets (project_id,section,name) values ('${pa.id}','Props','Cup'),('${pa.id}','Props','Plate')`)) === null);
await db.exec(`insert into github_connections (user_id,login,token_encrypted,refresh_token_encrypted,token_expires_at,github_id,name)
  values ('${A}','mara-films','gAAAA-sealed','gAAAA-refresh',now() + interval '8 hours',1001,'Mara')`);
await db.exec(`insert into epic_connections (user_id,login,token_encrypted,scope) values ('${A}','mara-films','gAAAA-epic','read:packages')`);
check("a project names no branch until it chooses one", (await one("select github_branch from projects where id=$1", [pa.id])).github_branch === null);
check("one Epic connection per user", /duplicate key/.test(await refused(`insert into epic_connections (user_id,login,token_encrypted) values ('${A}','x','y')`) ?? ""));
const pc = await one("insert into projects (user_id,name,discipline) values ($1,'Gone','media') returning *", [A]);
const ec = await one("select * from moody_request_session($1,'blender','cpu','auto',1,5,$2)", [A, pc.id]);
await db.exec(`insert into assets (project_id,section,name) values ('${pc.id}','Props','Hat')`);
await one("select moody_append_transcript($1,'-work','s-2','',$2)", [pc.id, [{ uuid: "u-1", n: 1 }]]);
await one("select moody_begin_turn($1,$2,'bye',120)", [pc.id, A]);
await db.exec(`delete from projects where id='${pc.id}'`);
check("deleting a project deletes its library, events, and transcript", (await one(
  "select ((select count(*) from assets where project_id=$1) + (select count(*) from project_events where project_id=$1) + (select count(*) from agent_transcripts where project_id=$1))::int n",
  [pc.id])).n === 0);
check("and keeps its engines' sessions, unlinked", (await one("select project_id from sessions where id=$1", [ec.id])).project_id === null);
await one("select * from moody_end_session($1,'stopped',false)", [ec.id]);

const bucket = await one("select * from storage.buckets where id='library'");
check("the library bucket exists and is private", bucket.public === false, bucket);
const upgraded = new PGlite();
await upgraded.exec(SUPABASE);
for (const sql of migrations.slice(0, migration("github_app"))) await upgraded.exec(sql);
await upgraded.exec(`insert into auth.users values ('${A}','a@x.test'); select moody_ensure_profile('${A}','a@x.test',60)`);
await upgraded.exec(`insert into github_connections (user_id,login,token_encrypted,scope) values ('${A}','mara-films','gAAAA-oauth','repo,read:packages')`);
await upgraded.exec(migrations[migration("github_app")] ?? "");
check("moving to the GitHub App drops the OAuth App's grants", ((await upgraded.query<Row>("select count(*)::int n from github_connections")).rows[0] ?? {}).n === 0);
// A project that talked to the agent before its loop changed: its events stay, the replayed conversation goes.
const old = (await upgraded.query<Row>(`insert into projects (user_id,name,discipline) values ('${A}','Before','media') returning id`)).rows[0] ?? {};
const before = ((await upgraded.query<Row>("select moody_begin_turn($1,$2,'hello',120) t", [old.id, A])).rows[0] ?? {}).t;
await upgraded.exec(`insert into agent_messages (project_id,role,content) values ('${String(old.id)}','user','"hello"');
  insert into project_events (project_id,turn_id,kind,data) values ('${String(old.id)}','${String(before)}','text','{"text":"Hi."}')`);
await upgraded.exec(migrations[migration("agent_loop")] ?? "");
const kept = (await upgraded.query<Row>("select agent_session, permissions, turn_id from projects where id=$1", [old.id])).rows[0] ?? {};
check("moving to the agent's loop keeps a project's events and its running turn, with no session yet",
  ((await upgraded.query<Row>("select count(*)::int n from project_events where project_id=$1", [old.id])).rows[0] ?? {}).n === 2
  && kept.agent_session === null && JSON.stringify(kept.permissions) === "{}" && kept.turn_id === before, kept);
check("and the conversation it replayed is gone", ((await upgraded.query<Row>("select to_regclass('public.agent_messages') t")).rows[0] ?? {}).t === null);
await upgraded.exec(migrations[migration("limits")] ?? "");
const earlier = (await upgraded.query<Row>("select * from moody_ensure_profile($1,$2,$3)", [A, "a@x.test", 60])).rows[0] ?? {};
check("an account from before limits were its own has set none", earlier.credits === 60 && earlier.turn_budget_usd === null && earlier.turn_limit === null, earlier);
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
  for (const table of ["projects", "assets", "project_events", "agent_transcripts", "github_connections", "epic_connections"]) {
    check(`${role} sees no ${table} rows`, (await one(`select count(*)::int n from ${table}`)).n === 0);
  }
  check(`${role} cannot start a turn`, /permission denied/.test(await refused("select moody_begin_turn($1,$2,'x',120)", [pa.id, A]) ?? ""));
  check(`${role} cannot answer an approval`, /permission denied/.test(await refused("select moody_resolve_approval($1,'ap-1','always')", [pa.id]) ?? ""));
  check(`${role} cannot write a transcript`, /permission denied/.test(await refused("select moody_append_transcript($1,'-work','s-1','','[]')", [pa.id]) ?? "")
    && /permission denied/.test(await refused("select * from moody_transcript_sessions($1,'-work')", [pa.id]) ?? "")
    && /permission denied/.test(await refused("select * from moody_transcript_subkeys($1,'-work','s-1')", [pa.id]) ?? ""));
  check(`${role} cannot start an engine`, /permission denied/.test(await refused("select * from moody_request_session($1,'blender','cpu','auto',1,5,$2)", [A, pa.id]) ?? ""));
  check(`${role} cannot grant itself credits`, /permission denied/.test(await refused("select moody_add_credits($1,999,'grant',null)", [A]) ?? ""));
  check(`${role} cannot insert a profile`, /row-level security/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "") || /duplicate/.test(await refused(`insert into profiles (id) values ('${C}')`) ?? "x") === false);
  await db.exec("reset role");
}
await db.exec("set role service_role");
check("the service role may call the functions", (await refused("select moody_queue_position($1)", [s1.id])) === null
  && (await refused("select moody_turn_alive($1,$2)", [pa.id, A])) === null
  && (await refused("select moody_append_transcript($1,'-work','s-1','','[]')", [pa.id])) === null
  && (await refused("select moody_resolve_approval($1,'ap-2','once')", [pa.id])) === null);
await db.exec("reset role");

console.log(failures === 0 ? "\nall checks passed" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
