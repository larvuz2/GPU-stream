/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Screen: the live stream of the engine the person chose, in a frame of the page.
 *
 * The stage is one element for the life of the project, which the layout moves between the top
 * of the right column and the top of the center (`studio.css`), so the stream's iframe is never
 * remounted and its connection survives the move. In the column, a layer over the stream turns a
 * click into focus mode, since a click inside the iframe never reaches this page; in focus mode
 * the layer is gone and the stream takes input.
 *
 * The stream is served from the engine's own origin under a link minted for each load. Some
 * browsers refuse that origin its cookie inside another site's frame, and a frame the stream's
 * server will not be framed by loads empty; neither is visible from this page, since a frame of
 * another origin cannot be read. So the stage says what it can: a frame that has not loaded in
 * twenty seconds is reported as stalled, and the way to open the stream in a tab of its own is
 * always one click away, with a note under a loaded frame for the case this page cannot see.
 *
 * An engine whose session reports streams beside its desktop (`Session.streams`: the Unreal
 * Editor streams itself, apart from the desktop Blender runs on) gets a switch between "Desktop"
 * and each stream's name. The desktop is the session's own minted link; a stream is its own
 * address. Switching loads the other picture in place of the first, as switching engines does, so
 * only the picture on screen is streamed.
 * @module
 */
