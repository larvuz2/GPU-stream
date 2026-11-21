/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's sessions: a live card for each one in flight, and the list of recent ones.
 *
 * A card follows its session through every state the control plane reports: its place in the
 * queue, the workstation starting, the running session with its clock, spend, and the button that
 * opens the stream, and the end, with the reason. The stream's link is minted on demand (it is
 * fresh each time) and opened in a new tab.
 * @module
 */
import { useEffect, useId, useState, type ReactNode } from 'react';
import { CircleStop, ExternalLink, History, MonitorPlay, X } from 'lucide-react';
import { ArtImage } from '../components/Art';
import type { Session, SessionStatus } from '../lib/api';
import { brand, findApp, findRegion, findTier, hourlyUsd } from '../lib/catalog';
import { cx } from '../lib/cx';
import { clock, creditCount, price, shortDateTime, spanText, timestamp } from '../lib/format';
import { appImage } from '../lib/media';
import { describeEndReason } from './messages';
import { ErrorNotice } from './Notice';

/** How a status reads on its pill, and the dot beside it. */
const STATUS: Readonly<Record<SessionStatus, { label: string; dot: string }>> = {
  queued: { label: 'Queued', dot: 'dot-warn dot-live' },
  starting: { label: 'Starting', dot: 'dot-ember dot-live' },
  running: { label: 'Running', dot: 'dot-live' },
  ended: { label: 'Ended', dot: 'dot-idle' },
  failed: { label: 'Failed', dot: 'dot-bad' },
};

/**
 * Follows the clock while something on screen depends on it.
 *
 * @param ticking Whether to keep updating; a card that shows no running time does not re-render.
 * @returns The current time in milliseconds, at most a second old while ticking.
 */
function useNow(ticking: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) {
      return;
    }
    const update = (): void => {
      setNow(Date.now());
    };
    const first = window.setTimeout(update, 0);
    const interval = window.setInterval(update, 1000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(interval);
    };
  }, [ticking]);
  return now;
}

/**
 * The names a session's identifiers stand for.
 *
 * @param session The session.
 * @returns The app, tier, and region as the catalog names them, or the raw identifier of one the
 *   catalog no longer lists.
 */
function namesOf(session: Session): { app: string; tier: string; region: string } {
  return {
    app: findApp(session.app)?.name ?? session.app,
    tier: findTier(session.tier)?.name ?? session.tier,
    region: findRegion(session.region)?.name ?? session.region,
  };
}

/** Props of {@link ActiveSessions}. */
interface ActiveSessionsProps {
  /** The sessions to show cards for: those in flight, and those that ended while being watched. */
  sessions: Session[];
  /** Whether the first load has finished, before which an empty list says nothing. */
  loaded: boolean;
  /** Stops a session. */
  onStop: (id: string) => Promise<void>;
  /** Mints a link to a running session's stream. */
  onLink: (id: string) => Promise<string>;
  /** Stops showing an ended session's card. */
  onDismiss: (id: string) => void;
}

/**
 * Renders the cards of the sessions in flight, or what to do when there are none.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function ActiveSessions({ sessions, loaded, onStop, onLink, onDismiss }: ActiveSessionsProps) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="grid gap-4">
      <h2 id={titleId} className="sr-only">
        Active sessions
      </h2>
      {sessions.length === 0 ? (
        <div className="glass flex items-center gap-4 p-5 sm:p-6">
          <span className="icon-tile size-12">
            <MonitorPlay className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold tracking-tight">{loaded ? 'No session running' : 'Loading your studio…'}</p>
            <p className="mt-0.5 text-sm text-muted">
              {loaded ? 'Pick an app below and your workstation opens in a new tab.' : 'Fetching your sessions.'}
            </p>
          </div>
        </div>
      ) : (
        sessions.map((session) => (
          <SessionCard key={session.id} session={session} onStop={onStop} onLink={onLink} onDismiss={onDismiss} />
        ))
      )}
    </section>
  );
}

/** Props of {@link SessionCard}. */
interface SessionCardProps {
  /** The session the card follows. */
  session: Session;
  /** Stops the session. */
  onStop: (id: string) => Promise<void>;
  /** Mints a link to the session's stream. */
  onLink: (id: string) => Promise<string>;
  /** Stops showing the card once the session has ended. */
  onDismiss: (id: string) => void;
}

/**
 * Renders one session's live card.
 *
 * @param props The component's props.
 * @returns The card.
 */
