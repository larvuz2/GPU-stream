/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The stage of a card's `model` component: the canvas a 3D scene is drawn on (`model-scene.ts`),
 * and how the person moves its view.
 *
 * The person orbits and zooms by dragging and the wheel, or with the keyboard on the focused
 * stage: the arrow keys orbit, plus and minus zoom, and Home returns to the card's view, as the
 * reset button does. The view is shown as a readout in the corner, and each time a gesture ends
 * it is handed to the card.
 *
 * With reduced motion asked for, the model does not turn by itself and the controls stop where
 * they are let go. A browser that cannot start WebGL, or a file that is not a model, leaves a
 * line saying so in the stage's place.
 *
 * This module is the default export of a chunk of its own, with three.js in it (`Model.tsx`
 * imports it lazily).
 * @module
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { RotateCcw } from 'lucide-react';
import type { FinishName } from '../catalog';
import { useReducedMotion } from '../hooks';
import type { ModelView } from '../values';
import { ModelScene } from './model-scene';

/** How far one press of a key turns the view, in degrees, and how much it zooms. */
const KEY_STEP = { turn: 10, zoom: 1.15 };

/** The site's token a finish takes its color from where the card names none. */
const FINISH_TOKEN = '--color-soft';

/** Props of {@link ModelStage}. */
export interface ModelStageProps {
  /** The model's address, a binary glTF. */
  url: string;
  /** What the model is, for someone who cannot see it. */
  name: string;
  /** Where the model is seen from. */
  view: ModelView;
  /** The view the card set, which Home and the reset button return to. */
  home: ModelView;
  /** The finish of the whole model. */
  finish: FinishName;
  /** The finish's color, or `null` for the stage's own. */
  color: string | null;
  /** Whether the model turns by itself until the person takes over. */
  spin: boolean;
  /** Whether the view is fixed: a locked card shows the view that was locked in. */
  frozen: boolean;
  /** Takes the view each time the person has changed it. */
  onView: (view: ModelView) => void;
}

/**
 * Renders a 3D model on a stage the person can orbit.
 *
 * @param props The component's props.
 * @returns The stage, or a line where the browser cannot draw 3D or the model cannot be read.
 */
export default function ModelStage({ url, name, view, home, finish, color, spin, frozen, onView }: ModelStageProps) {
  const frame = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const scene = useRef<ModelScene | null>(null);
  const report = useRef(onView);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const reduced = useReducedMotion();

  useEffect(() => {
    report.current = onView;
  });

  // The scene is built once per model, and says when the model is on it or cannot be.
  useEffect(() => {
    const surface = canvas.current;
    const holder = frame.current;
    if (surface === null || holder === null) {
      return;
    }
    const leaving = new AbortController();
    let built: ModelScene | null = null;
    void (async (): Promise<void> => {
      try {
        // A browser without WebGL throws here, and a file that is not a model in `load`.
        built = new ModelScene(surface, holder, (next) => {
          report.current(next);
        });
        await built.load(url);
        if (!leaving.signal.aborted) {
          scene.current = built;
          setState('ready');
        }
      } catch {
        if (!leaving.signal.aborted) {
          setState('failed');
        }
      }
    })();
    return () => {
      leaving.abort();
      scene.current = null;
      built?.dispose();
    };
  }, [url]);

  // The view follows the card: its first view, a view locked in, and what the person's own gesture set.
  const { azimuth, elevation, zoom } = view;
  useEffect(() => {
    const now = scene.current?.view();
    if (state === 'ready' && now !== undefined) {
      if (now.azimuth !== azimuth || now.elevation !== elevation || Math.abs(now.zoom - zoom) > 0.011) {
        scene.current?.look({ azimuth, elevation, zoom });
      }
    }
  }, [state, azimuth, elevation, zoom]);

  useEffect(() => {
    if (state === 'ready') {
      scene.current?.move({ frozen, glide: !reduced, spin: spin && !reduced });
    }
  }, [state, frozen, reduced, spin]);

  useEffect(() => {
    if (state === 'ready' && canvas.current !== null) {
      // The stage's own color is the site's, read where the stage is styled.
      const own = window.getComputedStyle(canvas.current).getPropertyValue(FINISH_TOKEN).trim();
      scene.current?.paint(finish, color ?? own);
    }
  }, [state, finish, color]);

  /**
   * Moves the view to another and hands it to the card.
   *
   * @param next The view to move to.
   */
  function go(next: ModelView): void {
    const built = scene.current;
    if (built !== null) {
      built.hold();
      built.look(next);
      onView(built.view());
    }
  }

  /**
   * Changes the view by the keyboard.
   *
   * @param event The key press on the stage.
   */
  function onKeyDown(event: KeyboardEvent): void {
    const now = scene.current?.view();
    if (now === undefined || frozen) {
      return;
    }
    const moves: Record<string, ModelView> = {
      ArrowLeft: { ...now, azimuth: now.azimuth - KEY_STEP.turn },
      ArrowRight: { ...now, azimuth: now.azimuth + KEY_STEP.turn },
      ArrowUp: { ...now, elevation: now.elevation + KEY_STEP.turn },
      ArrowDown: { ...now, elevation: now.elevation - KEY_STEP.turn },
      '+': { ...now, zoom: now.zoom * KEY_STEP.zoom },
      '=': { ...now, zoom: now.zoom * KEY_STEP.zoom },
      '-': { ...now, zoom: now.zoom / KEY_STEP.zoom },
      Home: home,
    };
    const next = moves[event.key];
    if (next !== undefined) {
      event.preventDefault();
      go(next);
    }
  }

  if (state === 'failed') {
    return <p className="ui-missing">{name} cannot be shown in 3D here.</p>;
  }
  return (
    <div ref={frame} className="ui-frame ui-model" data-state={state}>
      <canvas
        ref={canvas}
        className="ui-model-canvas"
        role="img"
        tabIndex={0}
        aria-label={`${name}, a 3D model seen from ${view.azimuth} degrees around and ${view.elevation} degrees up.${
          frozen ? '' : ' Drag to orbit and scroll to zoom, or use the arrow keys, plus, and minus; Home resets the view.'
        }`}
        onKeyDown={onKeyDown}
      />
      {state === 'loading' ? (
        <span className="ui-model-wait" role="status">
          <span className="spinner" aria-hidden="true" />
          Loading the model…
        </span>
      ) : (
        <span className="ui-badge bottom-1.5 left-1.5" aria-hidden="true">
          {view.azimuth}° · {view.elevation}° · {view.zoom}×
        </span>
      )}
      {frozen || state !== 'ready' ? null : (
        <button
          type="button"
          className="ui-icon-button ui-model-reset"
          aria-label="Reset the view"
          onClick={() => {
            go(home);
          }}
        >
          <RotateCcw className="size-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