import { useCallback, useEffect, useState, type ComponentType } from 'react';
import { ChevronDown, ExternalLink, Maximize2, Minimize2, MonitorPlay, RefreshCw } from 'lucide-react';
import { isActive, type Session } from '../lib/api';
import { findApp, findTier, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { clock, timestamp } from '../lib/format';
import { useNow } from './hooks';
import { describeEndReason, describeError } from './messages';
import { openStreamTab } from './present';

/** How long a frame may take to load before the stage calls it stalled. */
const STALL_MS = 20_000;

/**
 * What stands in for the stream where there is none to show, as the demo has: drawn for the app,
 * and for the stream chosen beside its desktop (`null` for the desktop).
 */
export type StreamStandIn = ComponentType<{ app: CatalogApp | undefined; stream: string | null }>;

/** What the switch calls an engine's own desktop, beside the streams it reports. */
const DESKTOP = 'Desktop';

/** Props of {@link Stage}. */
interface StageProps {
  /** The project's engines. */
  engines: Session[];
  /** The engine on screen, or `null` for none. */
  engine: Session | null;
  /** Puts an engine on screen. */
  onSelect: (id: string) => void;
  /** Whether focus mode is on. */
  focus: boolean;
  /** Turns focus mode on or off. */
  onFocus: (focus: boolean) => void;
  /** Whether the panel is unfolded. */
  open: boolean;
  /** Folds or unfolds it. */
  onToggle: () => void;
  /** Mints a link to a running engine's stream. */
  link: (id: string) => Promise<string>;
  /** Goes to the Environment panel, to start an engine. */
  onStartEngine: () => void;
  /** Whether the layout is a narrow screen's tabs. */
  narrow: boolean;
  /** Whether the region is hidden behind another tab on a narrow screen. */
  mobileHidden: boolean;
  /** Drawn instead of the stream, where there is none to show. */
  standIn?: StreamStandIn;
}

/**
 * Renders the stage.
 *
 * @param props The component's props.
 * @returns The stage.
 */
export function Stage({
  engines,
  engine,
  onSelect,
  focus,
  onFocus,
  open,
  onToggle,
  link,
  onStartEngine,
  narrow,
  mobileHidden,
  standIn,
}: StageProps) {
  const [opening, setOpening] = useState(false);
  const [tabError, setTabError] = useState<string | null>(null);
  const [blockedLink, setBlockedLink] = useState<string | null>(null);
  const [streamName, setStreamName] = useState<string | null>(null);
  const app = engine === null ? undefined : findApp(engine.app);
  const running = engine?.status === 'running';
  const streams = engine?.streams ?? [];
  const stream = streams.find((candidate) => candidate.name === streamName) ?? null;
  const appName = app?.name ?? engine?.app ?? 'Engine';
  const pictureName = stream?.name ?? appName;
  const choices = engines.filter(isActive);
  const unfolded = open || focus || narrow;
  // By its address alone: the engine list is read again every few seconds, and a new list must
  // not count as a new picture.
  const streamUrl = stream?.url ?? null;
  const pictureLink = useCallback(
    (id: string): Promise<string> => (streamUrl === null ? link(id) : Promise.resolve(streamUrl)),
    [link, streamUrl],
  );

  /** Opens the picture on screen in a tab of its own. */
  async function openTab(): Promise<void> {
    if (engine === null) {
      return;
    }
    setOpening(true);
    setTabError(null);
    setBlockedLink(null);
    try {
      setBlockedLink(await openStreamTab(() => pictureLink(engine.id), pictureName));
    } catch (failure) {
      setTabError(describeError(failure));
    } finally {
      setOpening(false);
    }
  }

  return (
    <section className="studio-stage" aria-label="Screen" data-mobile-hidden={mobileHidden}>
      <div className={cx('flex min-h-[2.9rem] items-center gap-2 py-1.5 pr-2', focus ? 'pl-4 sm:pl-6' : 'pl-4')}>
        <button
          type="button"
          className="panel-toggle min-w-0 flex-none"
          aria-expanded={unfolded}
          disabled={focus || narrow}
          onClick={onToggle}
        >
          <MonitorPlay aria-hidden="true" />
          <span>Screen</span>
          {focus || narrow ? null : (
            <ChevronDown className={cx('panel-chevron', !open && '-rotate-90')} aria-hidden="true" />
          )}
        </button>
        {engine === null ? null : choices.length > 1 ? (
          <select
            className="field field-sm h-7 w-auto min-w-0 truncate py-0 pr-7 pl-2 text-xs"
            aria-label="Engine on screen"
            value={engine.id}
            onChange={(event) => {
              onSelect(event.target.value);
            }}
          >
            {choices.map((choice) => (
              <option key={choice.id} value={choice.id}>
                {findApp(choice.app)?.name ?? choice.app} · {findTier(choice.tier)?.name ?? choice.tier}
              </option>
            ))}
          </select>
        ) : (
          <span className="flex min-w-0 items-center gap-1.5 truncate text-xs text-muted">
            <span className={cx('dot', engineDot(engine))} aria-hidden="true" />
            <span className="truncate">{appName}</span>
          </span>
        )}
        {running && streams.length > 0 ? (
          <div className="flex flex-none items-center rounded-lg border border-line p-0.5" role="group" aria-label="Picture on screen">
            {[null, ...streams.map((candidate) => candidate.name)].map((name) => {
              const chosen = name === (stream?.name ?? null);
              return (
                <button
                  key={name ?? DESKTOP}
                  type="button"
                  aria-pressed={chosen}
                  className={cx(
                    'h-6 rounded-md px-2 text-xs transition-colors',
                    chosen ? 'bg-white/10 text-fg' : 'text-muted hover:text-fg',
                  )}
                  onClick={() => {
                    setStreamName(name);
                  }}
                >
                  {name ?? DESKTOP}
                </button>
              );
            })}
          </div>
        ) : null}
        <div className="ml-auto flex items-center gap-0.5">
          {running ? (
            <button
              type="button"
              className="icon-btn"
              aria-label={`Open ${pictureName} in a new tab`}
              title="Open in a new tab"
              disabled={opening}
              onClick={() => {
                void openTab();
              }}
            >
              {opening ? <span className="spinner size-3.5" aria-hidden="true" /> : <ExternalLink aria-hidden="true" />}
            </button>
          ) : null}
          {narrow || engine === null ? null : focus ? (
            <button
              type="button"
              className="btn btn-ghost btn-sm h-8 px-3 text-[0.8125rem]"
              onClick={() => {
                onFocus(false);
              }}
            >
              <Minimize2 className="size-3.5" aria-hidden="true" />
              Back to conversation
            </button>
          ) : (
            <button
              type="button"
              className="icon-btn"
              aria-label="Focus on the screen"
              title="Focus on the screen"
              onClick={() => {
                onFocus(true);
              }}
            >
              <Maximize2 aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {unfolded ? (
        <div className={cx('flex min-h-0 flex-1 flex-col pb-3', focus ? 'px-4 sm:px-6' : 'px-3')}>
          <div className="stream-box">
            {engine === null ? (
              <Empty engines={engines} onStartEngine={onStartEngine} />
            ) : running ? (
              <Stream
                key={`${engine.id} ${stream?.name ?? DESKTOP}`}
                engine={engine}
                appName={pictureName}
                app={app}
                stream={stream?.name ?? null}
                link={pictureLink}
                standIn={standIn}
                interactive={focus || narrow}
                onFocus={() => {
                  onFocus(true);
                }}
                onOpenTab={() => {
                  void openTab();
                }}
              />
            ) : (
              <Waiting engine={engine} appName={appName} />
            )}
          </div>
          {running && standIn === undefined ? (
            <p className="mt-2 text-[0.6875rem] text-faint">
              Blank, or asking you to sign in? Your browser may keep the stream out of this page.{' '}
              <button
                type="button"
                className="link"
                onClick={() => {
                  void openTab();
                }}
              >
                Open it in a new tab
              </button>
            </p>
          ) : null}
          {tabError === null ? null : <p className="mt-2 text-xs text-bad">{tabError}</p>}
          {blockedLink === null ? null : (
            <p className="mt-2 text-xs text-muted">
              Your browser blocked the new tab.{' '}
              <a className="link" href={blockedLink} target="_blank" rel="noopener noreferrer">
                Open {pictureName}
              </a>
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

/**
 * The status dot of an engine.
 *
 * @param engine The engine.
 * @returns The dot's classes.
 */
function engineDot(engine: Session): string {
  switch (engine.status) {
    case 'running':
      return 'dot-live';
    case 'starting':
      return 'dot-ember dot-live';
    case 'queued':
      return 'dot-warn dot-live';
    case 'failed':
      return 'dot-bad';
    case 'ended':
      return 'dot-idle';
  }
}

/** Props of {@link Empty}. */
interface EmptyProps {
  /** The project's engines. */
  engines: Session[];
  /** Goes to the Environment panel. */
  onStartEngine: () => void;
}

/**
 * Renders the screen with no engine on it.
 *
 * @param props The component's props.
 * @returns The placeholder.
 */
function Empty({ engines, onStartEngine }: EmptyProps) {
  return (
    <div className="absolute inset-0 grid place-items-center p-4 text-center">
      <div>
        <MonitorPlay className="mx-auto size-6 text-faint" aria-hidden="true" />
        <p className="mt-2 text-sm font-medium">No engine on screen</p>
        <p className="mt-1 text-xs text-muted">
          {engines.length === 0
            ? 'The agent opens one when the work needs it, or you can.'
            : 'Start one to watch it here.'}
        </p>
        <button type="button" className="btn btn-ghost btn-sm mt-3 h-8 px-3 text-xs" onClick={onStartEngine}>
          Start an engine
        </button>
      </div>
    </div>
  );
}

/** Props of {@link Waiting}. */
interface WaitingProps {
  /** The engine, queued, starting, or ended. */
  engine: Session;
  /** Its app's name. */
  appName: string;
}

/**
 * Renders the screen of an engine that is not streaming: coming up, or ended.
 *
 * @param props The component's props.
 * @returns The placeholder.
 */
function Waiting({ engine, appName }: WaitingProps) {
  const coming = engine.status === 'queued' || engine.status === 'starting';
  const now = useNow(coming);
  const since = timestamp(engine.created_at);
  return (
    <div className="absolute inset-0 grid place-items-center p-6 text-center">
      <div className="w-full max-w-xs">
        {coming ? (
          <>
            <p className="text-sm font-medium">
              {engine.status === 'queued' ? `${appName} is waiting for a workstation` : `${appName} is starting`}
            </p>
            <div className="progress mx-auto mt-3 w-40" aria-hidden="true" />
            <p className="mt-2.5 text-xs text-muted">
              {engine.status === 'queued' && engine.queue_position !== null
                ? `Number ${engine.queue_position} in line`
                : 'Usually about a minute'}
              {since === null ? '' : ` · ${clock(now - since)}`}
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium">
              {appName} {engine.status === 'failed' ? 'did not start' : 'has stopped'}
            </p>
            <p className="mt-1.5 text-xs text-muted">
              {describeEndReason(engine.end_reason) ?? 'Start it again from Environment.'}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

/** Props of {@link Stream}. */
interface StreamProps {
  /** The running engine. */
  engine: Session;
  /** Its catalog app. */
  app: CatalogApp | undefined;
  /** The name of what it shows: its app's, or the stream's beside its desktop. */
  appName: string;
  /** The stream beside its desktop that it shows, or `null` for the desktop. */
  stream: string | null;
  /** Mints a link to what it shows. */
  link: (id: string) => Promise<string>;
  /** Drawn instead of the stream, where there is none to show. */
  standIn: StreamStandIn | undefined;
  /** Whether the stream takes input, rather than a click entering focus mode. */
  interactive: boolean;
  /** Enters focus mode. */
  onFocus: () => void;
  /** Opens the stream in a tab of its own. */
  onOpenTab: () => void;
}

/**
 * Renders a running engine's stream, and what became of loading it.
 *
 * @param props The component's props.
 * @returns The stream.
 */
function Stream({
  engine,
  app,
  appName,
  stream,
  link,
  standIn: StandIn,
  interactive,
  onFocus,
  onOpenTab,
}: StreamProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [phase, setPhase] = useState<'minting' | 'loading' | 'loaded' | 'stalled' | 'failed'>('minting');
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (StandIn !== undefined) {
      return;
    }
    let current = true;
    link(engine.id)
      .then((url) => {
        if (current) {
          setSrc(url);
          setPhase('loading');
        }
      })
      .catch((failure: unknown) => {
        if (current) {
          setError(describeError(failure));
          setPhase('failed');
        }
      });
    return () => {
      current = false;
    };
  }, [engine.id, link, attempt, StandIn]);

  useEffect(() => {
    if (phase !== 'loading') {
      return;
    }
    const timer = window.setTimeout(() => {
      setPhase('stalled');
    }, STALL_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [phase]);

  /** Mints a fresh link and loads the frame again. */
  function retry(): void {
    setSrc(null);
    setError(null);
    setPhase('minting');
    setAttempt(attempt + 1);
  }

  if (StandIn !== undefined) {
    return (
      <>
        <StandIn app={app} stream={stream} />
        {interactive ? null : <FocusLayer appName={appName} onFocus={onFocus} />}
      </>
    );
  }

  return (
    <>
      {src === null ? null : (
        <iframe
          key={src}
          src={src}
          title={`${appName} stream`}
          allow="autoplay; fullscreen; clipboard-read; clipboard-write; microphone; camera; gamepad"
          allowFullScreen
          onLoad={() => {
            setPhase((previous) => (previous === 'loading' || previous === 'stalled' ? 'loaded' : previous));
          }}
        />
      )}
      {phase === 'minting' || phase === 'loading' ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <p className="flex items-center gap-2 text-xs text-muted">
            <span className="spinner size-3.5" aria-hidden="true" />
            Connecting to {appName}…
          </p>
        </div>
      ) : null}
      {phase === 'stalled' || phase === 'failed' ? (
        <div className="absolute inset-0 grid place-items-center bg-ink-950/85 p-5 text-center backdrop-blur-sm">
          <div className="max-w-xs">
            <p className="text-sm font-medium">
              {phase === 'failed' ? `Could not open ${appName}` : `${appName} is not loading here`}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">
              {error ?? 'Some browsers block the stream inside another page. It opens in a tab of its own.'}
            </p>
            <div className="mt-3.5 flex justify-center gap-2">
              <button type="button" className="btn btn-primary btn-sm h-8 px-3 text-xs" onClick={onOpenTab}>
                <ExternalLink className="size-3.5" aria-hidden="true" />
                Open in a new tab
              </button>
              <button type="button" className="btn btn-ghost btn-sm h-8 px-3 text-xs" onClick={retry}>
                <RefreshCw className="size-3.5" aria-hidden="true" />
                Retry
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {interactive || phase !== 'loaded' ? null : <FocusLayer appName={appName} onFocus={onFocus} />}
    </>
  );
}

/** Props of {@link FocusLayer}. */
interface FocusLayerProps {
  /** The app's name. */
  appName: string;
  /** Enters focus mode. */
  onFocus: () => void;
}

/**
 * Renders the layer over the small stream that a click turns into focus mode.
 *
 * @param props The component's props.
 * @returns The layer.
 */
function FocusLayer({ appName, onFocus }: FocusLayerProps) {
  return (
    <button type="button" className="stream-focus-layer" aria-label={`Focus on ${appName}`} onClick={onFocus}>
      <span className="flex items-center gap-2 rounded-full border border-white/20 bg-ink-950/70 px-3.5 py-1.5 text-xs font-semibold backdrop-blur">
        <Maximize2 className="size-3.5" aria-hidden="true" />
        Work in {appName}
      </span>
    </button>
  );
}
