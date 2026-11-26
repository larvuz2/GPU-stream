/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio's account-wide data: the account and its balance, what the control plane can do, the
 * projects, the GitHub connection, and the Epic connection.
 *
 * Each is read once when the studio opens. The balance is re-read when something spends it (an
 * engine changes state, a turn ends), so the sidebar follows the meter without a poll of its own.
 * The account also carries the person's name, the limits of their turns, and their settings,
 * which they change through it.
 * A control plane from before the studio answers the project and GitHub routes with 404; that is
 * reported as `missing`, which the studio shows as a calm "not here yet" rather than an error,
 * while the account, credits, and keys keep working.
 * @module
 */
import { useCallback, useEffect, useState } from 'react';
import {
  ApiError,
  isMissing,
  type ControlPlane,
  type EpicStatus,
  type GitHubRepo,
  type GitHubStatus,
  type Health,
  type AccountChanges,
  type Me,
  type NewProject,
  type Project,
  type ProjectChanges,
} from '../lib/api';
import { NOT_CONFIGURED } from './messages';

/**
 * How far a piece of data has come: still loading, loaded, not served by this control plane,
 * failed, or not asked for because no control plane is connected.
 */
export type Availability = 'loading' | 'ready' | 'missing' | 'failed' | 'offline';

/**
 * Returns the control plane, for an action to call.
 *
 * @param client The control plane, or `null`.
 * @returns The control plane.
 * @throws ApiError When none is connected.
 */
export function connected(client: ControlPlane | null): ControlPlane {
  if (client === null) {
    throw new ApiError(NOT_CONFIGURED, 'The control plane is not connected.');
  }
  return client;
}

/** The account and what the control plane can do. */
export interface Account {
  /** The signed-in account, or `null` until it has loaded. */
  me: Me | null;
  /** What the control plane reports about itself, or `null` until it answers. */
  health: Health | null;
  /** Re-reads the account, quietly. */
  refreshMe: () => void;
  /**
   * Changes the person's name, the limits of their turns, or their settings. Rejects with an
   * `ApiError`, 400 for a value the control plane refuses, in which case nothing changed.
   */
  change: (changes: AccountChanges) => Promise<void>;
}

/**
 * Loads the account and the control plane's health.
 *
 * @param client The control plane, or `null` when none is connected.
 * @returns The account.
 */
export function useAccount(client: ControlPlane | null): Account {
  const [me, setMe] = useState<Me | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  const refreshMe = useCallback((): void => {
    client
      ?.me()
      .then(setMe)
      .catch(() => {
        // A balance a moment old is still worth showing; the next refresh reads it again.
      });
  }, [client]);

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    client
      .me()
      .then((next) => {
        if (current) {
          setMe(next);
        }
      })
      .catch(() => {
        // The sidebar shows a dash for the balance until a refresh succeeds.
      });
    client
      .health()
      .then((next) => {
        if (current) {
          setHealth(next);
        }
      })
      .catch(() => {
        // Unknown health leaves every feature offered for the control plane itself to refuse.
      });
    return () => {
      current = false;
    };
  }, [client]);

  const change = useCallback(
    async (changes: AccountChanges): Promise<void> => {
      setMe(await connected(client).updateMe(changes));
    },
    [client],
  );

  return { me, health, refreshMe, change };
}

/** The account's projects and the actions over them. */
export interface Projects {
  /** The projects, most recently updated first. */
  list: Project[];
  /** How far the list has come. */
  status: Availability;
  /** Why the list failed to load, while it has. */
  error: unknown;
  /** Creates a project and puts it at the top. Rejects with an `ApiError`. */
  create: (project: NewProject) => Promise<Project>;
  /** Changes a project. Rejects with an `ApiError`. */
  update: (id: string, changes: ProjectChanges) => Promise<Project>;
  /** Deletes a project. Rejects with an `ApiError`. */
  remove: (id: string) => Promise<void>;
  /** Takes a project as another call returned it, in place of the one held. */
  accept: (project: Project) => void;
  /** Marks a project as just changed, which moves it to the top of the recent ones. */
  touch: (id: string) => void;
}

/**
 * Orders projects most recently updated first.
 *
 * @param projects The projects.
 * @returns A new, sorted list.
 */
function byRecency(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
}

/**
 * Loads the account's projects.
 *
 * @param client The control plane, or `null` when none is connected.
 * @returns The projects and the actions over them.
 */
export function useProjects(client: ControlPlane | null): Projects {
  const [list, setList] = useState<Project[]>([]);
  const [status, setStatus] = useState<Availability>(client === null ? 'offline' : 'loading');
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    client
      .listProjects()
      .then((projects) => {
        if (current) {
          setList(byRecency(projects));
          setStatus('ready');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setStatus(isMissing(failure) ? 'missing' : 'failed');
          setError(failure);
        }
      });
    return () => {
      current = false;
    };
  }, [client]);

  const accept = useCallback((project: Project): void => {
    setList((previous) =>
      byRecency(
        previous.some((other) => other.id === project.id)
          ? previous.map((other) => (other.id === project.id ? project : other))
          : [project, ...previous],
      ),
    );
  }, []);

  const create = useCallback(
    async (project: NewProject): Promise<Project> => {
      const made = await connected(client).createProject(project);
      accept(made);
      return made;
    },
    [client, accept],
  );

  const update = useCallback(
    async (id: string, changes: ProjectChanges): Promise<Project> => {
      const changed = await connected(client).updateProject(id, changes);
      accept(changed);
      return changed;
    },
    [client, accept],
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await connected(client).deleteProject(id);
      setList((previous) => previous.filter((project) => project.id !== id));
    },
    [client],
  );

  const touch = useCallback((id: string): void => {
    const now = new Date().toISOString();
    setList((previous) =>
      byRecency(previous.map((project) => (project.id === id ? { ...project, updated_at: now } : project))),
    );
  }, []);

  return { list, status, error, create, update, remove, accept, touch };
}

