/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What every component's renderer is given, and what an input reads of its card.
 *
 * A renderer draws one node. Whatever is inside it is drawn through `render`, which the card
 * supplies, so a layout component decides which of its children are in view (a `tabs` draws one
 * tab's) without importing the table of renderers it is itself registered in.
 * @module
 */
import type { ReactNode } from 'react';
import { useCard } from './context';
import { idOf, text, type UiNode } from './tree';

/** Props of a component's renderer. */
export interface ViewProps {
  /** The component to draw. */
  node: UiNode;
  /** Draws a component inside this one. */
  render: (node: UiNode) => ReactNode;
}

/** A component's renderer. */
export type View = (props: ViewProps) => ReactNode;

/** What an input reads of its card. */
export interface InputBinding {
  /** Its value now. */
  value: unknown;
  /** Replaces its value. */
  set: (value: unknown) => void;
  /** Whether the card is locked in, so the control shows its value and takes no change. */
  frozen: boolean;
  /** The `id` of its control in the document, unique to this card. */
  domId: string;
  /** The words that name it: its label, else its id as words. */
  label: string;
  /** Whether the card gave it a label to show; without one the name is for assistive technology only. */
  labeled: boolean;
}

/**
 * Binds a component that answers to its card's state.
 *
 * @param node The component.
 * @returns Its value, the function that sets it, and how its control is named.
 */
export function useInput(node: UiNode): InputBinding {
  const card = useCard();
  const id = idOf(node);
  const label = text(node, 'label');
  return {
    value: id === null ? undefined : card.state[id],
    set: (value) => {
      if (id !== null) {
        card.set(id, value);
      }
    },
    frozen: card.frozen,
    domId: `${card.uid}-${id ?? node.path}`,
    label: label ?? (id ?? node.type).replaceAll('_', ' '),
    labeled: label !== null,
  };
}
