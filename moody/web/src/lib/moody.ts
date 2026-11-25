/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Moody motion library: the wordmark as pixels, the eight procedural animations that move
 * them, and the two ways a page plays them on a canvas.
 *
 * The wordmark is "moody" on a 26 by 8 grid ({@link RAW}), and its two o's are its eyes. Every
 * animation is a pure function of time: {@link points} takes an animation's index and the seconds
 * into it and returns where each pixel is, how opaque, and, for the few that are not one cell, how
 * large. Indices 0 to 4 are facial expressions (the eyes stretch, squint, blink, and look, with
 * brows and a mouth fading in around them); 5 assembles the wordmark from scattered pixels; 6 drops
 * it in under gravity; 7 morphs it through the shapes of what the studio makes ({@link MORPH_SHAPES})
 * and back. Coordinates are in cells, relative to the wordmark's center, so a caller chooses what
 * part of that plane a canvas shows with a {@link View}.
 *
 * Drawing works in device pixels: the canvas's backing store follows its CSS size times the
 * device pixel ratio, and the cell size is floored to a whole number of device pixels, so the
 * wordmark at rest lies exactly on the pixel grid at any ratio and only pixels in motion are
 * antialiased. The color is the canvas's own computed `color`, so a mark follows its text.
 *
 * Two controllers mount on a canvas and return a handle that removes everything they added:
 *
 * - {@link mountLogo} is a header's wordmark. It rests static; after `idleSeconds` without playing
 *   it plays the next expression of {@link HEADER_ORDER}, a click plays the next one at once, and
 *   only expressions are ever played. Its handle's `express` lets a page show a mood on purpose.
 * - {@link mountMotion} plays chosen animations for a hero or a section, only while the canvas is
 *   on screen and the tab is visible.
 *
 * With `prefers-reduced-motion: reduce` neither animates: the logo stays the static wordmark and a
 * motion shows its resting frame.
 * @module
 */

/** A pixel of a frame: its center in cells, its opacity, and its size in cells where not 1 by 1. */
export type Point = readonly [x: number, y: number, opacity: number, width?: number, height?: number];

/** A cell of a grid, as column and row. */
type Cell = readonly [x: number, y: number];

/** The part of the plane a canvas shows: its center and its size, in cells. */
export interface View {
  /** The horizontal center, in cells from the wordmark's center. */
  cx: number;
  /** The vertical center, in cells from the wordmark's center. */
  cy: number;
  /** How many cells the canvas is wide. */
  cols: number;
  /** How many cells the canvas is tall. */
  rows: number;
}

/** The wordmark's lit cells on its 26 by 8 grid, column then row. */
export const RAW: readonly Cell[] = [
  [21, 0], [21, 1], [0, 2], [1, 2], [2, 2], [3, 2], [4, 2], [8, 2], [9, 2], [13, 2], [14, 2], [19, 2], [20, 2],
  [21, 2], [23, 2], [25, 2], [0, 3], [2, 3], [5, 3], [7, 3], [10, 3], [12, 3], [15, 3], [18, 3], [21, 3], [23, 3],
  [25, 3], [0, 4], [2, 4], [5, 4], [7, 4], [10, 4], [12, 4], [15, 4], [18, 4], [21, 4], [24, 4], [25, 4], [0, 5],
  [2, 5], [5, 5], [8, 5], [9, 5], [13, 5], [14, 5], [19, 5], [20, 5], [21, 5], [25, 5], [24, 6], [23, 7],
];

/** The wordmark grid's width, in cells. */
export const GRID_COLS = 26;

/** The wordmark grid's height, in cells. */
export const GRID_ROWS = 8;

/** Half the grid, which centers a cell's coordinates on the wordmark. */
const HALF_COLS = 12.5;
const HALF_ROWS = 3.5;

/** The wordmark at rest, centered. */
export const LOGO: readonly Point[] = RAW.map(([x, y]): Point => [x - HALF_COLS, y - HALF_ROWS, 1]);

