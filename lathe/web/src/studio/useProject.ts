/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * One open project's live data: the agent's event log, its engines, and its library.
 *
 * The event log is read after a cursor, the highest event identifier seen, so each poll returns
 * only what is new. One poll is in flight at a time and the next is scheduled when it settles:
 * about once a second while a turn runs, every five seconds while idle, and every fifteen while
 * the tab is hidden. Sending a message or stopping a turn polls at once, and so does the tab
 * coming back into view. Between the message being accepted and the log showing its turn (the
 * agent is spawned elsewhere and takes a moment), the page counts the turn as running and shows
 * the message as sent, so the composer does not flicker back to idle.
 *
 * The first page replays the whole log, which the conversation is folded from. Events that arrive
 * after it are live, and also update what they describe: a `library` event puts its asset in the
 * library, an `engine` event re-reads the engines, and the end of a turn marks the project as
 * just changed and re-reads the balance the turn may have spent. The plan is the latest `plan`
 * event's, or the project's own before any.
 *
 * Engines are re-read every three seconds while one is queued or starting, which is how an
 * engine the person started is seen coming up without the agent saying so.
 * @module
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  isMissing,
  TURN_RUNNING,
  ApiError,
  type Asset,
  type ControlPlane,
  type LaunchRequest,
  type Library,
  type NewAsset,
  type PlanItem,
  type Project,
  type Session,
  type StudioEvent,
  type TurnId,
} from '../lib/api';
import { connected, type Availability } from './useAccount';

/** How often the log is read while a turn runs. */
const RUNNING_MS = 1000;
/** How often the log is read while the project is idle and in view. */
const IDLE_MS = 5000;
/** How often the log is read while the tab is hidden. */
const HIDDEN_MS = 15_000;
/** How long to wait after a failed read before the next. */
const RETRY_MS = 8000;
/** How long a sent message counts its turn as running before the log shows the turn. */
const TURN_GRACE_MS = 20_000;
/** How often the engines are re-read while one is coming up. */
const ENGINE_POLL_MS = 3000;

/** A message the control plane accepted, shown as sent until the log has it. */
export interface PendingMessage {
  /** The turn it started. */
  turn: TurnId;
  /** The message. */
  text: string;
  /** When it was sent, in milliseconds since the epoch. */
  at: number;
}

/** What the open project's views render from, and the actions that change it. */
export interface ProjectData {
  /** The project's events, in log order. */
  events: StudioEvent[];
  /** How far the log has come. */
  eventsStatus: Availability;
  /** Why the latest read of the log failed, or `null`. */
  eventsError: unknown;
  /** Whether a turn is running, as the log says or as a message just sent implies. */
  running: boolean;
  /** The message just sent, until the log has it. */
  pending: PendingMessage | null;
  /** Sends a message, starting a turn. Rejects with an `ApiError`, 409 while a turn runs. */
  send: (text: string) => Promise<void>;
  /** Stops the running turn. Rejects with an `ApiError`. */
  stop: () => Promise<void>;
  /** The agent's plan. */
  plan: PlanItem[];
  /** The project's engines, as last read. */
  engines: Session[];
  /** How far the engines have come. */
  enginesStatus: Availability;
  /** Starts an engine. Rejects with an `ApiError`. */
  startEngine: (request: LaunchRequest) => Promise<Session>;
  /** Stops an engine. Rejects with an `ApiError`. */
  stopEngine: (id: string) => Promise<void>;
  /** Mints a link to a running engine's stream. Rejects with an `ApiError`. */
  link: (id: string) => Promise<string>;
  /** The library, or `null` until it has loaded. */
  library: Library | null;
  /** How far the library has come. */
  libraryStatus: Availability;
  /** The library's sections: the project's, then any only an asset names, in order. */
  sections: string[];
  /** Adds an asset, uploading a file to it when one is given. Rejects with an `ApiError`. */
  createAsset: (asset: NewAsset, file: File | null) => Promise<Asset>;
  /** Uploads a media file to an asset. Rejects with an `ApiError`. */
  uploadMedia: (assetId: string, file: File) => Promise<Asset>;
  /** Deletes an asset. Rejects with an `ApiError`. */
  deleteAsset: (assetId: string) => Promise<void>;
  /** Adds a section to the library. Rejects with an `ApiError`. */
  addSection: (name: string) => Promise<void>;
}

/** What the open project's data reports back to the studio around it. */
export interface ProjectCallbacks {
  /** Takes the project as a call returned it. */
  onProject: (project: Project) => void;
  /** Marks the project as just changed. */
  onTouched: () => void;
  /** Re-reads the balance. */
  onSpent: () => void;
}

/**
 * Puts a record in a list in place of the one with its identifier, or first when it is new.
 *
 * @param list The list.
 * @param record The record.
 * @returns The new list.
 */
function upsert<T extends { id: string }>(list: T[], record: T): T[] {
  return list.some((other) => other.id === record.id)
    ? list.map((other) => (other.id === record.id ? record : other))
    : [record, ...list];
}

