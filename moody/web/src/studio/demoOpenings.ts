/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How a project of the demo starts by its kind (`moody/STUDIO.md`, "Contract: starting a project
 * by its kind"): the card that asks the kind, as the control plane writes it.
 *
 * A project made without a format, in a discipline the catalog gives an opening question, opens
 * on {@link kindCard}: one `pick` of the discipline's formats in the catalog's order, each with
 * the line and the pixel icon its `kinds` entry names. Choosing locks it, and the message that
 * locks it sets the project's format before the agent's first turn.
 * @module
 */
import type { UiData } from '../lib/api';
import { asksKind, catalog, type Discipline } from '../lib/catalog';

/** What of a project the card that asks its kind sets, which is also the id of the card's one input. */
export const KIND_FIELD = 'format';

/**
 * Builds the card that asks a new project's kind.
 *
 * @param discipline The project's discipline.
 * @param id The card's identifier.
 * @returns The card, or `null` for a discipline that asks nothing first.
 */
export function kindCard(discipline: Discipline, id: string): UiData | null {
  if (discipline.opening === undefined || !asksKind(discipline)) {
    return null;
  }
  return {
    ui_id: id,
    title: discipline.opening,
    kind: 'components',
    spec: {
      type: 'pick',
      id: KIND_FIELD,
      options: discipline.formats.map((format) => {
        const kind = discipline.kinds?.[format];
        const icon = kind === undefined ? undefined : catalog.icons[kind.icon];
        return {
          value: format,
          label: format,
          ...(kind === undefined ? {} : { note: kind.note }),
          ...(icon === undefined ? {} : { icon }),
        };
      }),
    },
    submit: null,
    waits: true,
    instant: true,
    sets: KIND_FIELD,
    media: [],
  };
}

/**
 * Reads the kind a locked card chose.
 *
 * @param card The card the message locked.
 * @param value What it was locked with.
 * @returns The kind, or `null` for a card that sets none or a value that names none.
 */
export function chosenKind(card: UiData, value: unknown): string | null {
  if (card.sets !== KIND_FIELD || typeof value !== 'object' || value === null || !(KIND_FIELD in value)) {
    return null;
  }
  const chosen: unknown = value[KIND_FIELD];
  return typeof chosen === 'string' ? chosen : null;
}