/**
 * Reads a picture drawn as rows of `1` and `0` into centered points.
 *
 * @param art The picture's rows, top first, all of one length.
 * @returns A point for every `1`.
 */
export function rows(art: readonly string[]): Point[] {
  return art.flatMap((row, y) =>
    Array.from(row).flatMap((value, x): Point[] =>
      value === '1' ? [[x - (row.length - 1) / 2, y - (art.length - 1) / 2, 1]] : [],
    ),
  );
}

/** What each shape of the morph pictures, in the order it plays them. */
export const MORPH_SHAPES = [
  'wordmark',
  'heart',
  'controller',
  'wordmark',
  'clapper',
  'picture',
  'wordmark',
  'waveform',
  'face',
  'wordmark',
] as const;

/** A shape of the morph, by what it pictures. */
export type MorphShape = (typeof MORPH_SHAPES)[number];

const HEART = rows(['01100110', '11111111', '11111111', '11111111', '01111110', '00111100', '00011000']);

const CONTROLLER = rows([
  '001111111100',
  '011111111110',
  '110100001011',
  '100010010001',
  '110100000101',
  '111111111111',
  '111100001111',
  '110000000011',
]);

const CLAPPER = rows([
  '11101110111011',
  '11011101110111',
  '11111111111111',
  '10000000000001',
  '10000100000001',
  '10000110000001',
  '10000111000001',
  '10000111100001',
  '10000111000001',
  '10000110000001',
  '10000100000001',
  '10000000000001',
  '11111111111111',
]);

const PICTURE = rows([
  '11111111111',
  '10000000001',
  '10110000001',
  '10110001001',
  '10000011101',
  '10010111101',
  '10111111101',
  '11111111111',
]);

const WAVEFORM = rows([
  '0000001000000',
  '0001001001000',
  '0001001101000',
  '0101101111010',
  '1111111111111',
  '0101101111010',
  '0001001101000',
  '0001001001000',
  '0000001000000',
]);

const FACE = rows([
  '0011111100',
  '0100000010',
  '1000000001',
  '1011001101',
  '1011001101',
  '1000000001',
  '1010000101',
  '1001111001',
  '0100000010',
  '0011111100',
]);

/** The morph's shapes as points, in playing order. */
const SHAPES: readonly (readonly Point[])[] = [LOGO, HEART, CONTROLLER, LOGO, CLAPPER, PICTURE, LOGO, WAVEFORM, FACE, LOGO];

/** A morph pixel: where it is and whether it is lit. */
type MorphPoint = readonly [x: number, y: number, opacity: number];

/**
 * Builds the morph's key frames: every shape padded to as many pixels as the largest has, the
 * spare ones unlit on top of lit ones, and each frame's pixels ordered so that pixel `i` of one
 * frame travels to the nearest unclaimed pixel of the next (lit to lit where it can).
 *
 * @returns One frame per shape of {@link SHAPES}.
 */
function morphFrames(): MorphPoint[][] {
  const count = Math.max(...SHAPES.map((shape) => shape.length));
  const pad = (shape: readonly Point[]): MorphPoint[] =>
    Array.from({ length: count }, (_, index): MorphPoint => {
      const source = shape[index % shape.length] ?? [0, 0, 0];
      return [source[0], source[1], index < shape.length ? 1 : 0];
    });
  const frames: MorphPoint[][] = [pad(LOGO)];
  for (let index = 1; index < SHAPES.length; index += 1) {
    const pool = pad(SHAPES[index] ?? LOGO);
    const previous = frames[index - 1] ?? [];
    frames.push(
      previous.map((from): MorphPoint => {
        let nearest = 0;
        let distance = Infinity;
        pool.forEach((to, candidate) => {
          const value = (from[0] - to[0]) ** 2 + (from[1] - to[1]) ** 2 + Math.abs(from[2] - to[2]) * 2;
          if (value < distance) {
            nearest = candidate;
            distance = value;
          }
        });
        return pool.splice(nearest, 1)[0] ?? from;
      }),
    );
  }
  return frames;
}

