/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The tracks of a version of a video: its edit laid out as lanes on the version's own timeline.
 *
 * A version's edit (`VersionEdit`) says what that version changed, each change with its kind and
 * the time it sits at in the new video. One version's changes alone are a sparse picture of a
 * video: the second version of a cut may record a single caption. So the tracks of a version are
 * built from every version up to it ({@link tracksOf}): what the earlier ones made is carried
 * forward and what this one changed is laid over it, marked as its own.
 *
 * Carrying forward follows three rules. A cut moves what came after it: a version's cuts are
 * recorded at their place in the new video with the time they removed, so a time of the version
 * before maps to this one by taking off every cut before it, and a span that sat wholly inside a
 * cut is gone ({@link through}). A change replaces what it changed: an earlier block of the same
 * lane, made by the same file, that the new one overlaps, gives way to it; a change recorded
 * with no span, which is one to the whole video, takes the span of what it changed where there
 * is such a block and fills the lane where there is none. And a version that restored an earlier
 * one (recorded as `restore v3`) has that version's tracks, since everything after it was undone.
 *
 * The result is as exact as the record. A version the agent saved and never showed is not among
 * the versions here, so its cuts move nothing, and a block's place is then off by what it cut.
 *
 * Blocks of a lane that overlap are stacked in rows ({@link packed}), up to {@link ROWS}.
 * @module
 */
import type { EditChange, EditKind, VersionEdit } from '../lib/api';

/** The lanes of the timeline, top to bottom: picture over sound, as an editor lays tracks out. */
export const LANES = [
  { id: 'text', name: 'Text' },
  { id: 'captions', name: 'Captions' },
  { id: 'graphics', name: 'Graphics' },
  { id: 'video', name: 'Video' },
  { id: 'voice', name: 'Voice' },
  { id: 'music', name: 'Music' },
  { id: 'sfx', name: 'Effects' },
  { id: 'cut', name: 'Cuts' },
  { id: 'other', name: 'Other' },
] as const;

/** One lane, by identifier: a kind of change, or `other` for a change with none. */
export type LaneId = (typeof LANES)[number]['id'];

/** The most rows a lane stacks its blocks in; blocks past them share the last. */
const ROWS = 3;

/** The time a block at a moment is taken to fill when rows are given, in seconds: its mark has a width. */
const MOMENT = 0.001;

/** What a version records itself as when it restored an earlier one. */
const RESTORED = /^restore (v\d+)$/u;

/** One block on a lane: something a version made or changed, at its place in the version on screen. */
export interface Block {
  /** A key of its own among the blocks. */
  key: string;
  /** Where it starts, in seconds. */
  from: number;
  /** Where it ends, in seconds: `from` again for something at a moment. */
  to: number;
  /** Whether it was recorded with no span, as a change to the whole video. */
  whole: boolean;
  /** What changed, in the person's words. */
  text: string;
  /** The file that makes it, or `null` where none was recorded. */
  src: string | null;
  /** The label of the version that made it. */
  by: string;
  /** Whether the version on screen made it, rather than one before it. */
  fresh: boolean;
  /** How much time a cut removed, in seconds, or `null` for a block that is no cut. */
  removed: number | null;
  /** Whether it was added or moved in time, or `null` where neither was recorded. */
  type: NonNullable<EditChange['type']> | null;
  /** The row of its lane it is drawn in, from 0. */
  row: number;
}

/** One lane with what is on it. */
export interface Lane {
  /** The lane. */
  id: LaneId;
  /** Its name. */
  name: string;
  /** How many rows its blocks take. */
  rows: number;
  /** Its blocks, in the order to draw them. */
  blocks: Block[];
}

/** A version whose edit is known, as the tracks are built from it. */
export interface Tracked {
  /** What the version is called. */
  label: string;
  /** Its edit. */
  edit: VersionEdit;
}

/** A block before its lane has given it a row. */
type Loose = Omit<Block, 'row'> & { lane: LaneId };

/** A cut of a version: where it sits in the new video, and the time it removed. */
interface Cut {
  /** Its place in the new video, in seconds. */
  at: number;
  /** The time it removed, in seconds. */
  removed: number;
}

/**
 * The lane a kind of change is drawn on.
 *
 * @param kind The change's kind, if it has one.
 * @returns The lane.
 */
function laneOf(kind: EditKind | undefined): LaneId {
  return kind ?? 'other';
}

/**
 * Maps a time of the version before to the version that made the cuts.
 *
 * @param cuts The version's cuts, in the order of their places.
 * @param time The time in the version before, in seconds.
 * @returns The time in the new version, and whether a cut removed that moment: it is then the
 * cut's own place.
 */
function through(cuts: readonly Cut[], time: number): { at: number; gone: boolean } {
  let taken = 0;
  for (const cut of cuts) {
    // Where the cut began in the version before: its place now, with what earlier cuts took put back.
    const began = cut.at + taken;
    if (time < began) {
      break;
    }
    if (time < began + cut.removed) {
      return { at: cut.at, gone: true };
    }
    taken += cut.removed;
  }
  return { at: time - taken, gone: false };
}

