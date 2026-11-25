/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Moody eyes on a canvas: the pair that says what an agent is doing.
 *
 * {@link MoodyEyes} mounts the expression library (`lib/moodyEyes.ts`) on a canvas for as long as
 * the component is, so every pair on a page shares the library's one animation loop. The canvas is
 * 33 by 24 CSS pixels (`.moody-eyes`), three per cell of the library's 11 by 8 grid, and takes its
 * color from its tone, a token of the page. A pair that is `still` shows the eyes at rest and joins
 * no loop: an agent that was stopped or failed is not doing anything.
 *
 * The eyes are decoration: the activity's label, which the caller writes beside them from the
 * catalog, is what says it in words.
 * @module
 */
import { useEffect, useRef } from 'react';
import { cx } from '../lib/cx';
import { drawNeutral, mountEyes, type Expression, type EyesHandle } from '../lib/moodyEyes';

/** What a pair's color says: nothing in particular, the intelligence at work, done, failed, or over. */
export type EyesTone = 'default' | 'active' | 'ok' | 'bad' | 'faint';

/** The text color of each tone, which the canvas draws with. */
const TONES: Readonly<Record<EyesTone, string>> = {
  default: 'text-muted',
  active: 'text-lavender',
  ok: 'text-ok',
  bad: 'text-bad',
  faint: 'text-faint',
};

/** Props of {@link MoodyEyes}. */
interface MoodyEyesProps {
  /** The expression to play. */
  expression: Expression;
  /** What its color says; `default` when left out. */
  tone?: EyesTone;
  /** Whether to show the eyes at rest instead of playing the expression. */
  still?: boolean;
  /** Extra classes for the canvas. */
  className?: string;
}

/**
 * Renders a pair of eyes playing an expression.
 *
 * @param props The component's props.
 * @returns The canvas.
 */
export function MoodyEyes({ expression, tone = 'default', still = false, className }: MoodyEyesProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const handle = useRef<EyesHandle | null>(null);
  // The expression a pair is mounted with; a later one is handed to the mounted pair instead.
  const mounted = useRef(expression);

  useEffect(() => {
    const element = canvas.current;
    if (element === null) {
      return undefined;
    }
    if (still) {
      drawNeutral(element);
      const observer = new ResizeObserver(() => {
        drawNeutral(element);
      });
      observer.observe(element);
      return () => {
        observer.disconnect();
      };
    }
    const eyes = mountEyes(element, { expression: mounted.current });
    handle.current = eyes;
    return () => {
      handle.current = null;
      eyes.destroy();
    };
  }, [still]);

  useEffect(() => {
    mounted.current = expression;
    if (handle.current !== null && handle.current.expression !== expression) {
      handle.current.setExpression(expression);
    }
  }, [expression]);

  // The color is read from the canvas as it draws, so a resting pair is drawn again when it changes.
  useEffect(() => {
    if (still && canvas.current !== null) {
      drawNeutral(canvas.current);
    }
  }, [still, tone]);

  return <canvas ref={canvas} className={cx('moody-eyes', TONES[tone], className)} aria-hidden="true" />;
}