const FRAMES = morphFrames();

/** The animations' names, by index. */
export const NAMES = [
  'Surprised',
  'Angry',
  'Look around',
  'Happy',
  'Blink & wink',
  'Assembly',
  'Gravity',
  'Morph',
] as const;

/** How long each animation runs, in seconds, by index. */
export const DURATIONS: readonly number[] = [6, 6, 5.5, 6, 12, 4.6, 5.2, 16.85];

/** The animations by name, so a caller does not write a bare index. */
export const ANIMATION = {
  surprised: 0,
  angry: 1,
  lookAround: 2,
  happy: 3,
  blinkAndWink: 4,
  assembly: 5,
  gravity: 6,
  morph: 7,
} as const;

/** How many of the animations are facial expressions: indices 0 to 4. */
export const EXPRESSION_COUNT = 5;

/** The order a header's wordmark plays its expressions in. */
export const HEADER_ORDER: readonly number[] = [2, 3, 4, 0, 1];

/** How long a header's wordmark rests before it plays an expression by itself, in seconds. */
export const IDLE_SECONDS = 17;

/**
 * How far into each expression its first visible change is, in seconds. An expression a person
 * asked for (a click, a mood) starts there, so it answers at once; one played from idle runs whole.
 */
const LEAD_IN: readonly number[] = [0.8, 0.8, 0, 0.8, 2.9];

/** The seconds one shape of the morph takes: a hold, then the move to the next. */
const MORPH_STEP = 1.75;
const MORPH_HOLD = 0.8;
const MORPH_MOVE = 0.95;

/** The brows each expression raises, as cells of the wordmark's grid. */
const BROWS: Readonly<Record<number, readonly Cell[]>> = {
  0: [[7, -1], [8, -2], [9, -2], [10, -1], [12, -1], [13, -2], [14, -2], [15, -1]],
  1: [[7, -2], [8, -1], [9, 0], [10, 1], [12, 1], [13, 0], [14, -1], [15, -2]],
  3: [[7, 0], [8, -1], [9, -1], [10, 0], [12, 0], [13, -1], [14, -1], [15, 0]],
};

/** The mouth each expression draws, as cells of the wordmark's grid. */
const MOUTHS: Readonly<Record<number, readonly Cell[]>> = {
  0: [[10, 7], [11, 6], [12, 7], [11, 8]],
  1: [[9, 8], [10, 7], [11, 7], [12, 7], [13, 8]],
  3: [[9, 6], [10, 7], [11, 7], [12, 7], [13, 6]],
};

/** The horizontal centers of the two eyes, in grid columns. */
const EYE_CENTERS: readonly number[] = [8.5, 13.5];

const clamp = (value: number): number => Math.max(0, Math.min(1, value));

const ease = (value: number): number => {
  const x = clamp(value);
  return x * x * (3 - 2 * x);
};

/** A fixed pseudo-random number in [0, 1) for an index, so every run scatters the same way. */
const noise = (index: number): number => {
  const value = Math.sin(index * 127.1 + 311.7) * 43758.5453;
  return value - Math.floor(value);
};

/** A bump from 0 to 1 and back over `width` seconds from `start`, and 0 outside it. */
function pulse(seconds: number, start: number, width: number): number {
  const value = (seconds - start) / width;
  return value >= 0 && value <= 1 ? Math.pow(Math.sin(Math.PI * value), 1.5) : 0;
}

/**
 * Whether an index names a facial expression.
 *
 * @param index The animation's index.
 * @returns `true` for 0 to 4.
 */
export function isExpression(index: number): boolean {
  return Number.isInteger(index) && index >= 0 && index < EXPRESSION_COUNT;
}