/**
 * Whether two blocks share any time; one to the whole video shares time with every other.
 *
 * @param one A block.
 * @param other Another.
 * @returns Whether they overlap.
 */
function overlaps(one: Loose, other: Loose): boolean {
  return one.whole || other.whole || (one.from <= other.to && other.from <= one.to);
}

/**
 * The blocks of a version on its own timeline, without rows: what the versions before it left,
 * and what it changed.
 *
 * @param history The versions whose edits are known, the oldest first.
 * @param index The version's place among them.
 * @returns Its blocks.
 */
function blocksAt(history: readonly Tracked[], index: number): Loose[] {
  const version = history[index];
  if (version === undefined) {
    return [];
  }
  const restored = RESTORED.exec(version.edit.message)?.[1];
  const source = restored === undefined ? -1 : history.findIndex((one, at) => at < index && one.label === restored);
  if (source >= 0) {
    return blocksAt(history, source).map((block) => ({ ...block, fresh: false }));
  }
  const cuts: Cut[] = version.edit.changes
    .flatMap((change) =>
      change.kind === 'cut' && change.from !== undefined && change.removed !== undefined
        ? [{ at: change.from, removed: change.removed }]
        : [],
    )
    .sort((one, other) => one.at - other.at);
  const carried = blocksAt(history, index - 1).flatMap((block): Loose[] => {
    if (block.lane === 'cut') {
      return [];
    }
    if (block.whole) {
      return [{ ...block, fresh: false }];
    }
    const from = through(cuts, block.from);
    const to = through(cuts, block.to);
    // Both ends inside one cut: nothing of it is left.
    if (from.gone && to.gone && from.at === to.at) {
      return [];
    }
    return [{ ...block, from: from.at, to: Math.max(from.at, to.at), fresh: false }];
  });
  const own = version.edit.changes.map((change, place): Loose => {
    const spanned = change.from !== undefined && change.to !== undefined;
    return {
      key: `${version.label}:${place}`,
      lane: laneOf(change.kind),
      from: change.from ?? 0,
      to: change.to ?? 0,
      whole: !spanned,
      text: change.text,
      src: change.src ?? null,
      by: version.label,
      fresh: true,
      removed: change.kind === 'cut' ? (change.removed ?? null) : null,
      type: change.type ?? null,
    };
  });
  const changed = (old: Loose, now: Loose): boolean => now.lane === old.lane && now.src === old.src && overlaps(now, old);
  const made: Loose[] = [];
  for (const now of own) {
    const before = now.whole ? carried.filter((old) => !old.whole && changed(old, now)) : [];
    if (before.length === 0) {
      made.push(now);
      continue;
    }
    // A change to the whole video takes the spans of what it changed.
    before.forEach((old, place) => {
      made.push({ ...now, key: `${now.key}:${place}`, from: old.from, to: old.to, whole: false });
    });
  }
  return [...carried.filter((old) => !own.some((now) => changed(old, now))), ...made];
}

/**
 * Gives the blocks of one lane their rows: each the first row whose last block ended before it
 * starts, so blocks that overlap sit under one another.
 *
 * @param blocks The lane's blocks.
 * @returns The blocks with rows, and how many rows they take.
 */
function packed(blocks: readonly Loose[]): { blocks: Block[]; rows: number } {
  const ends: number[] = [];
  const placed = [...blocks]
    .sort((one, other) => Number(other.whole) - Number(one.whole) || one.from - other.from)
    .map((block): Block => {
      const free = block.whole ? -1 : ends.findIndex((end) => end <= block.from);
      const row = free >= 0 ? free : Math.min(ends.length, ROWS - 1);
      ends[row] = block.whole ? Number.POSITIVE_INFINITY : Math.max(ends[row] ?? 0, block.to, block.from + MOMENT);
      return { ...block, row };
    });
  return { blocks: placed, rows: Math.max(1, ends.length) };
}

/**
 * Lays out the tracks of one version.
 *
 * @param history The versions whose edits are known, the oldest first.
 * @param index The place among them of the version to lay out.
 * @returns Its lanes that hold anything, top to bottom.
 */
export function tracksOf(history: readonly Tracked[], index: number): Lane[] {
  const blocks = blocksAt(history, index);
  return LANES.flatMap((lane) => {
    const mine = blocks.filter((block) => block.lane === lane.id);
    return mine.length === 0 ? [] : [{ id: lane.id, name: lane.name, ...packed(mine) }];
  });
}

/**
 * How long the tracks of a version run, where the file itself does not say.
 *
 * @param lanes The version's lanes.
 * @returns The end of the last block, in seconds; 0 for none.
 */
export function tracksEnd(lanes: readonly Lane[]): number {
  return Math.max(0, ...lanes.flatMap((lane) => lane.blocks.map((block) => block.to)));
}
