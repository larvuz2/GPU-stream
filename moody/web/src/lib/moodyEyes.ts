/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Moody eyes: the brand's subagent expression library, which draws the wordmark's two pixel
 * eyes alone and moves them through ten expressions that say what an agent is doing.
 *
 * An expression is a pure function of time. {@link eyePixels} takes one of {@link EXPRESSIONS} and
 * the seconds into it and returns each pixel of the two eyes, and of the brows some expressions
 * raise, in cells around the pair's center: an eye is the wordmark's 4 by 4 ring ({@link EYE}),
 * scaled, shifted, and squeezed by the expression ({@link eyeState}), and both eyes blink once in
 * every four-second cycle. The expression identifiers are the activity identifiers of
 * `catalog.json` (`activities`), which is also where each one's label is read from
 * (`activityLabel` in `lib/catalog.ts`): this module draws, and names nothing.
 *
 * {@link mountEyes} plays an expression on a canvas. Every mounted pair shares one
 * `requestAnimationFrame` loop, which runs only while a pair is mounted, and each keeps its own
 * clock, started at a random point of the cycle so that a column of agents does not blink in
 * unison. A pair that is not in the document or not on screen is skipped, and the browser pauses
 * the loop in a hidden tab. With `prefers-reduced-motion: reduce` a pair shows the first frame of
 * its expression and does not move.
 *
 * Drawing is the motion library's (`drawPoints` in `lib/moody.ts`): the cell is a whole number of
 * device pixels, so eyes at rest lie on the pixel grid, and the color is the canvas's own computed
 * `color`, so a pair follows the text beside it and takes its color from the page's tokens. The
 * pair sits a little below the middle of its canvas ({@link EYES_VIEW}), which leaves the room
 * above it that the brows rise into.
 * @module
 */
import { drawPoints, type Point, type View } from './moody';

/** The expressions, in the brand's order; each is also an activity identifier of the catalog. */
export const EXPRESSIONS = [
  'thinking',
  'searching',
  'processing',
  'analyzing',
  'creating',
  'curious',
  'confused',
  'focused',
  'surprised',
  'satisfied',
] as const;

/** One expression of the eyes. */
export type Expression = (typeof EXPRESSIONS)[number];

/** The expression an identifier the eyes do not know is drawn as. */
const FALLBACK: Expression = 'thinking';

/** The seconds one cycle of an expression lasts, the blink included. */
const CYCLE = 4;

/** When in the cycle the eyes are fully shut, and how long closing or opening takes, in seconds. */
const BLINK_AT = 3.75;
const BLINK_HALF = 0.17;

/**
 * One eye, as cells around its center: the wordmark's o.
 *
 * ```text
 * .XX.
 * X..X
 * X..X
 * .XX.
 * ```
 */
const EYE: readonly (readonly [x: number, y: number])[] = [
  [0, 0],
  [1, 0],
  [-1, 1],
  [2, 1],
  [-1, 2],
  [2, 2],
  [0, 3],
  [1, 3],
];

/** The horizontal center of each eye, in cells from the pair's center. */
const EYE_CENTERS: readonly number[] = [-3, 2];

/** The part of the plane a pair's canvas shows: 11 by 8 cells, the eyes' center at 60% of its height. */
export const EYES_VIEW: View = { cx: 0, cy: -0.8, cols: 11, rows: 8 };

/** How an expression shapes one eye at a point in time. */
interface EyeState {
  /** The horizontal scale. */
  sx: number;
  /** The vertical scale. */
  sy: number;
  /** The horizontal offset, in cells. */
  ox: number;
  /** The vertical offset, in cells. */
  oy: number;
  /** Whether the eye has a brow. */
  brows: boolean;
  /** The brow's height, in cells from the eye's center. */
  browHeight: number;
  /** How far each end of the brow rises or falls, in cells. */
  browAngle: number;
}

const clamp = (value: number, min = 0, max = 1): number => Math.max(min, Math.min(max, value));

/** A triangle from 0 up to 1 at `center` and back, `width` seconds either side, and 0 outside it. */
const pulse = (seconds: number, center: number, width: number): number =>
  Math.max(0, 1 - Math.abs(seconds - center) / width);

/**
 * Whether a value names an expression the eyes draw.
 *
 * @param value The value.
 * @returns `true` for one of {@link EXPRESSIONS}.
 */
export function isExpression(value: unknown): value is Expression {
  return EXPRESSIONS.some((expression) => expression === value);
}

/**
 * The expression an activity is drawn as.
 *
 * @param activity The activity's identifier, as an event or the catalog names it.
 * @returns The expression of that name, or `thinking` for one the eyes do not know or none at all.
 */
export function expressionOf(activity: string | null | undefined): Expression {
  return isExpression(activity) ? activity : FALLBACK;
}

