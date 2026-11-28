/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The versions of a video on the Screen: a version playing over the tracks of its edit, with the
 * other versions one press away and any two side by side.
 *
 * It is drawn by the page from the conversation's log alone. A version is a `preview` the agent
 * called one, and where the project's versions are kept with v2, the file of that preview
 * carries what the version changed (`VersionEdit`, read from the engine once, when the agent
 * showed it). So nothing here asks an engine for anything: the file plays from storage and the
 * tracks are laid out in the browser (`tracks.ts`), which is the same picture the engine's own
 * versions page gives at none of its cost. The engine's stream takes the Screen's place when one
 * is put on screen (`Stage.tsx`).
 *
 * The tracks are lanes by kind of change, picture over sound, on the version's own timeline. A
 * block is something a version made or changed: lit where the version on screen made it, quiet
 * where it is carried from an earlier one, and a press on it plays from there. The lanes for
 * voice, music, and effects draw the file's sound inside their blocks, and a lane of its own
 * shows the sound of the whole file, from the bars kept with the version. A version with no
 * edit recorded still plays; it has no tracks to draw, and says so.
 *
 * The file plays in the browser's own player, so its controls are the ones the person knows.
 * The page only follows that player's clock ({@link usePlayerClock}) to place the playhead, and
 * moves it when the ruler or a block is pressed. The playhead is moved by the stylesheet between
 * two readings of the clock, so no script runs per frame while a version plays.
 *
 * Comparing puts an earlier or later version beside the one on screen. The second player has no
 * controls and no sound: at each reading of the first one's clock it is set to play, pause, and
 * stand where the first does, at the same time on the clock, which is the same moment of the
 * piece only up to the first cut that differs.
 * @module
 */
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { Download, MessageSquare } from 'lucide-react';
import { downloadAddress } from '../lib/api';
import { shortDateTime } from '../lib/format';
import { MediaView } from './MediaView';
import { tracksEnd, tracksOf, type Block, type Lane, type LaneId, type Tracked } from './tracks';
import type { Version } from './transcript';

/** The lanes whose blocks draw the file's sound inside them. */
const SOUND_LANES: readonly LaneId[] = ['voice', 'music', 'sfx'];

/** The steps a ruler may count in, in seconds, the smallest that leaves it readable winning. */
const TICK_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];

/** The most labels a ruler carries. */
const TICKS = 6;

/** How far the keys move the playhead, in seconds: an arrow, and a page key. */
const KEY_STEP = 1;
const PAGE_STEP = 10;

/** How far the second player of a comparison may drift from the first before it is set again, in seconds. */
const DRIFT = 0.25;

/** The events of a player after which its clock is read again. */
const CLOCK_EVENTS = [
  'timeupdate',
  'seeking',
  'seeked',
  'loadedmetadata',
  'durationchange',
  'ratechange',
  'play',
  'pause',
  'ended',
] as const;

/**
 * Writes a time in a video.
 *
 * @param seconds The time; a negative one reads as zero.
 * @returns Text such as `0:03.4`, with the tenth only where there is one.
 */
function stamp(seconds: number): string {
  const tenths = Math.max(0, Math.round(seconds * 10));
  const minutes = Math.floor(tenths / 600);
  const rest = tenths - minutes * 600;
  const whole = `${minutes}:${String(Math.floor(rest / 10)).padStart(2, '0')}`;
  return rest % 10 === 0 ? whole : `${whole}.${rest % 10}`;
}

/** A reading of a player's clock. */
interface Clock {
  /** Where the player is, in seconds. */
  time: number;
  /** How long its file runs, in seconds; 0 until the file says. */
  length: number;
  /** Whether it is playing. */
  playing: boolean;
  /** How fast it plays, as a share of the file's own speed. */
  rate: number;
}

/** The clock of a player that has reported nothing yet. */
const AT_REST: Clock = { time: 0, length: 0, playing: false, rate: 1 };

/**
 * Follows a player's clock.
 *
 * The clock is read when the player reports that it moved, started, or stopped
 * ({@link CLOCK_EVENTS}), a few times a second while it plays, and never in between: a reading
 * taken at every render would differ from the last one whenever the file is playing and so
 * render again without end. A reading belongs to the player it was taken from, so a new player
 * is at rest until it reports.
 *
 * @param player The element that plays, or `null` before there is one.
 * @returns The player's last reading.
 */