/** The person's GitHub connection and the actions over it. */
export interface GitHub {
  /** The connection, or `null` until it has loaded. */
  status: GitHubStatus | null;
  /** How far it has come. */
  availability: Availability;
  /**
   * Sends the browser to GitHub to connect, returning to `back` or to the address it left from.
   * Rejects with an `ApiError`.
   */
  connect: (back?: URL) => Promise<void>;
  /**
   * Sends the browser to the GitHub App's installation page, for a repository it is not on yet,
   * returning to `back` or to the address it left from. Rejects with an `ApiError`.
   */
  install: (back?: URL) => Promise<void>;
  /** Disconnects. Rejects with an `ApiError`. */
  disconnect: () => Promise<void>;
  /** Lists the repositories of the GitHub App's installations the person reaches. Rejects with an `ApiError`. */
  repos: () => Promise<GitHubRepo[]>;
}

/** The query parameter GitHub's callback reports the outcome in, which the studio reads once. */
export const GITHUB_RESULT_PARAMETER = 'github';

/** The query parameter the Epic connection's callback reports its outcome in, read once the same way. */
export const EPIC_RESULT_PARAMETER = 'epic';

/**
 * The address to come back to from GitHub: the one given, or this page's, without the outcome
 * parameters of an earlier attempt.
 *
 * @param back The address to come back to, where not this page's.
 * @returns The address.
 */
function returnAddress(back?: URL): string {
  const address = new URL(back ?? window.location.href);
  address.searchParams.delete(GITHUB_RESULT_PARAMETER);
  address.searchParams.delete(EPIC_RESULT_PARAMETER);
  return address.href;
}

/**
 * Loads the GitHub connection.
 *
 * Connecting leaves the page for GitHub and comes back to the address it left from, without the
 * outcome parameter of an earlier attempt, so the same project is open on return. Installing the
 * GitHub App goes the same way, through its installation page.
 *
 * @param client The control plane, or `null` when none is connected.
 * @returns The connection.
 */
export function useGitHub(client: ControlPlane | null): GitHub {
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [availability, setAvailability] = useState<Availability>(client === null ? 'offline' : 'loading');

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    client
      .github()
      .then((next) => {
        if (current) {
          setStatus(next);
          setAvailability('ready');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setAvailability(isMissing(failure) ? 'missing' : 'failed');
        }
      });
    return () => {
      current = false;
    };
  }, [client]);

  const connect = useCallback(
    async (back?: URL): Promise<void> => {
      window.location.assign(await connected(client).connectGitHub(returnAddress(back)));
    },
    [client],
  );

  const install = useCallback(
    async (back?: URL): Promise<void> => {
      window.location.assign(await connected(client).installGitHub(returnAddress(back)));
    },
    [client],
  );

  const disconnect = useCallback(async (): Promise<void> => {
    await connected(client).disconnectGitHub();
    setStatus((previous) => (previous === null ? null : { ...previous, connected: false, login: null, avatar_url: null }));
  }, [client]);

  const repos = useCallback(async (): Promise<GitHubRepo[]> => connected(client).githubRepos(), [client]);

  return { status, availability, connect, install, disconnect, repos };
}

/** The person's Epic connection and the actions over it. */
export interface Epic {
  /** The connection, or `null` until it has loaded. */
  status: EpicStatus | null;
  /** How far it has come. */
  availability: Availability;
  /** Sends the browser to GitHub to connect the account linked to Epic, returning here. Rejects with an `ApiError`. */
  connect: () => Promise<void>;
  /** Asks again whether Epic's registry lets the account pull the editor, as after linking it on Epic's site. */
  refresh: () => void;
  /** Disconnects. Rejects with an `ApiError`. */
  disconnect: () => Promise<void>;
}

/**
 * Loads the Epic connection.
 *
 * It is read once when the studio opens and again when the person asks, never on a timer: each
 * read asks Epic's registry, and the link it reports changes only when the person links their
 * accounts on Epic's site.
 *
 * @param client The control plane, or `null` when none is connected.
 * @returns The connection.
 */
export function useEpic(client: ControlPlane | null): Epic {
  const [status, setStatus] = useState<EpicStatus | null>(null);
  const [availability, setAvailability] = useState<Availability>(client === null ? 'offline' : 'loading');
  const [reading, setReading] = useState(0);

  useEffect(() => {
    if (client === null) {
      return;
    }
    let current = true;
    client
      .epic()
      .then((next) => {
        if (current) {
          setStatus(next);
          setAvailability('ready');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setAvailability(isMissing(failure) ? 'missing' : 'failed');
        }
      });
    return () => {
      current = false;
    };
  }, [client, reading]);

  const connect = useCallback(async (): Promise<void> => {
    window.location.assign(await connected(client).connectEpic(returnAddress()));
  }, [client]);

  const refresh = useCallback((): void => {
    setReading((previous) => previous + 1);
  }, []);

  const disconnect = useCallback(async (): Promise<void> => {
    await connected(client).disconnectEpic();
    setStatus((previous) =>
      previous === null ? null : { ...previous, connected: false, login: null, linked: null, detail: null },
    );
  }, [client]);

  return { status, availability, connect, refresh, disconnect };
}