function SessionCard({ session, onStop, onLink, onDismiss }: SessionCardProps) {
  const [pending, setPending] = useState<'opening' | 'stopping' | null>(null);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [blockedLink, setBlockedLink] = useState<string | null>(null);
  const running = session.status === 'running';
  const now = useNow(running);
  const names = namesOf(session);
  const tier = findTier(session.tier);
  const startedAt = timestamp(session.started_at);
  const endedAt = timestamp(session.ended_at);

  /**
   * Opens the stream in a new tab.
   *
   * The tab is opened before the link is asked for, while the click still counts as the user's
   * gesture: a tab opened after the request returns is a pop-up to the browser, and is blocked.
   * Where even that is refused, the link is shown for the user to follow.
   */
  async function open(): Promise<void> {
    setPending('opening');
    setError(null);
    setBlockedLink(null);
    const tab = window.open('', '_blank');
    if (tab !== null) {
      tab.document.title = `Opening ${names.app} — ${brand}`;
    }
    try {
      const url = await onLink(session.id);
      if (tab === null) {
        setBlockedLink(url);
      } else {
        tab.opener = null;
        tab.location.replace(url);
      }
    } catch (failure) {
      tab?.close();
      setError(failure);
    } finally {
      setPending(null);
    }
  }

  /** Stops the session, or takes it out of the queue. */
  async function stop(): Promise<void> {
    setPending('stopping');
    setError(null);
    setConfirmingStop(false);
    try {
      await onStop(session.id);
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(null);
    }
  }

  const status = STATUS[session.status];
  return (
    <article
      className="glass relative overflow-hidden p-5 sm:p-6"
      style={{ '--accent': findApp(session.app)?.accent }}
      aria-label={`${names.app} session, ${status.label.toLowerCase()}`}
    >
      <div
        className={cx(
          'pointer-events-none absolute -top-32 -right-24 size-72 rounded-full blur-3xl transition-opacity duration-700',
          'bg-[color-mix(in_oklab,var(--accent)_26%,transparent)]',
          running ? 'opacity-100' : 'opacity-40',
        )}
        aria-hidden="true"
      />
      <div className="relative">
        <header className="flex items-center gap-4">
          <span className="art h-14 w-[5.25rem] flex-none rounded-xl">
            <ArtImage src={appImage(session.app)} width={1200} height={800} />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-lg font-semibold tracking-tight">{names.app}</h3>
            <p className="text-sm text-muted">
              {names.tier} · {names.region}
            </p>
          </div>
          <span className="pill" role="status">
            <span className={cx('dot', status.dot)} aria-hidden="true" />
            {status.label}
          </span>
        </header>

        {session.status === 'queued' ? (
          <div className="mt-6">
            <p className="display text-3xl">
              {session.queue_position === null ? 'Waiting for a machine' : `#${session.queue_position} in line`}
            </p>
            <p className="lede mt-2 text-sm">
              Every {names.tier} machine is busy right now. Your workstation starts as soon as one is free, and this
              card updates on its own.
            </p>
          </div>
        ) : null}

        {session.status === 'starting' ? (
          <div className="mt-6">
            <p className="display text-3xl">Starting your workstation</p>
            <div className="progress mt-4" role="progressbar" aria-label="Starting" />
            <p className="lede mt-3 text-sm">
              Booting the machine and opening {names.app}. The button to open it appears here when it is ready.
            </p>
          </div>
        ) : null}

        {running ? (
          <dl className="mt-6 grid grid-cols-3 gap-2.5 sm:gap-3">
            <Stat label="Elapsed">
              <span className="tabular-nums">{startedAt === null ? '—' : clock(now - startedAt)}</span>
            </Stat>
            <Stat label="Spent" unit="credits">
              <span className="tabular-nums">{creditCount(session.credits_used)}</span>
            </Stat>
            <Stat label="Rate" unit={tier === undefined ? undefined : '/ hr'}>
              {tier === undefined ? '—' : price(hourlyUsd(tier))}
            </Stat>
          </dl>
        ) : null}

        {session.status === 'ended' || session.status === 'failed' ? (
          <div className="mt-6">
            <p className="display text-2xl">
              {session.status === 'failed' ? 'This session failed' : 'Session ended'}
            </p>
            <p className={cx('mt-2 text-sm', session.status === 'failed' ? 'text-bad' : 'text-muted')}>
              {describeEndReason(session.end_reason) ??
                (session.status === 'failed' ? 'The workstation could not be started.' : 'No reason was recorded.')}
            </p>
            <p className="mt-3 text-sm text-faint">
              {startedAt !== null && endedAt !== null ? `Ran for ${spanText(endedAt - startedAt)} · ` : ''}
              {creditCount(session.credits_used)} credits used
            </p>
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap items-center gap-2.5">
          {running ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={pending !== null}
              onClick={() => {
                void open();
              }}
            >
              {pending === 'opening' ? (
                <span className="spinner" aria-hidden="true" />
              ) : (
                <ExternalLink className="size-4" aria-hidden="true" />
              )}
              Open studio
            </button>
          ) : null}
          {session.status === 'queued' || session.status === 'starting' || running ? (
            confirmingStop ? (
              <>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => {
                    void stop();
                  }}
                >
                  <CircleStop className="size-4" aria-hidden="true" />
                  Yes, stop it
                </button>
                <button
                  type="button"
                  className="btn btn-quiet"
                  onClick={() => {
                    setConfirmingStop(false);
                  }}
                >
                  Keep running
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-ghost"
                disabled={pending !== null}
                onClick={() => {
                  if (running) {
                    setConfirmingStop(true);
                  } else {
                    void stop();
                  }
                }}
              >
                {pending === 'stopping' ? (
                  <span className="spinner" aria-hidden="true" />
                ) : (
                  <CircleStop className="size-4" aria-hidden="true" />
                )}
                {session.status === 'queued' ? 'Leave the queue' : running ? 'Stop' : 'Cancel'}
              </button>
            )
          ) : (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                onDismiss(session.id);
              }}
            >
              <X className="size-4" aria-hidden="true" />
              Dismiss
            </button>
          )}
          {confirmingStop ? (
            <p className="basis-full text-sm text-muted">Save to your workspace first. Unsaved work is lost.</p>
          ) : null}
        </div>

        {blockedLink === null ? null : (
          <p className="notice notice-info mt-4">
            <span>
              Your browser blocked the new tab.{' '}
              <a href={blockedLink} target="_blank" rel="noopener noreferrer" className="link font-semibold">
                Open your studio
              </a>
            </span>
          </p>
        )}
        {error === null ? null : (
          <div className="mt-4">
            <ErrorNotice error={error} />
          </div>
        )}
      </div>
    </article>
  );
}