function usePlayerClock(player: HTMLMediaElement | null): Clock {
  const [read, setRead] = useState<(Clock & { of: HTMLMediaElement }) | null>(null);
  useEffect(() => {
    if (player === null) {
      return;
    }
    const changed = (): void => {
      setRead({
        of: player,
        time: player.currentTime,
        length: Number.isFinite(player.duration) ? player.duration : 0,
        playing: !player.paused && !player.ended,
        rate: player.playbackRate,
      });
    };
    for (const name of CLOCK_EVENTS) {
      player.addEventListener(name, changed);
    }
    return () => {
      for (const name of CLOCK_EVENTS) {
        player.removeEventListener(name, changed);
      }
    };
  }, [player]);
  return read !== null && read.of === player ? read : AT_REST;
}

/**
 * What a version is called on the Screen.
 *
 * @param version The version.
 * @returns Its label, or words for the file that stands in where the agent named none.
 */
function nameOf(version: Version): string {
  return version.label ?? 'The newest shown';
}

/** Props of {@link VersionsScreen}. */
interface VersionsScreenProps {
  /** The versions the session showed, the newest first; at least one. */
  versions: readonly Version[];
  /** Leads to where a version was shown in the conversation. */
  onShow: (version: Version) => void;
}

/**
 * Renders the versions: the one on screen over its tracks, and the way to the others.
 *
 * @param props The component's props.
 * @returns The Screen's body, or nothing while there is no version.
 */
