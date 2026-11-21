/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's data: the account, its sessions, and its API keys, kept current.
 *
 * Everything is loaded once, and the session list is then polled every five seconds for as long
 * as a session is queued, starting, or running, and only while the tab is visible. The account is
 * re-read when the list shows credits being spent or a session changing state, so the balance in
 * the header follows the meter without a second poll. Which tiers can be started comes from the
 * control plane's health check, read once with the rest.
 *
 * A session the page has seen active stays "watched" after it ends, which is how the dashboard
 * keeps showing its card, with the reason it ended, until the user dismisses it.
 * @module
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  isActive,
  type ApiKey,
  type ControlPlane,
  type CreatedKey,
  type LaunchRequest,
  type Me,
  type Session,
} from '../lib/api';
import { describeError, NOT_CONFIGURED } from './messages';

/** How often the session list is re-read while a session is active. */
const POLL_MS = 5000;

/** What the dashboard renders from, and the actions that change it. */
export interface Studio {
  /** The signed-in account, or `null` until it has loaded. */
  me: Me | null;
  /** The account's sessions: the active ones, then the most recent ended ones. */
  sessions: Session[];
  /** The account's API keys. */
  keys: ApiKey[];
  /**
   * The identifiers of the tiers that can be started right now, or `null` when every tier can:
   * the control plane does not say, or its health check did not answer.
   */
  openTiers: ReadonlySet<string> | null;
  /** The identifiers of sessions seen active on this page, whose cards outlive their end. */
  watched: ReadonlySet<string>;
  /** Whether the first load has finished, with or without an error. */
  loaded: boolean;
  /** Why the latest load or poll failed, or `null` when it did not. */
  loadError: string | null;
  /** Starts a session. Rejects with an `ApiError`. */
  launch: (request: LaunchRequest) => Promise<void>;
  /** Stops a session. Rejects with an `ApiError`. */
  stop: (id: string) => Promise<void>;
  /** Mints a link to a running session's stream. Rejects with an `ApiError`. */
  link: (id: string) => Promise<string>;
  /** Stops showing an ended session's card. */
  dismiss: (id: string) => void;
  /** Creates an API key and returns its secret once. Rejects with an `ApiError`. */
  createKey: (name: string) => Promise<CreatedKey>;
  /** Revokes an API key. Rejects with an `ApiError`. */
  revokeKey: (id: string) => Promise<void>;
  /** Starts a checkout and returns the page to send the browser to. Rejects with an `ApiError`. */
  checkout: (pack: string) => Promise<string>;
}

/**
 * Summarizes a session list as the parts the balance depends on.
 *
 * @param sessions The session list.
 * @returns A string that changes when a session changes state or spends credits.
 */
function spendFingerprint(sessions: Session[]): string {
  return sessions.map((session) => `${session.id}:${session.status}:${session.credits_used}`).join('|');
}

/**
 * Loads and follows the account's data through a control plane.
 *
 * @param client The control plane, or `null` when none is connected; every action then rejects
 *   and nothing is requested.
 * @returns The data and the actions over it.
 */
