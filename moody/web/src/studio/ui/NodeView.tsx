/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Draws one node of a card's tree with the renderer the table names for it (`registry.ts`).
 *
 * A node whose `when` does not hold is not drawn at all, and so loses nothing: its value is the
 * card's state, not its own, and is there again when the condition holds.
 * @module
 */
import type { ReactNode } from 'react';
import { useCard } from './context';
import { COMPONENTS } from './registry';
import { holds, type UiNode } from './tree';

/** Props of {@link NodeView}. */
interface NodeViewProps {
  /** The node to draw. */
  node: UiNode;
}

/**
 * Draws a node inside another, keyed by its place in the tree.
 *
 * @param node The node.
 * @returns Its element.
 */
function renderNode(node: UiNode): ReactNode {
  return <NodeView key={node.path} node={node} />;
}

/**
 * Renders one component of a card.
 *
 * @param props The component's props.
 * @returns The component, or nothing while its condition does not hold.
 */
export function NodeView({ node }: NodeViewProps) {
  const card = useCard();
  if (!holds(node, card.state)) {
    return null;
  }
  const View = COMPONENTS[node.type].view;
  return <View node={node} render={renderNode} />;
}