/**
 * One frame of a facial expression.
 *
 * @param index The expression, 0 to 4.
 * @param seconds The time into it.
 * @param faceOnly Whether to leave out the letters that are not eyes.
 * @returns The frame's pixels.
 */
function expression(index: number, seconds: number, faceOnly: boolean): Point[] {
  let amount = ease((seconds - 0.9) / 0.6) * (1 - ease((seconds - 3.8) / 0.65));
  let blink = pulse(seconds, 4.8, 0.28);
  let wink = 0;
  let gaze = 0;
  if (index === 2) {
    amount = ease(seconds / 0.12) * (1 - ease((seconds - 2.34) / 0.14));
    gaze = -0.5 + ease((seconds - 1.05) / 0.22);
    blink = ease((seconds - 2.3) / 0.18) * (1 - ease((seconds - 2.48) / 0.2));
  }
  if (index === 4) {
    amount = 0;
    blink = pulse(seconds, 3, 0.28);
    wink = pulse(seconds, 7.5, 0.5);
  }
  const frame = RAW.flatMap(([x, y]): Point[] => {
    const eye = x >= 7 && x <= 10 ? 1 : x >= 12 && x <= 15 ? 2 : 0;
    if (eye === 0) {
      return faceOnly ? [] : [[x - HALF_COLS, y - HALF_ROWS, 1]];
    }
    const cx = eye === 1 ? 8.5 : 13.5;
    const cy = 3.5;
    let sx = 1;
    let sy = 1;
    let oy = 0;
    let ox = 0;
    if (index === 0) {
      sy = 1 + 0.36 * amount + 0.15 * Math.sin(Math.PI * clamp((seconds - 0.9) / 0.65));
      sx = 1 + 0.08 * amount;
      oy = -0.48 * amount;
    }
    if (index === 1) {
      sy = 1 - 0.48 * amount;
      oy = 0.25 * amount;
      ox = (eye === 1 ? 0.1 : -0.1) * amount;
    }
    if (index === 2) {
      sy = 1 + 0.08 * amount;
    }
    if (index === 3) {
      sy = 1 - 0.58 * amount;
      oy = -0.25 * amount + Math.sin(seconds * 12) * 0.08 * amount;
    }
    const closed = Math.max(blink, eye === 2 ? wink : 0);
    sy *= 1 - closed;
    return [[cx + (x - cx) * sx + ox - HALF_COLS, cy + (y - cy) * sy + oy - HALF_ROWS, 1, 1, 1 - 0.2 * closed]];
  });
  for (const [x, y] of BROWS[index] ?? []) {
    frame.push([x - HALF_COLS, y + 0.5 * (1 - amount) - HALF_ROWS, amount]);
  }
  for (const [x, y] of MOUTHS[index] ?? []) {
    frame.push([x - HALF_COLS, y - 0.4 * (1 - amount) - HALF_ROWS, amount]);
  }
  if (index === 2) {
    for (const cx of EYE_CENTERS) {
      for (const dx of [-1, 0, 1]) {
        frame.push([cx + dx + gaze * 0.25 - HALF_COLS, -0.05 + dx * gaze * 0.5 * amount + 0.45 * (1 - amount) - HALF_ROWS, amount]);
      }
      frame.push([cx + gaze - HALF_COLS, 0, amount * (1 - blink), 0.85, 0.85]);
    }
  }
  return frame;
}

/**
 * One frame of an animation.
 *
 * @param index The animation, 0 to 7 ({@link NAMES}).
 * @param seconds The time into it.
 * @returns The frame's pixels, in cells from the wordmark's center.
 */
