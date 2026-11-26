/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's 3D model: a stage the person orbits, whose finish, color, and turning can follow the
 * card's inputs, and whose view is an answer where the model has an id.
 *
 * The stage and the 3D library it needs are a chunk of their own (`ModelStage.tsx`), fetched the
 * first time a card shows a model, so a conversation without one never downloads them. Until the
 * chunk arrives the frame holds its place.
 *
 * The view the person leaves the model at is kept here in every case, so the stage's readout
 * follows the hand; with an id it is also the card's value, which is how a card asks "from which
 * angle" and gets back two angles and a zoom the agent can frame a render by.
 * @module
 */
import { lazy, Suspense, useState } from 'react';
import { isBoolean, isString } from '../../../lib/narrow';
import { isFinishName, type FinishName } from '../catalog';
import { useCard } from '../context';
import { bound, idOf, text } from '../tree';
import { isModelView, STARTS, type ModelView } from '../values';
import { useInput, type ViewProps } from '../view';
import { Missing } from './Adjusted';

const ModelStage = lazy(() => import('./ModelStage'));

/** The finish of a model whose card names none, or one this build does not draw. */
const PLAIN: FinishName = 'original';

/**
 * Renders a 3D model.
 *
 * @param props The component's props.
 * @returns The stage, or its placeholder where the card does not carry the model.
 */
export function Model({ node }: ViewProps) {
  const card = useCard();
  const input = useInput(node);
  const media = card.media(node.props.src);
  const home = STARTS.model(node);
  const [seen, setSeen] = useState<ModelView>(home);
  const answers = idOf(node) !== null;
  const view = answers && isModelView(input.value) ? input.value : seen;
  const finish = bound(node, 'finish', card.state);
  const color = bound(node, 'color', card.state);
  const spin = bound(node, 'spin', card.state);
  if (media === null) {
    return <Missing name={text(node, 'src') ?? 'A model'} />;
  }
  return (
    <Suspense
      fallback={
        <div className="ui-frame ui-model" data-state="loading">
          <span className="ui-model-wait" role="status">
            <span className="spinner" aria-hidden="true" />
            Loading the model…
          </span>
        </div>
      }
    >
      <ModelStage
        url={media.url}
        name={text(node, 'label') ?? media.name}
        view={view}
        home={home}
        finish={isString(finish) && isFinishName(finish) ? finish : PLAIN}
        color={isString(color) ? color : null}
        spin={isBoolean(spin) ? spin : false}
        frozen={card.frozen}
        onView={(next) => {
          setSeen(next);
          if (answers) {
            input.set(next);
          }
        }}
      />
    </Suspense>
  );
}