export function VersionsScreen({ versions, onShow }: VersionsScreenProps) {
  // The version pressed stays on screen until a newer one arrives, which the newest's key tells.
  const [picked, setPicked] = useState<{ key: string; newest: string } | null>(null);
  const [against, setAgainst] = useState<string | null>(null);
  // The player is held twice: as state, whose change subscribes the clock to a new element, and
  // in a ref, through which the page moves it.
  const [player, setPlayer] = useState<HTMLMediaElement | null>(null);
  const playerRef = useRef<HTMLMediaElement | null>(null);
  const secondRef = useRef<HTMLVideoElement | null>(null);
  const takePlayer = useCallback((element: HTMLMediaElement | null): void => {
    playerRef.current = element;
    setPlayer(element);
  }, []);
  const clock = usePlayerClock(player);

  // The versions whose edits are known, the oldest first; a version shown twice counts as it was last shown.
  const history = useMemo(() => {
    const known = new Map<string, Tracked>();
    for (const version of [...versions].reverse()) {
      if (version.edit !== null && version.label !== null) {
        known.delete(version.label);
        known.set(version.label, { label: version.label, edit: version.edit });
      }
    }
    return [...known.values()];
  }, [versions]);

  const newest = versions[0];
  const shown =
    (picked?.newest === newest?.key ? versions.find((version) => version.key === picked?.key) : undefined) ?? newest;
  const place = shown === undefined || shown.edit === null ? -1 : history.findIndex((one) => one.label === shown.label);
  const lanes = useMemo(() => (place < 0 ? [] : tracksOf(history, place)), [history, place]);
  const other =
    against === null || shown?.media.kind !== 'video'
      ? undefined
      : versions.find((version) => version.key === against && version.key !== shown.key && version.media.kind === 'video');
  const otherKey = other?.key ?? null;
  // The second player of a comparison follows each reading of the first one's clock.
  useEffect(() => {
    const follower = secondRef.current;
    if (follower === null || otherKey === null) {
      return;
    }
    follower.playbackRate = clock.rate;
    if (Math.abs(follower.currentTime - clock.time) > DRIFT) {
      follower.currentTime = clock.time;
    }
    if (!clock.playing) {
      follower.pause();
    } else if (follower.paused) {
      follower.play().catch(() => {
        // Refused by the browser, or its file is gone: the first player goes on alone.
      });
    }
  }, [clock, otherKey]);
  if (newest === undefined || shown === undefined) {
    return null;
  }
  const seconds = shown.seconds ?? (clock.length > 0 ? clock.length : tracksEnd(lanes));
  const at = seconds > 0 ? Math.min(1, clock.time / seconds) : 0;
  const carried = lanes.some((lane) => lane.blocks.some((block) => !block.fresh));
  const others = versions.filter((version) => version.key !== shown.key && version.media.kind === 'video');

  /** Moves the player to a time. */
  const seek = (time: number): void => {
    if (playerRef.current !== null) {
      playerRef.current.currentTime = Math.min(Math.max(0, time), seconds);
    }
  };
  /** Moves the player by a span from where it is now, which the last reading of its clock may be behind. */
  const step = (by: number): void => {
    if (playerRef.current !== null) {
      seek(playerRef.current.currentTime + by);
    }
  };

  return (
    <div className="versions-screen thin-scroll">
      <div
        className="versions-view"
        data-kind={shown.media.kind}
        data-compare={other !== undefined}
        style={{
          '--versions-shape': Math.min(16 / 9, Math.max(1, shown.aspect ?? 16 / 9)) * (other === undefined ? 1 : 2),
        }}
      >
        {other === undefined ? null : (
          <figure className="versions-side">
            <video
              key={other.key}
              ref={secondRef}
              src={other.media.url}
              muted
              playsInline
              preload="metadata"
              aria-label={`${nameOf(other)}, playing beside ${nameOf(shown)} with no sound`}
            />
            <figcaption>{nameOf(other)}</figcaption>
          </figure>
        )}
        <figure className="versions-side">
          <MediaView
            key={shown.key}
            media={shown.media}
            label={nameOf(shown)}
            className={shown.media.kind === 'audio' ? 'm-3 self-center' : 'size-full'}
            onPlayer={takePlayer}
          />
          {other === undefined ? null : <figcaption>{nameOf(shown)}</figcaption>}
        </figure>
      </div>

      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold tracking-tight">
            {nameOf(shown)}
            {shown.edit === null || shown.edit.message === '' ? null : (
              <span className="font-normal text-soft"> · {shown.edit.message}</span>
            )}
            {shown === newest ? null : <span className="font-normal text-faint"> · an earlier version</span>}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted">{shown.caption}</p>
        </div>
        <button
          type="button"
          className="icon-btn icon-btn-sm"
          aria-label="Show it in the conversation"
          title="Show it in the conversation"
          onClick={() => {
            onShow(shown);
          }}
        >
          <MessageSquare aria-hidden="true" />
        </button>
        <a
          className="icon-btn icon-btn-sm"
          href={downloadAddress(shown.media)}
          download={shown.media.name ?? ''}
          aria-label="Download"
          title="Download"
        >
          <Download aria-hidden="true" />
        </a>
      </div>

      {versions.length < 2 ? null : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="segmented max-w-full flex-wrap" role="group" aria-label="Version on screen">
            {[...versions].reverse().map((version) => (
              <button
                key={version.key}
                type="button"
                className="segment"
                aria-pressed={version === shown}
                title={version.edit?.message === undefined || version.edit.message === '' ? version.caption : version.edit.message}
                onClick={() => {
                  setPicked(version === newest ? null : { key: version.key, newest: newest.key });
                }}
              >
                {nameOf(version)}
              </button>
            ))}
          </div>
          {others.length === 0 || shown.media.kind !== 'video' ? null : (
            <label className="flex items-center gap-2 text-xs text-muted">
              Compare with
              <select
                className="field field-sm h-7 w-auto min-w-0 py-0 pr-7 pl-2 text-xs"
                value={other?.key ?? ''}
                onChange={(event) => {
                  setAgainst(event.target.value === '' ? null : event.target.value);
                }}
              >
                <option value="">Nothing</option>
                {others.map((version) => (
                  <option key={version.key} value={version.key}>
                    {nameOf(version)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}

      {shown.edit === null ? (
        <p className="text-xs leading-relaxed text-faint">
          No edit was recorded for this version, so it has no tracks to draw. It plays as it is.
        </p>
      ) : seconds <= 0 ? null : (
        <Tracks
          lanes={lanes}
          sound={shown.edit.sound ?? null}
          seconds={seconds}
          time={clock.time}
          at={at}
          playing={clock.playing}
          onSeek={seek}
          onStep={step}
          shownLabel={nameOf(shown)}
          carried={carried}
        />
      )}

      {shown.edit === null || shown.edit.prompts.length === 0 ? null : (
        <div>
          <h3 className="section-label">
            You asked
            {shown.edit.saved_at === undefined ? null : (
              <span className="font-normal tracking-normal normal-case"> · saved {shortDateTime(shown.edit.saved_at)}</span>
            )}
          </h3>
          <ul className="mt-1.5 grid grid-cols-1 gap-1 text-xs leading-relaxed text-soft">
            {shown.edit.prompts.map((prompt, index) => (
              <li key={index} className="border-l border-line-strong pl-2">
                {prompt}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Props of {@link Tracks}. */
interface TracksProps {
  /** The version's lanes that hold anything, top to bottom. */
  lanes: readonly Lane[];
  /** The bars of the file's sound, from 0 to 100, or `null` for a file with none. */
  sound: readonly number[] | null;
  /** How long the version runs, in seconds; more than 0. */
  seconds: number;
  /** Where the player is, in seconds. */
  time: number;
  /** The same as a share of the length, from 0 to 1. */
  at: number;
  /** Whether the player is playing. */
  playing: boolean;
  /** Moves the player to a time, in seconds. */
  onSeek: (time: number) => void;
  /** Moves the player by a span from where it is, in seconds. */
  onStep: (by: number) => void;
  /** What the version on screen is called. */
  shownLabel: string;
  /** Whether any block is carried from an earlier version, which the legend then explains. */
  carried: boolean;
}

/**
 * Renders the timeline of a version: a ruler that moves the player, a lane for each kind of
 * change the version holds, the file's sound, and the playhead over all of them.
 *
 * @param props The component's props.
 * @returns The timeline.
 */
function Tracks({ lanes, sound, seconds, time, at, playing, onSeek, onStep, shownLabel, carried }: TracksProps) {
  const step = TICK_STEPS.find((size) => seconds / size <= TICKS) ?? seconds;
  const ticks = Array.from({ length: Math.floor(seconds / step) + 1 }, (_, index) => index * step);

  /** Moves the player to where the pointer is on the ruler. */
  const point = (event: PointerEvent<HTMLDivElement>): void => {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width > 0) {
      onSeek(((event.clientX - box.left) / box.width) * seconds);
    }
  };
  /** Moves the player by the keys a slider answers to. */
  const key = (event: KeyboardEvent<HTMLDivElement>): void => {
    const steps: Readonly<Record<string, number>> = {
      ArrowLeft: -KEY_STEP,
      ArrowDown: -KEY_STEP,
      ArrowRight: KEY_STEP,
      ArrowUp: KEY_STEP,
      PageDown: -PAGE_STEP,
      PageUp: PAGE_STEP,
    };
    const by = steps[event.key];
    if (by !== undefined) {
      event.preventDefault();
      onStep(by);
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      onSeek(event.key === 'Home' ? 0 : seconds);
    }
  };

  return (
    <div>
      <div className="tracks" data-playing={playing}>
        <span className="tracks-name" aria-hidden="true" />
        <div
          className="tracks-ruler"
          role="slider"
          tabIndex={0}
          aria-label="Position in the version"
          aria-valuemin={0}
          aria-valuemax={Math.round(seconds)}
          aria-valuenow={Math.round(time)}
          aria-valuetext={`${stamp(time)} of ${stamp(seconds)}`}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            point(event);
          }}
          onPointerMove={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) {
              point(event);
            }
          }}
          onKeyDown={key}
        >
          {ticks.map((tick) => (
            <span key={tick} className="tracks-tick" style={{ left: `${(tick / seconds) * 100}%` }}>
              {stamp(tick)}
            </span>
          ))}
        </div>
        {lanes.map((lane) => (
          <LaneRow key={lane.id} lane={lane} sound={sound} seconds={seconds} onSeek={onSeek} shownLabel={shownLabel} />
        ))}
        {sound === null ? null : (
          <>
            <span className="tracks-name">Sound</span>
            <div className="tracks-lane" data-lane="sound" style={{ height: '1.75rem' }}>
              <Waveform bars={sound} from={0} to={1} />
            </div>
          </>
        )}
        <div className="tracks-over" aria-hidden="true">
          <span className="tracks-playhead" style={{ left: `${at * 100}%` }} />
        </div>
      </div>
      {carried ? (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.6875rem] text-faint">
          <span className="flex items-center gap-1.5">
            <span className="tracks-key" data-fresh="true" aria-hidden="true" />
            Changed in {shownLabel}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="tracks-key" data-fresh="false" aria-hidden="true" />
            From an earlier version
          </span>
        </p>
      ) : null}
    </div>
  );
}

/** Props of {@link LaneRow}. */
interface LaneRowProps {
  /** The lane. */
  lane: Lane;
  /** The bars of the file's sound, or `null` for a file with none. */
  sound: readonly number[] | null;
  /** How long the version runs, in seconds. */
  seconds: number;
  /** Moves the player to a time, in seconds. */
  onSeek: (time: number) => void;
  /** What the version on screen is called. */
  shownLabel: string;
}

/**
 * Renders one lane: its name, and its blocks at their places, each a control that plays from it.
 *
 * @param props The component's props.
 * @returns The lane's two cells of the timeline's grid.
 */
function LaneRow({ lane, sound, seconds, onSeek, shownLabel }: LaneRowProps) {
  return (
    <>
      <span className="tracks-name">{lane.name}</span>
      <div className="tracks-lane" data-lane={lane.id} style={{ height: `${lane.rows * 1.5}rem` }}>
        {lane.blocks.map((block) => {
          const from = block.whole ? 0 : Math.min(1, block.from / seconds);
          const to = block.whole ? 1 : Math.min(1, block.to / seconds);
          return (
            <button
              key={block.key}
              type="button"
              className="tracks-block"
              data-fresh={block.fresh}
              data-moment={to <= from}
              style={{
                left: `${from * 100}%`,
                top: `${block.row * 1.5}rem`,
                ...(to > from ? { width: `${(to - from) * 100}%` } : {}),
              }}
              title={describe(block, lane.name, shownLabel)}
              aria-label={describe(block, lane.name, shownLabel)}
              onClick={() => {
                onSeek(block.whole ? 0 : block.from);
              }}
            >
              {sound !== null && SOUND_LANES.includes(lane.id) && to > from ? (
                <Waveform bars={sound} from={from} to={to} />
              ) : null}
              <span className="tracks-text">
                {block.removed === null ? block.text : `−${stamp(block.removed)} · ${block.text}`}
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
}

/**
 * Words a block for its tooltip and for a screen reader.
 *
 * @param block The block.
 * @param lane The name of its lane.
 * @param shownLabel What the version on screen is called.
 * @returns The lane, where the block sits, what it is, and the version that made it where that
 * is not the one on screen.
 */
function describe(block: Block, lane: string, shownLabel: string): string {
  const where = block.whole
    ? 'the whole video'
    : block.to > block.from
      ? `${stamp(block.from)} to ${stamp(block.to)}`
      : stamp(block.from);
  const removed = block.removed === null ? '' : `, ${stamp(block.removed)} removed`;
  const type = block.type === null ? '' : `, ${block.type}`;
  const by = block.by === shownLabel ? '' : `, from ${block.by}`;
  return `${lane}, ${where}${removed}${type}: ${block.text}${by}`;
}

/** Props of {@link Waveform}. */
interface WaveformProps {
  /** The bars of the whole file's sound, from 0 to 100. */
  bars: readonly number[];
  /** Where the part to draw starts, as a share of the file from 0 to 1. */
  from: number;
  /** Where it ends. */
  to: number;
}

/**
 * Renders a part of the file's sound as a waveform that fills its box.
 *
 * @param props The component's props.
 * @returns The drawing, or nothing for a part too short to hold a bar.
 */
function Waveform({ bars, from, to }: WaveformProps) {
  const first = Math.floor(from * bars.length);
  const part = bars.slice(first, Math.max(first + 1, Math.ceil(to * bars.length)));
  if (part.length === 0) {
    return null;
  }
  // Each bar is a line through the middle, as tall as its level; a silent one keeps a hair so the track reads as one.
  const path = part
    .map((level, index) => {
      const half = Math.max(1, level / 2);
      return `M${index + 0.5} ${50 - half}V${50 + half}`;
    })
    .join('');
  return (
    <svg
      className="tracks-wave"
      viewBox={`0 0 ${part.length} 100`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <path d={path} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
