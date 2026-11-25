# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""A project's conversation, kept in the database: the loop's session store over the service's `Store`.

The Claude Agent SDK writes a session's transcript to the disk of the machine
a turn runs on, one JSON entry a line, and mirrors every batch of entries to a
`SessionStore`; resuming a session asks the store for the entries and rebuilds
the file from them. A turn's machine is gone when the turn ends, so the store
is the conversation: `Transcript` keeps the entries as rows of
`agent_transcripts` and gives them back in the order they were written, which
is what lets a project's next turn run anywhere.

An adapter is one project's. Every row carries the project's id beside the
key the SDK addresses a transcript by (its `project_key`, the turn's working
directory in the SDK's own spelling, the session's id, and a `subpath` for a
subagent's transcript, empty for the session's own), so a project's rows are
deleted with it and no key the SDK sends reaches another project's.

The database does the parts that have to be one transaction
(`moody/supabase/migrations`): `moody_append_transcript` writes a batch in
order and leaves out an entry whose `uuid` the transcript already has, since
the SDK sends a batch again when an append fails partway; an entry without one
(a title, a mode marker) is always kept. The SDK calls the store from its
event loop and the `Store` is a blocking client, so each method does its
request on a thread.
"""

from __future__ import annotations

from typing import Any

import anyio
from claude_agent_sdk import (
    SessionKey,
    SessionListSubkeysKey,
    SessionStore,
    SessionStoreEntry,
    SessionStoreListEntry,
)

TABLE = "agent_transcripts"


class Transcript(SessionStore):
    """The session store of one project: `agent_transcripts` rows under that project's id."""

    def __init__(self, store: Any, project_id: str) -> None:
        self.store = store
        self.project_id = project_id

    def scope(self, key: SessionKey | SessionListSubkeysKey) -> dict[str, str]:
        """The filter that selects one transcript's rows: this project's, of a key's project key, session, and subpath."""
        return {
            "project_id": f"eq.{self.project_id}",
            "project_key": f"eq.{key['project_key']}",
            "session_id": f"eq.{key['session_id']}",
            "subpath": f"eq.{key.get('subpath') or ''}",
        }

    async def append(self, key: SessionKey, entries: list[SessionStoreEntry]) -> None:
        """Add a batch of entries to a transcript, in order, once each."""
        if not entries:
            return
        await anyio.to_thread.run_sync(
            lambda: self.store.rpc(
                "moody_append_transcript",
                p_project=self.project_id,
                p_project_key=key["project_key"],
                p_session=key["session_id"],
                p_subpath=key.get("subpath") or "",
                p_entries=entries,
            )
        )

    async def load(self, key: SessionKey) -> list[SessionStoreEntry] | None:
        """A transcript's entries as they were appended, or nothing for one never written."""
        rows = await anyio.to_thread.run_sync(
            lambda: self.store.every(TABLE, **self.scope(key), order="id.asc")
        )
        return [row["entry"] for row in rows] or None

    def has(self, key: SessionKey) -> bool:
        """Whether a transcript has any entry, which is whether its session can be resumed."""
        return bool(self.store.rows(TABLE, **self.scope(key), select="id", limit="1"))

    async def list_sessions(self, project_key: str) -> list[SessionStoreListEntry]:
        """The sessions written under a project key, each with when it was last written, in milliseconds."""
        rows = await anyio.to_thread.run_sync(
            lambda: self.store.rpc(
                "moody_transcript_sessions",
                p_project=self.project_id,
                p_project_key=project_key,
            )
        )
        return [
            {"session_id": row["session_id"], "mtime": int(row["mtime"])}
            for row in rows or []
        ]

    async def list_subkeys(self, key: SessionListSubkeysKey) -> list[str]:
        """The subpaths written under a session: its subagents' transcripts."""
        rows = await anyio.to_thread.run_sync(
            lambda: self.store.rpc(
                "moody_transcript_subkeys",
                p_project=self.project_id,
                p_project_key=key["project_key"],
                p_session=key["session_id"],
            )
        )
        return [row["subpath"] if isinstance(row, dict) else row for row in rows or []]

    async def delete(self, key: SessionKey) -> None:
        """Delete one transcript, and with a session's own transcript every subagent's under it."""
        scope = self.scope(key)
        if not key.get("subpath"):
            del scope["subpath"]
        await anyio.to_thread.run_sync(lambda: self.store.delete(TABLE, **scope))