export function points(index: number, seconds: number): Point[] {
  if (index === 5) {
    return LOGO.map((point, i): Point => {
      const arrived = 1 - Math.pow(1 - clamp((seconds - 0.6 - noise(i + 3) * 0.7) / 2.2), 3);
      const angle = noise(i + 54) * Math.PI * 2;
      const radius = 8 + noise(i + 138) * 10;
      return [
        point[0] + Math.cos(angle) * radius * (1 - arrived),
        point[1] + Math.sin(angle) * radius * 0.6 * (1 - arrived),
        1,
      ];
    });
  }
  if (index === 6) {
    return LOGO.map((point, i): Point => {
      const fallen = Math.max(0, seconds - 0.35 - noise(i + 19) * 1.25);
      const bounced = fallen - 0.62;
      const y =
        fallen < 0.62
          ? -15 * (1 - (fallen / 0.62) ** 2)
          : bounced > 1.5
            ? 0
            : -2.3 * Math.abs(Math.sin(bounced * 9)) * Math.exp(-bounced * 3.8);
      return [point[0], point[1] + y, 1];
    });
  }
  if (index === 7) {
    const last = FRAMES.length - 1;
    const step = Math.min(last, Math.floor(seconds / MORPH_STEP));
    const moved = ease((seconds - step * MORPH_STEP - MORPH_HOLD) / MORPH_MOVE);
    const from = FRAMES[step] ?? [];
    const to = FRAMES[Math.min(step + 1, last)] ?? from;
    return from.map((point, i): Point => {
      const target = to[i] ?? point;
      return [
        point[0] + (target[0] - point[0]) * moved,
        point[1] + (target[1] - point[1]) * moved,
        point[2] + (target[2] - point[2]) * moved,
      ];
    });
  }
  return expression(index, seconds, false);
}

/**
 * One frame of an expression with the eyes alone: the two o's, and the brows and mouth the
 * expression adds, without the other letters. This is Moody's face where there is no room for
 * its name.
 *
 * @param index The expression, 0 to 4.
 * @param seconds The time into it.
 * @returns The frame's pixels, in cells from the wordmark's center.
 */
export function facePoints(index: number, seconds: number): Point[] {
  return expression(isExpression(index) ? index : ANIMATION.blinkAndWink, seconds, true);
}

/**
 * Which shape the morph shows at a time: the one it holds, or the nearer one while it moves.
 *
 * @param seconds The time into the morph.
 * @returns What the shape pictures.
 */
export function morphShapeAt(seconds: number): MorphShape {
  const last = MORPH_SHAPES.length - 1;
  const index = Math.max(0, Math.min(last, Math.floor((seconds + MORPH_STEP - MORPH_HOLD - MORPH_MOVE / 2) / MORPH_STEP)));
  return MORPH_SHAPES[index] ?? 'wordmark';
}

/**
 * The time at which an animation shows the frame it rests on: the assembled wordmark.
 *
 * @param index The animation.
 * @returns The seconds into it: its end for the two that begin scattered, its start otherwise.
 */
export function restSeconds(index: number): number {
  return index === ANIMATION.assembly || index === ANIMATION.gravity ? (DURATIONS[index] ?? 0) : 0;
}

/** The playground's stage: room around the wordmark for the shapes and the scatter. */
export const STAGE_VIEW: View = { cx: 0, cy: 0, cols: 34, rows: 21 };

/** A header's wordmark: its 26 columns, and rows above and below for the brows and the mouth. */
export const LOGO_VIEW: View = { cx: 0, cy: 0, cols: GRID_COLS, rows: 12 };

/** The eyes alone, with the same room for brows and mouth. */
export const FACE_VIEW: View = { cx: -1.5, cy: 0, cols: 11, rows: 12 };

/** How far from a whole device pixel still counts as on it. */
const ALIGNED = 1e-6;

const isAligned = (value: number): boolean => Math.abs(value - Math.round(value)) < ALIGNED;

/**
 * Sizes a canvas's backing store to its CSS box at the device's pixel ratio.
 *
 * @param canvas The canvas.
 */
