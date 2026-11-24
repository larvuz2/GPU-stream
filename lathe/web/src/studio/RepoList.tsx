/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The repositories a person can bring into the studio, searchable, with the way to add one.
 *
 * They are the repositories of the control plane's GitHub App's installations the person reaches,
 * read once when the list appears. One the list lacks is one the app is not installed on, so
 * under it "Don't see your repository?" opens the app's installation page, where the person
 * installs it on their account or an organization, or, as an organization member who may not,
 * sends the request to its owners, who approve once. The Environment panel links a project with
 * it, and the new-project dialog imports one.
 * @module
 */
import { useEffect, useState } from 'react';
import { Check, Lock } from 'lucide-react';
import type { GitHubRepo } from '../lib/api';
import { cx } from '../lib/cx';
import { useNow } from './hooks';
import { ErrorNotice } from './Notice';
import { ago } from './present';

/** Props of {@link RepoList}. */
interface RepoListProps {
  /** Lists the repositories of the GitHub App's installations the person reaches. */
  loadRepos: () => Promise<GitHubRepo[]>;
  /** Whether a choice is being acted on, when none can be made. */
  busy: boolean;
  /** The repository chosen, as `owner/name`, where the list holds a choice. */
  chosen?: string | null;
  /** Called with the repository the person picks. */
  onPick: (repo: GitHubRepo) => void;
  /** Sends the browser to the GitHub App's installation page. */
  onInstall: () => void;
}

/**
 * Renders the searchable list of repositories and the link that adds one.
 *
 * @param props The component's props.
 * @returns The list.
 */
export function RepoList({ loadRepos, busy, chosen = null, onPick, onInstall }: RepoListProps) {
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [query, setQuery] = useState('');
  const now = useNow(false);

  useEffect(() => {
    let current = true;
    loadRepos()
      .then((listed) => {
        if (current) {
          setRepos(listed);
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setLoadError(failure);
        }
      });
    return () => {
      current = false;
    };
  }, [loadRepos]);

  const shown = (repos ?? []).filter((repo) => repo.full_name.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <div>
      <input
        type="search"
        className="field field-sm"
        placeholder="Find a repository"
        aria-label="Find a repository"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
        }}
      />
      {loadError === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={loadError} />
        </div>
      )}
      <ul className="thin-scroll mt-1.5 max-h-48 overflow-y-auto">
        {repos === null && loadError === null ? (
          <li className="px-2 py-2 text-xs text-faint">Loading your repositories…</li>
        ) : shown.length === 0 && loadError === null ? (
          <li className="px-2 py-2 text-xs text-faint">
            {repos?.length === 0 ? 'Lathe’s GitHub App is on none of your repositories yet.' : 'No repository matches.'}
          </li>
        ) : (
          shown.map((repo) => (
            <li key={repo.full_name}>
              <button
                type="button"
                className={cx(
                  'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/[0.05]',
                  chosen === repo.full_name && 'bg-white/[0.07]',
                )}
                aria-pressed={chosen === null ? undefined : chosen === repo.full_name}
                disabled={busy}
                onClick={() => {
                  onPick(repo);
                }}
              >
                {repo.private ? <Lock className="size-3 flex-none text-faint" aria-label="Private" /> : null}
                <span className="min-w-0 flex-1 truncate">{repo.full_name}</span>
                {chosen === repo.full_name ? (
                  <Check className="size-3.5 flex-none text-ember-200" aria-hidden="true" />
                ) : (
                  <span className="text-[0.6875rem] text-faint">{ago(repo.updated_at, now)}</span>
                )}
              </button>
            </li>
          ))
        )}
      </ul>
      <p className="mt-2 border-t border-line pt-2 text-xs leading-relaxed text-faint">
        Don&rsquo;t see your repository?{' '}
        <button type="button" className="link text-muted" disabled={busy} onClick={onInstall}>
          Add it to Lathe&rsquo;s GitHub App
        </button>
        . A member of an organization who cannot install it there sends the request to its owners, who approve once.
      </p>
    </div>
  );
}
