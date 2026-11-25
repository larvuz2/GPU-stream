/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio's "Connect Claude" dialog, opened from the account menu: create, list, and revoke API
 * keys, and the command that hands one to Claude.
 *
 * The control plane returns a key's secret once, when it is created, so the dialog shows it then,
 * with the setup command already filled in, and holds it only in this component's state: closing
 * the dialog or leaving the page is the last anyone sees of it. The keys are read each time the
 * dialog opens, since the content mounts afresh then.
 * @module
 */
import { useEffect, useId, useState, type SubmitEvent } from 'react';
import { KeyRound, Plus, Sparkles, Trash2, X } from 'lucide-react';
import { CommandBlock, CopyButton } from '../components/Copy';
import { Dialog } from '../components/Dialog';
import type { ApiKey, CreatedKey } from '../lib/api';
import { shortDate } from '../lib/format';
import { mcpEndpoint, mcpSetupCommand, SECRET_PLACEHOLDER } from '../lib/mcp';
import { ErrorNotice, Notice } from './Notice';

/** What the dialog does with the account's keys. */
interface KeyActions {
  /** Whether a control plane is connected; without one no key can be made. */
  connected: boolean;
  /** Lists the account's keys. */
  onList: () => Promise<ApiKey[]>;
  /** Creates a key and returns its secret. */
  onCreate: (name: string) => Promise<CreatedKey>;
  /** Revokes a key. */
  onRevoke: (id: string) => Promise<void>;
}

/** Props of {@link ConnectClaudeDialog}. */
interface ConnectClaudeDialogProps extends KeyActions {
  /** Whether the dialog is shown. */
  open: boolean;
  /** Closes the dialog. */
  onClose: () => void;
}

/**
 * Renders the dialog.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function ConnectClaudeDialog({ open, onClose, ...actions }: ConnectClaudeDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={open} onClose={onClose} labelledBy={titleId} wide>
      <ConnectClaude titleId={titleId} {...actions} />
    </Dialog>
  );
}

/** Props of {@link ConnectClaude}. */
interface ConnectClaudeProps extends KeyActions {
  /** The `id` the dialog is titled by. */
  titleId: string;
}

/**
 * Renders the dialog's content.
 *
 * @param props The component's props.
 * @returns The content.
 */