function fit(canvas: HTMLCanvasElement): void {
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
  const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

/**
 * Draws a frame's pixels on a canvas.
 *
 * The cell is the largest whole number of device pixels at which the view fits (a fraction only
 * where the canvas is smaller than one device pixel per cell), and the view's center is rounded to
 * a device pixel, so a pixel at a grid position fills exact device pixels. A pixel between
 * positions is drawn a hair larger, which closes the seams between neighbors moving together.
 *
 * @param canvas The canvas, sized by CSS.
 * @param frame The pixels to draw.
 * @param view The part of the plane the canvas shows.
 * @param color The fill; the canvas's computed `color` when left out.
 */
export function drawPoints(canvas: HTMLCanvasElement, frame: readonly Point[], view: View, color?: string): void {
  fit(canvas);
  const context = canvas.getContext('2d');
  if (context === null) {
    return;
  }
  const { width, height } = canvas;
  const loose = Math.min(width / view.cols, height / view.rows);
  const cell = loose >= 1 ? Math.floor(loose) : loose;
  const originX = Math.round(width / 2 - view.cx * cell);
  const originY = Math.round(height / 2 - view.cy * cell);
  const seam = 0.03 * (window.devicePixelRatio || 1);
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.clearRect(0, 0, width, height);
  context.fillStyle = color ?? getComputedStyle(canvas).color;
  for (const point of frame) {
    const opacity = clamp(point[2]);
    if (opacity === 0) {
      continue;
    }
    const w = point[3] ?? 1;
    const h = point[4] ?? w;
    const x = originX + (point[0] - w / 2) * cell;
    const y = originY + (point[1] - h / 2) * cell;
    const exact = isAligned(x) && isAligned(y) && isAligned(w * cell) && isAligned(h * cell);
    context.globalAlpha = opacity;
    if (exact) {
      context.fillRect(Math.round(x), Math.round(y), Math.round(w * cell), Math.round(h * cell));
    } else {
      context.fillRect(x, y, w * cell + seam, h * cell + seam);
    }
  }
  context.globalAlpha = 1;
}

/**
 * Draws one frame of an animation on a canvas.
 *
 * @param canvas The canvas, sized by CSS.
 * @param index The animation.
 * @param seconds The time into it.
 * @param view The part of the plane the canvas shows; the playground's stage when left out.
 * @param color The fill; the canvas's computed `color` when left out.
 */
export function draw(canvas: HTMLCanvasElement, index: number, seconds: number, view: View = STAGE_VIEW, color?: string): void {
  drawPoints(canvas, points(index, seconds), view, color);
}

/** The longest step of time one frame advances by, in seconds, so a stalled tab does not jump. */
const MAX_STEP = 0.06;

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';

/**
 * Calls back whenever a canvas's box or the device's pixel ratio changes.
 *
 * @param canvas The canvas to watch.
 * @param onChange The callback.
 * @returns A function that stops watching.
 */
function watchSize(canvas: HTMLCanvasElement, onChange: () => void): () => void {
  const observer = new ResizeObserver(onChange);
  observer.observe(canvas);
  // A zoom or a move to another screen changes the ratio without changing the CSS box.
  window.addEventListener('resize', onChange);
  return () => {
    observer.disconnect();
    window.removeEventListener('resize', onChange);
  };
}

/** How a header's wordmark behaves. */
export interface LogoOptions {
  /** The seconds of rest before it plays an expression by itself; {@link IDLE_SECONDS} when left out. */
  idleSeconds?: number;
  /** The expressions it cycles through; {@link HEADER_ORDER} when left out. Anything else is skipped. */
  order?: readonly number[];
  /** Whether to draw the eyes alone instead of the whole wordmark. */
  face?: boolean;
  /** Whether a click plays the next expression; `true` when left out. */
  clickable?: boolean;
  /**
   * An expression to keep playing, over and over, instead of resting: a face that is busy. `null`
   * or left out for the resting behavior.
   */
  busy?: number | null;
}

/** What {@link mountLogo} returns. */
export interface LogoHandle {
  /**
   * Plays an expression now, from its first visible change.
   *
   * @param index The expression, 0 to 4; any other index is ignored.
   */
  express: (index: number) => void;
  /** Stops everything and removes every listener, leaving the canvas as it is. */
  destroy: () => void;
}

/**
 * Makes a canvas a header's wordmark: static at rest, an expression after every idle spell, the
 * next one on a click, and nothing but the static mark under reduced motion.
 *
 * @param canvas The canvas, sized by CSS and colored by its `color`.
 * @param options How it behaves.
 * @returns The handle that plays a mood and removes the behavior.
 */
export function mountLogo(canvas: HTMLCanvasElement, options: LogoOptions = {}): LogoHandle {
  const { idleSeconds = IDLE_SECONDS, face = false, clickable = true, busy = null } = options;
  const order = (options.order ?? HEADER_ORDER).filter(isExpression);
  const view = face ? FACE_VIEW : LOGO_VIEW;
  const reduced = window.matchMedia(REDUCED_MOTION);
  let turn = 0;
  let current: number | null = null;
  let seconds = 0;
  let last = 0;
  let frame = 0;
  let timer: number | undefined;

  const paint = (): void => {
    if (current === null) {
      drawPoints(canvas, face ? facePoints(ANIMATION.blinkAndWink, 0) : LOGO, view);
    } else {
      drawPoints(canvas, face ? facePoints(current, seconds) : points(current, seconds), view);
    }
  };

  const rest = (): void => {
    current = null;
    window.cancelAnimationFrame(frame);
    frame = 0;
    paint();
  };

  const tick = (now: number): void => {
    frame = 0;
    if (current === null) {
      return;
    }
    seconds += last === 0 ? 0 : Math.min(MAX_STEP, (now - last) / 1000);
    last = now;
    if (seconds >= (DURATIONS[current] ?? 0)) {
      if (busy !== null && isExpression(busy)) {
        start(busy, 0);
        return;
      }
      rest();
      schedule();
      return;
    }
    paint();
    frame = window.requestAnimationFrame(tick);
  };

  const start = (index: number, from: number): void => {
    if (reduced.matches || !isExpression(index)) {
      return;
    }
    window.clearTimeout(timer);
    current = index;
    seconds = from;
    last = 0;
    if (frame === 0) {
      frame = window.requestAnimationFrame(tick);
    }
  };

  const next = (): number | undefined => {
    const index = order[turn % Math.max(1, order.length)];
    turn += 1;
    return index;
  };

  const schedule = (): void => {
    window.clearTimeout(timer);
    if (reduced.matches || order.length === 0) {
      return;
    }
    timer = window.setTimeout(() => {
      // A hidden tab keeps resting, and plays once it has been looked at for a spell again.
      if (document.hidden) {
        schedule();
        return;
      }
      const index = next();
      if (index !== undefined) {
        start(index, 0);
      }
    }, idleSeconds * 1000);
  };

  const begin = (): void => {
    if (busy !== null && isExpression(busy)) {
      start(busy, 0);
    } else {
      schedule();
    }
  };

  const onClick = (): void => {
    const index = next();
    if (index !== undefined) {
      start(index, LEAD_IN[index] ?? 0);
    }
  };

  const onMotionChange = (): void => {
    window.clearTimeout(timer);
    rest();
    begin();
  };

  paint();
  begin();
  const unwatch = watchSize(canvas, paint);
  if (clickable) {
    canvas.addEventListener('click', onClick);
  }
  reduced.addEventListener('change', onMotionChange);

  return {
    express: (index) => {
      start(index, LEAD_IN[index] ?? 0);
    },
    destroy: () => {
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
      frame = 0;
      current = null;
      unwatch();
      canvas.removeEventListener('click', onClick);
      reduced.removeEventListener('change', onMotionChange);
    },
  };
}

/** What a canvas plays, for {@link mountMotion}. */
export interface MotionOptions {
  /** The animation to play. */
  animation: number;
  /** An animation to play once before it, such as the assembly before the morph. */
  intro?: number;
  /**
   * Whether the animation starts over when it ends; `true` when left out. One that does not loop
   * holds its last frame, and plays again each time the canvas comes back on screen.
   */
  loop?: boolean;
  /** The part of the plane the canvas shows; {@link STAGE_VIEW} when left out. */
  view?: View;
  /** Whether to draw the eyes alone (expressions only). */
  face?: boolean;
  /**
   * Called for every frame drawn, with what is playing and how far in, so a page can caption it.
   *
   * @param index The animation on screen.
   * @param seconds The time into it.
   */
  onFrame?: (index: number, seconds: number) => void;
}

/** What {@link mountMotion} returns. */
export interface MotionHandle {
  /** Starts the animation over (after the intro), unless motion is reduced. */
  replay: () => void;
  /** Stops everything and removes every listener and observer. */
  destroy: () => void;
}

/**
 * Plays an animation on a canvas while it can be seen: paused off screen and in a hidden tab, and
 * replaced by its resting frame under reduced motion.
 *
 * @param canvas The canvas, sized by CSS and colored by its `color`.
 * @param options What to play.
 * @returns The handle that replays and removes it.
 */
export function mountMotion(canvas: HTMLCanvasElement, options: MotionOptions): MotionHandle {
  const { animation, intro, loop = true, view = STAGE_VIEW, face = false, onFrame } = options;
  const reduced = window.matchMedia(REDUCED_MOTION);
  let current = intro ?? animation;
  let seconds = 0;
  let last = 0;
  let frame = 0;
  let onScreen = false;
  let finished = false;

  const paint = (): void => {
    drawPoints(canvas, face ? facePoints(current, seconds) : points(current, seconds), view);
    onFrame?.(current, seconds);
  };

  const settle = (): void => {
    current = animation;
    seconds = restSeconds(animation);
    paint();
  };

  const tick = (now: number): void => {
    frame = 0;
    seconds += last === 0 ? 0 : Math.min(MAX_STEP, (now - last) / 1000);
    last = now;
    const length = DURATIONS[current] ?? 0;
    if (seconds >= length) {
      if (current !== animation) {
        current = animation;
        seconds = 0;
      } else if (loop) {
        seconds = 0;
      } else {
        seconds = length;
        finished = true;
        paint();
        return;
      }
    }
    paint();
    frame = window.requestAnimationFrame(tick);
  };

  const update = (): void => {
    const run = onScreen && !document.hidden && !reduced.matches && !finished;
    if (run && frame === 0) {
      last = 0;
      frame = window.requestAnimationFrame(tick);
    } else if (!run && frame !== 0) {
      window.cancelAnimationFrame(frame);
      frame = 0;
    }
  };

  const restart = (): void => {
    if (reduced.matches) {
      settle();
      return;
    }
    current = animation;
    seconds = 0;
    finished = false;
    update();
  };

  const observer = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible && !onScreen && finished) {
      current = animation;
      seconds = 0;
      finished = false;
    }
    onScreen = visible;
    update();
  });

  const onMotionChange = (): void => {
    if (reduced.matches) {
      window.cancelAnimationFrame(frame);
      frame = 0;
      settle();
    } else {
      restart();
    }
  };

  if (reduced.matches) {
    settle();
  } else {
    paint();
  }
  observer.observe(canvas);
  const unwatch = watchSize(canvas, paint);
  document.addEventListener('visibilitychange', update);
  reduced.addEventListener('change', onMotionChange);

  return {
    replay: restart,
    destroy: () => {
      window.cancelAnimationFrame(frame);
      frame = 0;
      observer.disconnect();
      unwatch();
      document.removeEventListener('visibilitychange', update);
      reduced.removeEventListener('change', onMotionChange);
    },
  };
}