/**
 * Loads and follows one project.
 *
 * @param client The control plane, or `null` when none is connected.
 * @param project The project.
 * @param callbacks What the data reports back.
 * @returns The project's data and the actions over it.
 */
export function useProject(client: ControlPlane | null, project: Project, callbacks: ProjectCallbacks): ProjectData {
  const projectId = project.id;
  const [events, setEvents] = useState<StudioEvent[]>([]);
  const [eventsStatus, setEventsStatus] = useState<Availability>(client === null ? 'offline' : 'loading');
  const [eventsError, setEventsError] = useState<unknown>(null);
  const [serverRunning, setServerRunning] = useState(false);
  const [pending, setPending] = useState<PendingMessage | null>(null);
  const [engines, setEngines] = useState<Session[]>([]);
  const [enginesStatus, setEnginesStatus] = useState<Availability>(client === null ? 'offline' : 'loading');
  const [library, setLibrary] = useState<Library | null>(null);
  const [libraryStatus, setLibraryStatus] = useState<Availability>(client === null ? 'offline' : 'loading');

  const cursor = useRef(0);
  const pendingRef = useRef<PendingMessage | null>(null);
  const wake = useRef<() => void>(() => undefined);
  const latest = useRef(callbacks);
  useEffect(() => {
    latest.current = callbacks;
  });

  const refreshEngines = useCallback(async (): Promise<void> => {
    if (client === null) {
      return;
    }
    try {
      setEngines(await client.listEngines(projectId));
      setEnginesStatus('ready');
    } catch (failure) {
      setEnginesStatus(isMissing(failure) ? 'missing' : 'failed');
    }
  }, [client, projectId]);

  /** Applies what live events describe to the data they describe. */
  const applyLive = useCallback(
    (live: StudioEvent[]): void => {
      let reread = false;
      for (const event of live) {
        if (event.kind === 'library') {
          const { asset } = event.data;
          setLibrary((previous) =>
            previous === null ? previous : { ...previous, assets: upsert(previous.assets, asset) },
          );
        } else if (event.kind === 'engine') {
          setEngines((previous) => upsert(previous, event.data.engine));
          reread = true;
        } else if (event.kind === 'turn_end') {
          latest.current.onTouched();
          latest.current.onSpent();
        }
      }
      if (reread) {
        void refreshEngines();
      }
    },
    [refreshEngines],
  );

  useEffect(() => {
    if (client === null) {
      return;
    }
    let canceled = false;
    let timer: number | undefined;
    let inFlight = false;
    let wanted = false;
    let first = true;

    const schedule = (delay: number): void => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        void tick();
      }, delay);
    };

    /**
     * Reads the next page of the log and takes in what it holds.
     *
     * @returns How long to wait before the next read.
     */
    const poll = async (): Promise<number> => {
      try {
        const page = await client.listEvents(projectId, cursor.current);
        if (canceled) {
          return IDLE_MS;
        }
        const after = cursor.current;
        if (page.cursor !== null) {
          cursor.current = Math.max(after, page.cursor);
        }
        const fresh = page.events.filter((event) => event.id > after);
        if (fresh.length > 0) {
          setEvents((previous) => [...previous, ...fresh]);
          if (!first) {
            applyLive(fresh);
          }
        }
        const waiting = pendingRef.current;
        if (
          waiting !== null &&
          (fresh.some(
            (event) =>
              event.turn_id === waiting.turn || (event.kind === 'user_message' && event.data.text === waiting.text),
          ) ||
            Date.now() - waiting.at > TURN_GRACE_MS)
        ) {
          pendingRef.current = null;
          setPending(null);
        }
        setServerRunning(page.running);
        setEventsStatus('ready');
        setEventsError(null);
        first = false;
        if (page.running || pendingRef.current !== null) {
          return RUNNING_MS;
        }
        return document.visibilityState === 'visible' ? IDLE_MS : HIDDEN_MS;
      } catch (failure) {
        if (canceled) {
          return RETRY_MS;
        }
        if (isMissing(failure)) {
          setEventsStatus('missing');
          // A control plane without the studio's routes may be upgraded while the page is open.
          return 60_000;
        }
        setEventsError(failure);
        setEventsStatus((previous) => (previous === 'loading' ? 'failed' : previous));
        return RETRY_MS;
      }
    };

    const tick = async (): Promise<void> => {
      if (inFlight) {
        wanted = true;
        return;
      }
      inFlight = true;
      const delay = await poll();
      inFlight = false;
      if (!canceled) {
        schedule(wanted ? 0 : delay);
        wanted = false;
      }
    };

    wake.current = () => {
      schedule(0);
    };
    void tick();
    const onVisibility = (): void => {
      if (document.visibilityState === 'visible') {
        schedule(0);
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      canceled = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibility);
      wake.current = () => undefined;
    };
  }, [client, projectId, applyLive]);

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    client
      .listEngines(projectId)
      .then((listed) => {
        if (current) {
          setEngines(listed);
          setEnginesStatus('ready');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setEnginesStatus(isMissing(failure) ? 'missing' : 'failed');
        }
      });
    client
      .getLibrary(projectId)
      .then((loaded) => {
        if (current) {
          setLibrary(loaded);
          setLibraryStatus('ready');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setLibraryStatus(isMissing(failure) ? 'missing' : 'failed');
        }
      });
    client
      .getProject(projectId)
      .then((fresh) => {
        if (current) {
          latest.current.onProject(fresh);
        }
      })
      .catch(() => {
        // The list's copy of the project stands in until the next change returns a fresh one.
      });
    return () => {
      current = false;
    };
  }, [client, projectId]);

  const comingUp = engines.some((engine) => engine.status === 'queued' || engine.status === 'starting');
  useEffect(() => {
    if (!comingUp) {
      return;
    }
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void refreshEngines();
      }
    }, ENGINE_POLL_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [comingUp, refreshEngines]);

  const send = useCallback(
    async (text: string): Promise<void> => {
      const turn = await connected(client).sendMessage(projectId, text);
      const message = { turn, text, at: Date.now() };
      pendingRef.current = message;
      setPending(message);
      latest.current.onTouched();
      wake.current();
    },
    [client, projectId],
  );

  const stop = useCallback(async (): Promise<void> => {
    try {
      await connected(client).stopTurn(projectId);
    } finally {
      pendingRef.current = null;
      setPending(null);
      wake.current();
    }
  }, [client, projectId]);

  const startEngine = useCallback(
    async (request: LaunchRequest): Promise<Session> => {
      try {
        const engine = await connected(client).startEngine(projectId, request);
        setEngines((previous) => upsert(previous, engine));
        return engine;
      } finally {
        latest.current.onSpent();
      }
    },
    [client, projectId],
  );

  const stopEngine = useCallback(
    async (id: string): Promise<void> => {
      const engine = await connected(client).stopSession(id);
      setEngines((previous) => upsert(previous, engine));
      latest.current.onSpent();
    },
    [client],
  );

  const link = useCallback(async (id: string): Promise<string> => connected(client).sessionLink(id), [client]);

  const putAsset = useCallback((asset: Asset): void => {
    setLibrary((previous) =>
      previous === null
        ? { sections: [asset.section], assets: [asset] }
        : { ...previous, assets: upsert(previous.assets, asset) },
    );
  }, []);

  const uploadMedia = useCallback(
    async (assetId: string, file: File): Promise<Asset> => {
      const asset = await connected(client).uploadMedia(projectId, assetId, file);
      putAsset(asset);
      return asset;
    },
    [client, projectId, putAsset],
  );

  const createAsset = useCallback(
    async (asset: NewAsset, file: File | null): Promise<Asset> => {
      const made = await connected(client).createAsset(projectId, asset);
      putAsset(made);
      return file === null ? made : uploadMedia(made.id, file);
    },
    [client, projectId, putAsset, uploadMedia],
  );

  const deleteAsset = useCallback(
    async (assetId: string): Promise<void> => {
      await connected(client).deleteAsset(projectId, assetId);
      setLibrary((previous) =>
        previous === null ? previous : { ...previous, assets: previous.assets.filter((asset) => asset.id !== assetId) },
      );
    },
    [client, projectId],
  );

  const sections = useMemo(() => {
    const ordered = [...(library?.sections ?? []), ...project.library_sections];
    for (const asset of library?.assets ?? []) {
      ordered.push(asset.section);
    }
    return [...new Set(ordered.filter((section) => section.trim() !== ''))];
  }, [library, project.library_sections]);

  const addSection = useCallback(
    async (name: string): Promise<void> => {
      const trimmed = name.trim();
      if (trimmed === '' || sections.includes(trimmed)) {
        return;
      }
      const changed = await connected(client).updateProject(projectId, { library_sections: [...sections, trimmed] });
      latest.current.onProject(changed);
      setLibrary((previous) => (previous === null ? previous : { ...previous, sections: changed.library_sections }));
    },
    [client, projectId, sections],
  );

  const plan = useMemo(() => {
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const event = events[index];
      if (event?.kind === 'plan') {
        return event.data.items;
      }
    }
    return project.plan;
  }, [events, project.plan]);

  return {
    events,
    eventsStatus,
    eventsError,
    running: serverRunning || pending !== null,
    pending,
    send,
    stop,
    plan,
    engines,
    enginesStatus,
    startEngine,
    stopEngine,
    link,
    library,
    libraryStatus,
    sections,
    createAsset,
    uploadMedia,
    deleteAsset,
    addSection,
  };
}

/**
 * Words a refused message for the composer, where 409 means a turn is still running rather than a
 * limit.
 *
 * @param error What sending rejected with.
 * @returns The sentence, or `null` when the refusal is not that one.
 */
export function turnRunningText(error: unknown): string | null {
  return error instanceof ApiError && error.status === TURN_RUNNING
    ? 'The agent is still working on the last message. Wait for it to finish, or stop it.'
    : null;
}