/**
 * Shapes one eye for an expression at a point in time.
 *
 * @param expression The expression.
 * @param eye Which eye: 0 the left, 1 the right.
 * @param seconds The time into the expression.
 * @returns The eye's scale, offset, and brow.
 */
function eyeState(expression: Expression, eye: number, seconds: number): EyeState {
  const phase = seconds % CYCLE;
  const state: EyeState = { sx: 1, sy: 1, ox: 0, oy: 0, brows: false, browHeight: -3, browAngle: 0 };
  switch (expression) {
    case 'thinking':
      state.sy = 0.85;
      state.oy = -0.15;
      state.ox = Math.sin(seconds * 1.2) * 0.35;
      state.brows = true;
      state.browAngle = eye === 0 ? 0.35 : -0.35;
      break;
    case 'searching':
      state.ox = phase < 1.3 ? -0.65 : phase < 2.6 ? 0.65 : 0;
      break;
    case 'processing':
      state.sy = 1 - 0.22 * Math.sin(seconds * 5 + eye * 0.9);
      break;
    case 'analyzing':
      state.sy = eye === 0 ? 0.65 : 1;
      state.ox = 0.25 * Math.sin(seconds * 1.7);
      state.brows = true;
      state.browAngle = 0.4;
      break;
    case 'creating':
      state.sy = 1 + 0.2 * Math.sin(seconds * 3 + eye * 0.5);
      state.oy = 0.3 * Math.sin(seconds * 3 + eye * 0.5);
      break;
    case 'curious':
      state.sy = eye === 0 ? 1 : 1.25;
      state.oy = eye === 0 ? 0 : -0.4;
      state.brows = true;
      state.browHeight = eye === 0 ? -2.75 : -3.7;
      break;
    case 'confused':
      state.sy = eye === 0 ? 0.6 : 1.2;
      state.oy = eye === 0 ? 0.3 : -0.4;
      state.brows = true;
      state.browAngle = eye === 0 ? 0.6 : -0.6;
      break;
    case 'focused':
      state.sy = 0.5;
      state.oy = 0.3;
      state.brows = true;
      state.browHeight = -2.6;
      state.browAngle = eye === 0 ? 0.65 : -0.65;
      break;
    case 'surprised': {
      const surprise = pulse(phase, 1.2, 0.8);
      state.sy = 1 + 0.55 * surprise;
      state.oy = -0.35 * surprise;
      state.brows = true;
      state.browHeight = -3.5 - 0.4 * surprise;
      break;
    }
    case 'satisfied':
      state.sy = 0.4 + 0.15 * Math.cos(seconds * 2);
      break;
  }
  return state;
}

/** Which parts of a frame are drawn. */
export interface EyeParts {
  /** Whether the eyes blink; `true` when left out. */
  blink?: boolean;
  /** Whether the brows an expression raises are drawn; `true` when left out. */
  brows?: boolean;
}

/**
 * One frame of an expression.
 *
 * @param expression The expression.
 * @param seconds The time into it.
 * @param parts Which parts to draw.
 * @returns The frame's pixels, in cells from the pair's center.
 */
export function eyePixels(expression: Expression, seconds: number, parts: EyeParts = {}): Point[] {
  const blink = parts.blink === false ? 0 : pulse(seconds % CYCLE, BLINK_AT, BLINK_HALF);
  const pixels: Point[] = [];
  EYE_CENTERS.forEach((cx, eye) => {
    const state = eyeState(expression, eye, seconds);
    const sy = state.sy * (1 - blink);
    for (const [x, y] of EYE) {
      pixels.push([cx + (x - 0.5) * state.sx + state.ox, (y - 1.5) * sy + state.oy, 1, 1, 1 - 0.25 * blink]);
    }
    if (state.brows && parts.brows !== false) {
      for (const offset of [-1, 0, 1]) {
        pixels.push([cx + offset, state.browHeight + offset * state.browAngle, 0.95]);
      }
    }
  });
  return pixels;
}

/**
 * The eyes at rest: open, level, and without brows, for a pair that is not doing anything.
 *
 * @returns The pixels, in cells from the pair's center.
 */
export function neutralPixels(): Point[] {
  return EYE_CENTERS.flatMap((cx) => EYE.map(([x, y]): Point => [cx + x - 0.5, y - 1.5, 1]));
}

/**
 * Draws the eyes at rest on a canvas, once.
 *
 * @param canvas The canvas, sized by CSS and colored by its `color`.
 */
export function drawNeutral(canvas: HTMLCanvasElement): void {
  drawPoints(canvas, neutralPixels(), EYES_VIEW);
}

/** A mounted pair, as the shared loop sees it. */
interface Instance {
  /**
   * Advances the pair's clock and draws it.
   *
   * @param now The frame's time, in milliseconds.
   */
  update: (now: number) => void;
}

/** Every mounted pair. */
const instances = new Set<Instance>();

