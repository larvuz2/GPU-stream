/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Moody on a canvas: the wordmark a header carries, the face that stands for the agent, and the
 * animations a hero or a section plays.
 *
 * Each component is a canvas the motion library (`lib/moody.ts`) is mounted on for as long as the
 * component is, and takes its color from the text color around it. {@link MoodyLogo} is the
 * header's wordmark, with the library's header behavior: static at rest, an expression after
 * every idle spell, the next one on a click, and static under reduced motion. {@link MoodyFace} is
 * the two eyes alone, for where the name does not fit. {@link MoodyMotion} plays a chosen
 * animation while it is on screen. A canvas is sized by its classes; the library draws the
 * largest whole-pixel grid that fits it, centered.
 * @module
 */
import { useEffect, useRef } from 'react';
import { cx } from '../lib/cx';
import { onExpress } from '../lib/mood';
import { FACE_VIEW, LOGO_VIEW, mountLogo, mountMotion, STAGE_VIEW, type View } from '../lib/moody';

/** Props of {@link MoodyLogo}. */
interface MoodyLogoProps {
  /**
   * The accessible name. Left out where the wordmark sits in a link or a heading that is already
   * named, which makes it decoration.
   */
  label?: string;
  /** Classes that size the canvas (its proportions are the wordmark's) and may color it. */
  className?: string;
  /** Whether it plays the moods the page asks for (`lib/mood.ts`). */
  reactive?: boolean;
  /** The seconds of rest before it plays an expression by itself; the library's when left out. */
  idleSeconds?: number;
}

/**
 * Renders the wordmark with the header behavior.
 *
 * @param props The component's props.
 * @returns The canvas.
 */
export function MoodyLogo({ label, className, reactive = false, idleSeconds }: MoodyLogoProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (canvas.current === null) {
      return undefined;
    }
    const logo = mountLogo(canvas.current, { idleSeconds });
    const unsubscribe = reactive ? onExpress(logo.express) : undefined;
    return () => {
      unsubscribe?.();
      logo.destroy();
    };
  }, [reactive, idleSeconds]);
  return (
    <canvas
      ref={canvas}
      className={cx('block', className)}
      style={{ aspectRatio: `${LOGO_VIEW.cols} / ${LOGO_VIEW.rows}` }}
      role={label === undefined ? undefined : 'img'}
      aria-label={label}
      aria-hidden={label === undefined ? true : undefined}
    />
  );
}

/** Props of {@link MoodyFace}. */
interface MoodyFaceProps {
  /** Classes that size the canvas and may color it. */
  className?: string;
  /** An expression (0 to 4) to keep playing while the agent is busy; resting when left out. */
  busy?: number;
  /** Whether a resting face plays an expression after every idle spell, as the wordmark does. */
  idle?: boolean;
}

/** A face that never plays by itself cycles through no expressions. */
const NO_EXPRESSIONS: readonly number[] = [];

/**
 * Renders Moody's face, the wordmark's two eyes, as decoration beside what the agent says.
 *
 * @param props The component's props.
 * @returns The canvas.
 */
export function MoodyFace({ className, busy, idle = false }: MoodyFaceProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (canvas.current === null) {
      return undefined;
    }
    const face = mountLogo(canvas.current, {
      face: true,
      clickable: false,
      busy,
      order: idle ? undefined : NO_EXPRESSIONS,
    });
    return face.destroy;
  }, [busy, idle]);
  return (
    <canvas
      ref={canvas}
      className={cx('block', className)}
      style={{ aspectRatio: `${FACE_VIEW.cols} / ${FACE_VIEW.rows}` }}
      aria-hidden="true"
    />
  );
}

/** Props of {@link MoodyMotion}. */
interface MoodyMotionProps {
  /** The animation to play, by index (`lib/moody.ts`, `ANIMATION`). */
  animation: number;
  /** An animation to play once before it. */
  intro?: number;
  /** Whether it starts over when it ends; one that does not plays again each time it is scrolled to. */
  loop?: boolean;
  /** The part of the plane the canvas shows; the library's stage when left out. */
  view?: View;
  /** Whether to draw the eyes alone (expressions only). */
  face?: boolean;
  /** What the animation pictures, for assistive technology; decoration when left out. */
  label?: string;
  /** Classes that size the canvas and may color it. */
  className?: string;
  /**
   * Called for every frame drawn, to caption what is on screen. It is read when the animation is
   * mounted, so it should not change between renders.
   *
   * @param index The animation on screen.
   * @param seconds The time into it.
   */
  onFrame?: (index: number, seconds: number) => void;
}

/**
 * Renders an animation of the motion library, playing while it is on screen and the tab is visible.
 *
 * @param props The component's props.
 * @returns The canvas.
 */
export function MoodyMotion({
  animation,
  intro,
  loop,
  view = STAGE_VIEW,
  face,
  label,
  className,
  onFrame,
}: MoodyMotionProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const { cx: centerX, cy: centerY, cols, rows } = view;
  useEffect(() => {
    if (canvas.current === null) {
      return undefined;
    }
    const motion = mountMotion(canvas.current, {
      animation,
      intro,
      loop,
      face,
      onFrame,
      view: { cx: centerX, cy: centerY, cols, rows },
    });
    return motion.destroy;
  }, [animation, intro, loop, face, onFrame, centerX, centerY, cols, rows]);
  return (
    <canvas
      ref={canvas}
      className={cx('block', className)}
      role={label === undefined ? undefined : 'img'}
      aria-label={label}
      aria-hidden={label === undefined ? true : undefined}
    />
  );
}
