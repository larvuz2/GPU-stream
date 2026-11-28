/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The pixel loaders: six small animations on a 5 by 5 grid, each a way of saying that something
 * is at work.
 *
 * A loader is a pattern, not a program. For every cell this module says whether it is part of
 * the pattern, which keyframes it plays (`styles.css`), how long one loop takes, and how far into
 * the loop it starts; the motion is those few keyframes played by the cells out of step with one
 * another. The browser runs it, so a loader costs no script while it plays and a page can hold as
 * many as there are subagents, which a canvas redrawn each frame could not say.
 *
 * Bit Flip lights the four corners in turn. Pixel Snake runs a fading tail around the edge.
 * Square Bloom opens from the center and closes. Bit Shuffle steps through eight scattered
 * frames. Pixel Clock sweeps a hand around a lit hub. Matrix Rain drops columns out of step.
 *
 * A subagent is given one of the six when it starts and keeps it. The choice is read from the
 * group it started in and its place there ({@link loaderStyle}), and where in its loop a loader
 * starts from the subagent's own identifier ({@link loaderOffset}), so the members of a group
 * differ from one another and move out of step, and a card drawn again (a reload, a project opened
 * a second time) shows the loader it showed before. Drawing a number each time a card mounts would
 * change a subagent's loader under the person's eyes.
 * @module
 */

/** The six loaders, by identifier. */
export const LOADER_STYLES = [
  'bit-flip',
  'pixel-snake',
  'square-bloom',
  'bit-shuffle',
  'pixel-clock',
  'matrix-rain',
] as const;

/** One of the six loaders. */
export type LoaderStyle = (typeof LOADER_STYLES)[number];

/** How a pixel moves between two keyframes: a step holds each until the next. */
type Timing = 'steps(1, end)' | 'linear';

/** One cell of a loader's grid, as the page draws it. */
export interface LoaderCell {
  /** The cell's place in the grid, counted along the rows. */
  index: number;
  /** Whether the cell is part of the pattern. One that is not keeps its place, unseen. */
  visible: boolean;
  /** The keyframes the pixel plays, or `null` for one that holds still. */
  keyframes: string | null;
  /** How long one loop takes, in seconds at full speed. */
  seconds: number;
  /** How far into its loop the pixel starts, in seconds at full speed: negative for one under way. */
  delay: number;
  /** How the pixel moves between two keyframes. */
  timing: Timing;
  /** The opacities the keyframes read, in order, where the cells of a style do not share them. */
  levels: readonly number[];
  /** The opacity of a pixel that holds still, or `null` for the grid's own. */
  opacity: number | null;
}

/** The cells along one side of the grid. */
const SIDE = 5;

/** The row and the column of the grid's center. */
const CENTER = 2;

/** The longest a loader's start is put off, in seconds at full speed: longer than any loop. */
const OFFSET_SECONDS = 3;

/** A cell before its style says anything about it: seen, still, and at the grid's own opacity. */
const REST: Omit<LoaderCell, 'index'> = {
  visible: true,
  keyframes: null,
  seconds: 1,
  delay: 0,
  timing: 'steps(1, end)',
  levels: [],
  opacity: null,
};

/** Pixel Snake's path: the grid's edge, clockwise from the top left, as column and row. */
const RING: readonly (readonly [number, number])[] = [
  [0, 0],
  [1, 0],
  [2, 0],
  [3, 0],
  [4, 0],
  [4, 1],
  [4, 2],
  [4, 3],
  [4, 4],
  [3, 4],
  [2, 4],
  [1, 4],
  [0, 4],
  [0, 3],
  [0, 2],
  [0, 1],
];

/** Pixel Clock's hands: the eight directions from the center, clockwise from twelve. */
const DIRECTIONS: readonly (readonly [number, number])[] = [
  [0, -1],
  [1, -1],
  [1, 0],
  [1, 1],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [-1, -1],
];

/** Bit Shuffle's eight frames, each the cells that are lit. */
const SHUFFLE_FRAMES: readonly (readonly number[])[] = [
  [0, 1, 5, 6, 18, 19, 23, 24],
  [3, 4, 8, 9, 15, 16, 20, 21],
  [6, 7, 8, 11, 13, 16, 17, 18],
  [2, 7, 10, 11, 12, 13, 14, 17, 22],
  [0, 4, 6, 8, 12, 16, 18, 20, 24],
  [1, 2, 3, 10, 12, 14, 21, 22, 23],
  [0, 1, 5, 6, 8, 9, 13, 14, 17, 22],
  [2, 6, 7, 8, 10, 11, 13, 14, 16, 17, 18, 22],
];

/** The stages Square Bloom opens through: the center, the ring around it, and the edge. */
const BLOOM_STAGES = [0, 1, 2] as const;

/** A cell outside its style's pattern. */
const UNSEEN: Partial<LoaderCell> = { visible: false };