function ConnectClaude({ titleId, connected, onList, onCreate, onRevoke }: ConnectClaudeProps) {
  const nameId = useId();
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<CreatedKey | null>(null);

  useEffect(() => {
    if (!connected) {
      return;
    }
    let current = true;
    onList()
      .then((listed) => {
        if (current) {
          setKeys(listed);
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
  }, [connected, onList]);

  /**
   * Revokes a key and drops it from the list.
   *
   * @param id The key to revoke.
   */
  async function revoke(id: string): Promise<void> {
    await onRevoke(id);
    setKeys((previous) => previous?.filter((key) => key.id !== id) ?? null);
  }

  /**
   * Creates a key under the name entered and shows its secret.
   *
   * @param event The form's submission.
   */
  async function create(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const made = await onCreate(name.trim());
      setCreated(made);
      setKeys((previous) => [made.key, ...(previous ?? [])]);
      setName('');
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div>
        <h2 id={titleId} className="flex items-center gap-2.5 pr-10 text-xl font-semibold tracking-tight">
          <Sparkles className="size-[1.1rem] text-ember-300" aria-hidden="true" />
          Connect Claude
        </h2>
        <p className="lede mt-2 text-sm">
          Give Claude an API key and it can start sessions, work inside the app you are watching, and stop them when
          it is done.
        </p>

        {created === null ? null : (
          <div className="mt-5 rounded-2xl border border-ember/40 bg-ember/[0.07] p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold">
                Your new key, <span className="text-ember-200">{created.key.name}</span>
              </p>
              <button
                type="button"
                aria-label="Hide the new key"
                className="btn btn-quiet btn-sm -mt-1 -mr-1 size-8 px-0"
                onClick={() => {
                  setCreated(null);
                }}
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <p className="mt-1 text-sm text-warn">Copy it now. It is not shown again.</p>
            <div className="mt-3 flex items-center gap-2 rounded-xl border border-line-strong bg-black/40 py-1.5 pr-1.5 pl-3">
              <code className="mono min-w-0 flex-1 truncate text-sm" title={created.secret}>
                {created.secret}
              </code>
              <CopyButton text={created.secret} label="Copy key" />
            </div>
            <CommandBlock
              className="mt-3"
              title="Paste into your terminal"
              command={mcpSetupCommand(created.secret)}
            />
          </div>
        )}

        <form
          className="mt-5 flex flex-col gap-2.5 sm:flex-row"
          onSubmit={(event) => {
            void create(event);
          }}
        >
          <div className="min-w-0 flex-1">
            <label htmlFor={nameId} className="sr-only">
              Key name
            </label>
            <input
              id={nameId}
              className="field"
              placeholder="Name, e.g. Laptop"
              required
              maxLength={60}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
            />
          </div>
          <button type="submit" className="btn btn-primary h-[2.9rem]" disabled={!connected || busy}>
            {busy ? <span className="spinner" aria-hidden="true" /> : <Plus className="size-4" aria-hidden="true" />}
            Create key
          </button>
        </form>
        {error === null ? null : (
          <div className="mt-3">
            <ErrorNotice error={error} />
          </div>
        )}

        <h3 className="mt-7 text-xs font-semibold tracking-[0.14em] text-faint uppercase">Your keys</h3>
        {loadError === null ? null : (
          <div className="mt-3">
            <ErrorNotice error={loadError} />
          </div>
        )}
        {keys === null ? (
          <p className="mt-3 text-sm text-muted">{connected ? 'Loading your keys…' : 'Keys appear here once the control plane is connected.'}</p>
        ) : keys.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No keys yet. Create one to connect Claude.</p>
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {keys.map((key) => (
              <KeyRow key={key.id} apiKey={key} onRevoke={revoke} />
            ))}
          </ul>
        )}

        {created === null ? (
          <>
            <h3 className="mt-7 text-xs font-semibold tracking-[0.14em] text-faint uppercase">Setup command</h3>
            <CommandBlock className="mt-3" title="Claude Code" command={mcpSetupCommand()} />
            <p className="mt-3 text-sm text-faint">
              Replace <span className="mono text-muted">{SECRET_PLACEHOLDER}</span> with your key. Other MCP clients
              can connect to <span className="mono break-all text-muted">{mcpEndpoint()}</span> with the key as a
              bearer token.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

/** Props of {@link KeyRow}. */
interface KeyRowProps {
  /** The key the row describes. */
  apiKey: ApiKey;
  /** Revokes the key. */
  onRevoke: (id: string) => Promise<void>;
}

/**
 * Renders one key with the two-step control that revokes it.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function KeyRow({ apiKey, onRevoke }: KeyRowProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  /** Revokes the key; the row disappears with it on success. */
  async function revoke(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onRevoke(apiKey.id);
    } catch (failure) {
      setError(failure);
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <li className="py-3.5">
      <div className="flex items-start gap-3">
        <KeyRound className="mt-1 size-4 flex-none text-faint" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{apiKey.name}</p>
          <p className="text-xs leading-relaxed text-faint">
            <span className="mono">{apiKey.prefix}…</span> · created {shortDate(apiKey.created_at)}
            <br />
            {apiKey.last_used_at === null ? 'Never used' : `Last used ${shortDate(apiKey.last_used_at)}`}
          </p>
        </div>
        {confirming ? (
          <div className="flex flex-none items-center gap-1.5">
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={busy}
              onClick={() => {
                void revoke();
              }}
            >
              {busy ? <span className="spinner" aria-hidden="true" /> : null}
              Revoke
            </button>
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label={`Revoke ${apiKey.name}`}
            className="btn btn-quiet btn-sm size-8 flex-none px-0"
            onClick={() => {
              setConfirming(true);
            }}
          >
            <Trash2 className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
      {confirming ? (
        <div className="mt-2.5">
          <Notice tone="warn">Anything using this key stops working at once.</Notice>
        </div>
      ) : null}
      {error === null ? null : (
        <div className="mt-2.5">
          <ErrorNotice error={error} />
        </div>
      )}
    </li>
  );
}