export function useStudio(client: ControlPlane | null): Studio {
  const [me, setMe] = useState<Me | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [openTiers, setOpenTiers] = useState<ReadonlySet<string> | null>(null);
  const [watched, setWatched] = useState<ReadonlySet<string>>(new Set<string>());
  const [loaded, setLoaded] = useState(client === null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const fingerprint = useRef('');

  /** Takes a fresh session list, and marks the active sessions in it as watched. */
  const acceptSessions = useCallback((next: Session[]): void => {
    setSessions(next);
    const active = next.filter(isActive).map((session) => session.id);
    if (active.length > 0) {
      setWatched((previous) => new Set([...previous, ...active]));
    }
  }, []);

  /** Re-reads the account, quietly: a balance that is a moment old is still worth showing. */
  const refreshMe = useCallback(async (): Promise<void> => {
    if (client === null) {
      return;
    }
    try {
      setMe(await client.me());
    } catch {
      // The next poll or action reads it again.
    }
  }, [client]);

  /** Re-reads the session list, and the account when the list shows the balance has moved. */
  const refreshSessions = useCallback(async (): Promise<void> => {
    if (client === null) {
      return;
    }
    try {
      const next = await client.listSessions();
      acceptSessions(next);
      setLoadError(null);
      const print = spendFingerprint(next);
      if (print !== fingerprint.current) {
        fingerprint.current = print;
        void refreshMe();
      }
    } catch (error) {
      setLoadError(describeError(error));
    }
  }, [client, acceptSessions, refreshMe]);

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    Promise.all([client.me(), client.listSessions(), client.listApiKeys()])
      .then(([nextMe, nextSessions, nextKeys]) => {
        if (!current) {
          return;
        }
        fingerprint.current = spendFingerprint(nextSessions);
        setMe(nextMe);
        acceptSessions(nextSessions);
        setKeys(nextKeys);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (current) {
          setLoadError(describeError(error));
        }
      })
      .finally(() => {
        if (current) {
          setLoaded(true);
        }
      });
    // Apart from the rest: a health check that fails takes nothing else down with it, and leaves
    // every tier offered for the control plane itself to accept or refuse.
    client
      .health()
      .then((health) => {
        if (current) {
          setOpenTiers(health.tiers === null ? null : new Set(health.tiers));
        }
      })
      .catch(() => {
        if (current) {
          setOpenTiers(null);
        }
      });
    return () => {
      current = false;
    };
  }, [client, acceptSessions]);

  const polling = sessions.some(isActive);
  useEffect(() => {
    if (client === null || !polling) {
      return;
    }
    const poll = (): void => {
      if (document.visibilityState === 'visible') {
        void refreshSessions();
      }
    };
    const interval = window.setInterval(poll, POLL_MS);
    // A tab that comes back into view catches up at once instead of at the next tick.
    document.addEventListener('visibilitychange', poll);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', poll);
    };
  }, [client, polling, refreshSessions]);

  /**
   * Returns the control plane, for an action to call.
   *
   * @returns The control plane.
   * @throws ApiError When none is connected.
   */
  const connected = useCallback((): ControlPlane => {
    if (client === null) {
      throw new ApiError(NOT_CONFIGURED, 'The control plane is not connected.');
    }
    return client;
  }, [client]);

  /** Puts a session the control plane just returned at its place in the list. */
  const mergeSession = useCallback((session: Session): void => {
    setSessions((previous) =>
      previous.some((other) => other.id === session.id)
        ? previous.map((other) => (other.id === session.id ? session : other))
        : [session, ...previous],
    );
    setWatched((previous) => new Set([...previous, session.id]));
  }, []);

  const launch = useCallback(
    async (request: LaunchRequest): Promise<void> => {
      try {
        mergeSession(await connected().createSession(request));
      } finally {
        // A refusal is news about the account too: a launch turned down for credits means the
        // balance on screen is stale.
        void refreshMe();
      }
    },
    [connected, mergeSession, refreshMe],
  );

  const stop = useCallback(
    async (id: string): Promise<void> => {
      mergeSession(await connected().stopSession(id));
      void refreshMe();
    },
    [connected, mergeSession, refreshMe],
  );

  const link = useCallback(async (id: string): Promise<string> => connected().sessionLink(id), [connected]);

  const dismiss = useCallback((id: string): void => {
    setWatched((previous) => new Set([...previous].filter((other) => other !== id)));
  }, []);

  const createKey = useCallback(
    async (name: string): Promise<CreatedKey> => {
      const created = await connected().createApiKey(name);
      setKeys((previous) => [created.key, ...previous]);
      return created;
    },
    [connected],
  );

  const revokeKey = useCallback(
    async (id: string): Promise<void> => {
      await connected().revokeApiKey(id);
      setKeys((previous) => previous.filter((key) => key.id !== id));
    },
    [connected],
  );

  const checkout = useCallback(async (pack: string): Promise<string> => connected().checkout(pack), [connected]);

  return {
    me,
    sessions,
    keys,
    openTiers,
    watched,
    loaded,
    loadError,
    launch,
    stop,
    link,
    dismiss,
    createKey,
    revokeKey,
    checkout,
  };
}