/** The pending frame of the shared loop, or `null` while it is not running. */
let frameId: number | null = null;

/**
 * Runs one frame of the shared loop: every pair, then the next frame while any is mounted.
 *
 * @param now The frame's time, in milliseconds.
 */
function tick(now: number): void {
  frameId = null;
  for (const instance of instances) {
    instance.update(now);
  }
  if (instances.size > 0) {
    frameId = window.requestAnimationFrame(tick);
  }
}

/** Starts the shared loop when a pair is mounted and it is not running. */
function startScheduler(): void {
  if (frameId === null && instances.size > 0) {
    frameId = window.requestAnimationFrame(tick);
  }
}

/** Stops the shared loop once no pair is mounted. */
function stopSchedulerIfEmpty(): void {
  if (instances.size === 0 && frameId !== null) {
    window.cancelAnimationFrame(frameId);
    frameId = null;
  }
}

/** How fast a pair's clock may run, as a multiple of real time. */
const SPEED_MIN = 0.1;
const SPEED_MAX = 4;

/** The longest step of time one frame advances a pair by, in seconds, so a stalled tab does not jump. */
const MAX_STEP = 0.1;

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';

/** How a mounted pair behaves. */
export interface EyesOptions extends EyeParts {
  /** The expression to play; `thinking` when left out. */
  expression?: Expression;
  /** How fast its clock runs, as a multiple of real time between 0.1 and 4; 1 when left out. */
  speed?: number;
  /** Whether its clock starts at a random point of the cycle; `true` when left out. */
  randomOffset?: boolean;
  /** Whether it plays as soon as it is mounted; `true` when left out. */
  autoplay?: boolean;
}

/** What {@link mountEyes} returns. */
export interface EyesHandle {
  /** The expression being played. */
  readonly expression: Expression;
  /**
   * Plays another expression.
   *
   * @param next The expression.
   * @param restart Whether its clock starts over; `true` when left out.
   */
  setExpression: (next: Expression, restart?: boolean) => void;
  /**
   * Changes how fast the clock runs.
   *
   * @param speed A multiple of real time, kept between 0.1 and 4.
   */
  setSpeed: (speed: number) => void;
  /** Lets the clock run. */
  play: () => void;
  /** Holds the clock where it is. */
  pause: () => void;
  /** Starts the expression over and lets the clock run. */
  replay: () => void;
  /** Leaves the shared loop, stops watching the canvas, and clears it. */
  destroy: () => void;
}

/**
 * Plays an expression on a canvas, on the shared loop.
 *
 * @param canvas The canvas, sized by CSS and colored by its `color`.
 * @param options How it behaves.
 * @returns The handle that changes what it plays and removes it.
 */
export function mountEyes(canvas: HTMLCanvasElement, options: EyesOptions = {}): EyesHandle {
  const { blink = true, brows = true, randomOffset = true, autoplay = true } = options;
  const reduced = window.matchMedia(REDUCED_MOTION);
  let expression = options.expression ?? FALLBACK;
  let speed = clamp(options.speed ?? 1, SPEED_MIN, SPEED_MAX);
  let playing = autoplay;
  let elapsed = randomOffset ? Math.random() * CYCLE : 0;
  let previous: number | null = null;
  let onScreen = true;

  const draw = (): void => {
    drawPoints(canvas, eyePixels(expression, reduced.matches ? 0 : elapsed, { blink, brows }), EYES_VIEW);
  };

  const instance: Instance = {
    update: (now) => {
      if (!canvas.isConnected || !onScreen) {
        previous = null;
        return;
      }
      previous ??= now;
      const step = clamp((now - previous) / 1000, 0, MAX_STEP);
      previous = now;
      if (playing && !reduced.matches) {
        elapsed += step * speed;
      }
      draw();
    },
  };

  const observer = new IntersectionObserver((entries) => {
    onScreen = entries.some((entry) => entry.isIntersecting);
  });
  observer.observe(canvas);
  instances.add(instance);
  startScheduler();
  draw();

  return {
    get expression() {
      return expression;
    },
    setExpression: (next, restart = true) => {
      expression = next;
      if (restart) {
        elapsed = 0;
      }
      draw();
    },
    setSpeed: (next) => {
      speed = clamp(Number.isFinite(next) ? next : 1, SPEED_MIN, SPEED_MAX);
    },
    play: () => {
      playing = true;
      previous = null;
    },
    pause: () => {
      playing = false;
    },
    replay: () => {
      elapsed = 0;
      playing = true;
      previous = null;
      draw();
    },
    destroy: () => {
      instances.delete(instance);
      stopSchedulerIfEmpty();
      observer.disconnect();
      const context = canvas.getContext('2d');
      context?.setTransform(1, 0, 0, 1, 0, 0);
      context?.clearRect(0, 0, canvas.width, canvas.height);
    },
  };
}
