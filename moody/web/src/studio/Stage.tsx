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
 * An engine that streams more than its desktop (`Session.streams`: an Unreal engine's Desktop,
 * where the files, the GitHub client, and Blender are, and Unreal, the editor's own stream) gets a
 * toggle between them in the header, in the column and in focus mode alike, with Alt+1, Alt+2,
 * and so on as its keys while this page, rather than the stream, has the keyboard. Outside focus
 * mode the toggle takes the place of the engine's name, which only focus mode has room for. Every picture
 * of the engine on screen is loaded at once and kept loaded, the ones not shown hidden rather than
 * removed, so a switch is instant and the stream switched away from keeps its connection: both
 * pictures are streamed for as long as the engine is on screen, which the switching is worth. A
 * picture opens first at the link its listing reported, and a retry mints a fresh one; a later
 * listing's links never reload a frame that is up. Which picture is shown is the workspace's,
 * since the agent switches it too (a `screen` event).
 *
 * Where the project keeps the versions of a video with their edits, the Screen shows them while
 * no engine is on it (`VersionsScreen.tsx`): the newest version playing over its tracks, drawn by
 * the page from the log, which costs no engine at all. An engine put on screen takes their place,
 * and a switch in the header brings the versions back over it. While they are shown over a
 * running engine the stream is not loaded, so the engine encodes no picture nobody watches; going
 * back to it connects again. The engine itself runs on, which the stage says.
 * @module
 */
import { useCallback, useEffect, useState, type ComponentType } from 'react';
import {
  Box,
  ChevronDown,
  ExternalLink,
  Layers,
  Maximize2,
  Minimize2,
  Monitor,
  MonitorPlay,
  RefreshCw,
  type LucideIcon,
} from 'lucide-react';
import { DESKTOP_STREAM, isActive, type EngineStream, type Session } from '../lib/api';
import { findApp, findTier, type CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { clock, timestamp } from '../lib/format';
import { useNow } from './hooks';
import { describeEndReason, describeError } from './messages';
import { openStreamTab } from './present';
import type { Version } from './transcript';
import { VersionsScreen } from './VersionsScreen';

/** How long a frame may take to load before the stage calls it stalled. */
const STALL_MS = 20_000;

/** The keys that pick a picture, by its place in the toggle: Alt with the digit's key. */
const PICTURE_KEYS = ['Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5', 'Digit6', 'Digit7', 'Digit8', 'Digit9'];

/**
 * What stands in for the stream where there is none to show, as the demo has: drawn for the app,
 * and for the picture of it on screen (`null` for an engine that streams its desktop alone).
 */
export type StreamStandIn = ComponentType<{ app: CatalogApp | undefined; stream: string | null }>;

/** Props of {@link Stage}. */
interface StageProps {
  /** The project's engines. */
  engines: Session[];
  /** The engine on screen, or `null` for none. */
  engine: Session | null;
  /** Puts an engine on screen. */
  onSelect: (id: string) => void;
  /** The picture of the engine on screen that is shown, by name, or `null` for its first. */
  stream: string | null;
  /** Shows another picture of the engine on screen. */
  onStream: (name: string) => void;
  /** Whether focus mode is on. */
  focus: boolean;
  /** Turns focus mode on or off. */
  onFocus: (focus: boolean) => void;
  /** Whether the panel is unfolded. */
  open: boolean;
  /** Folds or unfolds it. */
  onToggle: () => void;
  /** Mints a link to a running engine's desktop, or to the picture named. */
  link: (id: string, stream?: string) => Promise<string>;
  /** Goes to the Environment panel, to start an engine. */
  onStartEngine: () => void;
  /** Whether the layout is a narrow screen's tabs. */
  narrow: boolean;
  /** Whether the region is hidden behind another tab on a narrow screen. */
  mobileHidden: boolean;
  /** Drawn instead of the stream, where there is none to show. */
  standIn?: StreamStandIn;
  /** The versions of the piece that can take the screen, the newest first: none where no edit of one is known. */
  versions: readonly Version[];
  /** Whether the versions are on screen, in the stream's place. */
  versionsShown: boolean;
  /** Puts the versions on screen over the engine, or gives the screen back to it. */
  onVersions: (shown: boolean) => void;
  /** Leads to where a version was shown in the conversation. */
  onShowVersion: (version: Version) => void;
}

/**
 * The icon of a picture in the toggle.
 *
 * @param name The picture's name.
 * @returns A monitor for the desktop, a cube for the editor.
 */
function pictureIcon(name: string): LucideIcon {
  return name === DESKTOP_STREAM ? Monitor : Box;
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
  stream,
  onStream,
  focus,
  onFocus,
  open,
  onToggle,
  link,
  onStartEngine,
  narrow,
  mobileHidden,
  standIn,
  versions,
  versionsShown,
  onVersions,
  onShowVersion,
}: StageProps) {
  const [opening, setOpening] = useState(false);
  const [tabError, setTabError] = useState<string | null>(null);
  const [blockedLink, setBlockedLink] = useState<string | null>(null);
  const app = engine === null ? undefined : findApp(engine.app);
  const running = engine?.status === 'running';
  const pictures: EngineStream[] =
    running && engine.streams !== undefined && engine.streams.length > 1 ? engine.streams : [];
  const shown = pictures.find((picture) => picture.name === stream) ?? pictures[0] ?? null;
  const appName = app?.name ?? engine?.app ?? 'Engine';
  const pictureName = shown?.name ?? appName;
  const choices = engines.filter(isActive);
  const unfolded = open || focus || narrow;
  // By the names alone: the engine list is read again with fresh links, which must not count as
  // new pictures.
  const names = pictures.map((picture) => picture.name).join('\n');

  useEffect(() => {
    const order = names === '' ? [] : names.split('\n');
    if (order.length < 2) {
      return;
    }
    const onKey = (event: KeyboardEvent): void => {
      if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      const target = order[PICTURE_KEYS.indexOf(event.code)];
      if (target !== undefined) {
        event.preventDefault();
        onStream(target);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [names, onStream]);

  /** Opens the picture on screen in a tab of its own. */
  async function openTab(): Promise<void> {
    if (engine === null) {
      return;
    }
    setOpening(true);
    setTabError(null);
    setBlockedLink(null);
    try {
      setBlockedLink(await openStreamTab(() => link(engine.id, shown?.name), pictureName));
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
        {engine === null || !isActive(engine) ? (
          versionsShown ? (
            <span className="min-w-0 truncate text-xs text-muted">Versions</span>
          ) : null
        ) : versions.length > 0 ? (
          <div className="segmented min-w-0 flex-none" role="group" aria-label="On screen">
            <button
              type="button"
              className="segment"
              aria-pressed={versionsShown}
              onClick={() => {
                onVersions(true);
              }}
            >
              <Layers aria-hidden="true" />
              Versions
            </button>
            <button
              type="button"
              className="segment"
              aria-pressed={!versionsShown}
              onClick={() => {
                onVersions(false);
              }}
            >
              <span className={cx('dot', engineDot(engine))} aria-hidden="true" />
              <span className="truncate">{appName}</span>
            </button>
          </div>
        ) : null}
        {engine === null || versionsShown ? null : choices.length > 1 ? (
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
        ) : versions.length > 0 || (pictures.length > 0 && !focus) ? null : (
          <span className="flex min-w-0 items-center gap-1.5 truncate text-xs text-muted">
            <span className={cx('dot', engineDot(engine))} aria-hidden="true" />
            <span className="truncate">{appName}</span>
          </span>
        )}
        {pictures.length > 0 && shown !== null && !versionsShown ? (
          <PictureToggle pictures={pictures} shown={shown.name} onStream={onStream} />
        ) : null}
        <div className="ml-auto flex flex-none items-center gap-0.5">
          {running && !versionsShown ? (
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
          {narrow || (engine === null && !versionsShown) ? null : focus ? (
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

      {!unfolded ? null : versionsShown ? (
        <div className={cx('flex min-h-0 flex-1 flex-col pb-3', focus ? 'px-4 sm:px-6' : 'px-3')}>
          <VersionsScreen versions={versions} onShow={onShowVersion} />
          <p className="mt-2 text-[0.6875rem] text-faint">
            {engine !== null && isActive(engine) ? (
              <>
                Drawn from the project’s saved versions. {appName} is {running ? 'still running' : 'starting'}.{' '}
                <button
                  type="button"
                  className="link"
                  onClick={() => {
                    onVersions(false);
                  }}
                >
                  Show {appName}
                </button>
              </>
            ) : (
              'Drawn from the project’s saved versions. No engine is running for this.'
            )}
          </p>
        </div>
      ) : (
        <div className={cx('flex min-h-0 flex-1 flex-col pb-3', focus ? 'px-4 sm:px-6' : 'px-3')}>
          <div className="stream-box">
            {engine === null ? (
              <Empty engines={engines} onStartEngine={onStartEngine} />
            ) : !running ? (
              <Waiting engine={engine} appName={appName} />
            ) : pictures.length === 0 ? (
              <Stream
                key={engine.id}
                engine={engine}
                picture={null}
                label={appName}
                app={app}
                shown
                link={link}
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
              pictures.map((picture) => (
                <Stream
                  key={`${engine.id} ${picture.name}`}
                  engine={engine}
                  picture={picture}
                  label={picture.name}
                  app={app}
                  shown={picture.name === shown?.name}
                  link={link}
                  standIn={standIn}
                  interactive={focus || narrow}
                  onFocus={() => {
                    onFocus(true);
                  }}
                  onOpenTab={() => {
                    void openTab();
                  }}
                />
              ))
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
      )}
    </section>
  );
}

/** Props of {@link PictureToggle}. */
interface PictureToggleProps {
  /** The engine's pictures, in order. */
  pictures: EngineStream[];
  /** The name of the one shown. */
  shown: string;
  /** Shows another. */
  onStream: (name: string) => void;
}

/**
 * Renders the switch between an engine's pictures, each with its key in its tooltip.
 *
 * @param props The component's props.
 * @returns The toggle.
 */
function PictureToggle({ pictures, shown, onStream }: PictureToggleProps) {
  return (
    <div className="segmented flex-none" role="group" aria-label="View on screen">
      {pictures.map((picture, index) => {
        const Icon = pictureIcon(picture.name);
        const keys = `Alt+${index + 1}`;
        const chosen = picture.name === shown;
        return (
          <button
            key={picture.name}
            type="button"
            className="segment"
            aria-pressed={chosen}
            aria-keyshortcuts={keys}
            title={`${picture.name} (${keys})`}
            onClick={() => {
              onStream(picture.name);
            }}
          >
            <Icon aria-hidden="true" />
            {picture.name}
          </button>
        );
      })}
    </div>
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
      return 'dot-busy dot-live';
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
  /** The picture of it this frame loads, or `null` for an engine that streams its desktop alone. */
  picture: EngineStream | null;
  /** What the frame shows, as the person reads it: the picture's name, or the app's. */
  label: string;
  /** Whether it is the picture on screen; the others stay loaded, hidden. */
  shown: boolean;
  /** Mints a link to the engine's desktop, or to the picture named. */
  link: (id: string, stream?: string) => Promise<string>;
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
 * Renders one picture of a running engine, and what became of loading it.
 *
 * Its first load takes the link the engine's listing reported, where there is one, and a retry
 * mints a fresh one. A hidden picture keeps its frame and connection and takes no input.
 *
 * @param props The component's props.
 * @returns The picture's layer of the stream box.
 */
function Stream({
  engine,
  app,
  picture,
  label,
  shown,
  link,
  standIn: StandIn,
  interactive,
  onFocus,
  onOpenTab,
}: StreamProps) {
  const listed = picture?.url ?? null;
  const [src, setSrc] = useState<string | null>(listed);
  const [phase, setPhase] = useState<'minting' | 'loading' | 'loaded' | 'stalled' | 'failed'>(
    listed === null ? 'minting' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const name = picture?.name;
  const mint = useCallback(() => link(engine.id, name), [link, engine.id, name]);

  useEffect(() => {
    if (StandIn !== undefined || phase !== 'minting') {
      return;
    }
    let current = true;
    mint()
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
  }, [mint, attempt, phase, StandIn]);

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

  let content;
  if (StandIn !== undefined) {
    content = (
      <>
        <StandIn app={app} stream={name ?? null} />
        {interactive ? null : <FocusLayer label={label} onFocus={onFocus} />}
      </>
    );
  } else {
    content = (
      <>
        {src === null ? null : (
          <iframe
            key={src}
            src={src}
            title={`${label} stream`}
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
              Connecting to {label}…
            </p>
          </div>
        ) : null}
        {phase === 'stalled' || phase === 'failed' ? (
          <div className="absolute inset-0 grid place-items-center bg-ink-950/85 p-5 text-center backdrop-blur-sm">
            <div className="max-w-xs">
              <p className="text-sm font-medium">
                {phase === 'failed' ? `Could not open ${label}` : `${label} is not loading here`}
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
        {interactive || phase !== 'loaded' ? null : <FocusLayer label={label} onFocus={onFocus} />}
      </>
    );
  }
  return (
    <div className="stream-picture" data-shown={shown} inert={!shown} aria-hidden={!shown}>
      {content}
    </div>
  );
}

/** Props of {@link FocusLayer}. */
interface FocusLayerProps {
  /** What the stream shows. */
  label: string;
  /** Enters focus mode. */
  onFocus: () => void;
}

/**
 * Renders the layer over the small stream that a click turns into focus mode.
 *
 * @param props The component's props.
 * @returns The layer.
 */
function FocusLayer({ label, onFocus }: FocusLayerProps) {
  return (
    <button type="button" className="stream-focus-layer" aria-label={`Focus on ${label}`} onClick={onFocus}>
      <span className="flex items-center gap-2 rounded-full border border-white/20 bg-ink-950/70 px-3.5 py-1.5 text-xs font-semibold backdrop-blur">
        <Maximize2 className="size-3.5" aria-hidden="true" />
        Work in {label}
      </span>
    </button>
  );
}