/** What each style says about the cell at a column and a row. */
const PATTERNS: Readonly<Record<LoaderStyle, (x: number, y: number) => Partial<LoaderCell>>> = {
  'bit-flip': (x, y) => {
    if (x === CENTER || y === CENTER) {
      return UNSEEN;
    }
    // The corners take their turn clockwise from the top left, a quarter of the loop apart.
    const corner = y < CENTER ? (x < CENTER ? 0 : 1) : x < CENTER ? 3 : 2;
    return { keyframes: 'pixel-bit-flip', delay: -corner / 4 };
  },
  'pixel-snake': (x, y) => {
    const place = RING.findIndex(([column, row]) => column === x && row === y);
    if (place < 0) {
      return UNSEEN;
    }
    const steps = RING.length;
    return { keyframes: 'pixel-snake', seconds: steps / 12, delay: -((steps - place) % steps) / 12 };
  },
  'square-bloom': (x, y) => {
    const distance = Math.max(Math.abs(x - CENTER), Math.abs(y - CENTER));
    return {
      keyframes: 'pixel-bloom',
      levels: BLOOM_STAGES.map((stage) => (distance === stage ? 1 : distance < stage ? 0.3 : 0)),
    };
  },
  'bit-shuffle': (x, y) => ({
    keyframes: 'pixel-shuffle',
    seconds: 1.6,
    levels: SHUFFLE_FRAMES.map((frame) => (frame.includes(y * SIDE + x) ? 1 : 0)),
  }),
  'pixel-clock': (x, y) => {
    const dx = x - CENTER;
    const dy = y - CENTER;
    if (dx === 0 && dy === 0) {
      return { opacity: 1 };
    }
    const hand = DIRECTIONS.findIndex(([a, b]) => (dx === a && dy === b) || (dx === a * 2 && dy === b * 2));
    if (hand < 0) {
      return UNSEEN;
    }
    const hands = DIRECTIONS.length;
    return { keyframes: 'pixel-clock', seconds: hands / 6, delay: -((hands - hand) % hands) / 6, timing: 'linear' };
  },
  'matrix-rain': (x, y) => ({ keyframes: 'pixel-rain', delay: (y - x * 2 - (x % 2) * 3) / 7 }),
};

/**
 * Builds the grid of one style.
 *
 * @param style The loader.
 * @returns Its 25 cells, along the rows.
 */
function cellsOf(style: LoaderStyle): readonly LoaderCell[] {
  const cells: LoaderCell[] = [];
  for (let y = 0; y < SIDE; y += 1) {
    for (let x = 0; x < SIDE; x += 1) {
      cells.push({ ...REST, index: y * SIDE + x, ...PATTERNS[style](x, y) });
    }
  }
  return cells;
}

/** Every style's grid, built once. */
const CELLS: Readonly<Record<LoaderStyle, readonly LoaderCell[]>> = {
  'bit-flip': cellsOf('bit-flip'),
  'pixel-snake': cellsOf('pixel-snake'),
  'square-bloom': cellsOf('square-bloom'),
  'bit-shuffle': cellsOf('bit-shuffle'),
  'pixel-clock': cellsOf('pixel-clock'),
  'matrix-rain': cellsOf('matrix-rain'),
};

/**
 * Reads the grid of a loader.
 *
 * @param style The loader.
 * @returns Its 25 cells, along the rows.
 */
export function loaderCells(style: LoaderStyle): readonly LoaderCell[] {
  return CELLS[style];
}

/**
 * Turns a text into a number that is the same for the same text and unlike for a different one.
 *
 * @param text The text.
 * @returns Its 32-bit FNV-1a hash.
 */
function hashOf(text: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(index), 0x01000193);
  }
  return hash >>> 0;
}

/**
 * Starts a sequence of numbers that a seed decides (mulberry32).
 *
 * @param seed The seed.
 * @returns A function that returns the sequence's next number, from 0 up to but not 1.
 */
function sequence(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let mixed = Math.imul(state ^ (state >>> 15), 1 | state);
    mixed = (mixed + Math.imul(mixed ^ (mixed >>> 7), 61 | mixed)) ^ mixed;
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 0x100000000;
  };
}

/**
 * Picks the loader of one member of a group.
 *
 * The six are put in an order the group decides and its members take them in turn, so up to six
 * members of a group each get a different one, and a seventh starts the order again.
 *
 * @param group What the members share, such as the identifier of the first of them.
 * @param place The member's place in the group, from 0.
 * @returns The member's loader.
 */
export function loaderStyle(group: string, place: number): LoaderStyle {
  const order: LoaderStyle[] = [...LOADER_STYLES];
  const next = sequence(hashOf(group));
  for (let last = order.length - 1; last > 0; last -= 1) {
    const other = Math.floor(next() * (last + 1));
    const moved = order[last];
    const taken = order[other];
    if (moved !== undefined && taken !== undefined) {
      order[last] = taken;
      order[other] = moved;
    }
  }
  return order[place % order.length] ?? LOADER_STYLES[0];
}

/**
 * Picks how far into its loop a loader starts, so that two side by side do not move in step.
 *
 * @param key What the loader stands for, such as a subagent's identifier.
 * @returns The offset, in seconds at full speed.
 */
export function loaderOffset(key: string): number {
  return sequence(hashOf(key))() * OFFSET_SECONDS;
}