/** Props of {@link Stat}. */
interface StatProps {
  /** What the figure measures. */
  label: string;
  /** The figure's unit, set small after it. */
  unit?: string;
  /** The figure. */
  children: ReactNode;
}

/**
 * Renders one labeled figure of a running session.
 *
 * @param props The component's props.
 * @returns The term and its value, for a description list.
 */
function Stat({ label, unit, children }: StatProps) {
  return (
    <div className="rounded-xl border border-line bg-black/20 px-3 py-3 sm:px-4">
      <dt className="text-[0.6875rem] font-semibold tracking-wider text-faint uppercase">{label}</dt>
      <dd className="mt-1 flex flex-wrap items-baseline gap-x-1.5 text-lg font-semibold tracking-tight sm:text-2xl">
        {children}
        {unit === undefined ? null : <span className="text-xs font-normal tracking-normal text-muted">{unit}</span>}
      </dd>
    </div>
  );
}

/** Props of {@link RecentSessions}. */
interface RecentSessionsProps {
  /** The ended and failed sessions, most recent first. */
  sessions: Session[];
}

/**
 * Renders the list of recent sessions: what ran, when, for how long, at what cost, and why it
 * ended.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function RecentSessions({ sessions }: RecentSessionsProps) {
  const titleId = useId();
  return (
    <section className="glass p-5 sm:p-7" aria-labelledby={titleId}>
      <h2 id={titleId} className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
        <History className="size-[1.1rem] text-ember-300" aria-hidden="true" />
        Recent sessions
      </h2>
      {sessions.length === 0 ? (
        <p className="mt-4 text-sm text-muted">Sessions you have finished show up here.</p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {sessions.map((session) => (
            <RecentRow key={session.id} session={session} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Props of {@link RecentRow}. */
interface RecentRowProps {
  /** The finished session the row describes. */
  session: Session;
}

/**
 * Renders one finished session as a row.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function RecentRow({ session }: RecentRowProps) {
  const names = namesOf(session);
  const startedAt = timestamp(session.started_at);
  const endedAt = timestamp(session.ended_at);
  const failed = session.status === 'failed';
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-1 py-3.5">
      <p className="flex min-w-0 items-center gap-2.5 font-medium">
        <span className={cx('dot', failed ? 'dot-bad' : 'dot-idle')} aria-hidden="true" />
        <span className="truncate">
          {names.app} <span className="font-normal text-muted">· {names.tier}</span>
        </span>
      </p>
      <p className="text-right text-sm font-medium tabular-nums">{creditCount(session.credits_used)} credits</p>
      <p className={cx('col-span-2 pl-[1.125rem] text-sm sm:col-span-1', failed ? 'text-bad' : 'text-muted')}>
        {describeEndReason(session.end_reason) ?? (failed ? 'Failed' : 'Ended')}
      </p>
      <p className="col-span-2 pl-[1.125rem] text-sm text-faint sm:col-span-1 sm:pl-0 sm:text-right">
        {shortDateTime(session.started_at ?? session.created_at)}
        {startedAt !== null && endedAt !== null ? ` · ${spanText(endedAt - startedAt)}` : ''}
      </p>
    </li>
  );
}
