/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The layout components of a card: a stack, a row, a grid, and tabs.
 *
 * A card is as wide as the conversation lets it be, which on a phone is narrow, so the layouts
 * answer the card's own width (`ui.css` makes the card a container): a row's children wrap under
 * each other once they would be narrower than a control can be, and a grid gives up columns.
 *
 * Tabs follow the tabs pattern of the ARIA practices: one tab is in the tab order, the arrow
 * keys, Home, and End move between tabs and open the one they land on, and each panel is named
 * by its tab. A `tabs` with an id is also an answer, the open tab's value, which is how a card
 * asks "which of these directions" with a whole board per direction. Every panel stays mounted,
 * hidden while its tab is not open, so what the person set in one tab is still there when they
 * come back to it.
 * @module
 */
import { useState, type KeyboardEvent } from 'react';
import { cx } from '../../../lib/cx';
import { useCard } from '../context';
import { idOf, number, text } from '../tree';
import { tabValues } from '../values';
import type { ViewProps } from '../view';

/**
 * Renders children one under another, under a heading where the stack has a label.
 *
 * @param props The component's props.
 * @returns The stack.
 */
export function Stack({ node, render }: ViewProps) {
  const label = text(node, 'label');
  if (label === null) {
    return <div className="ui-stack">{node.children.map(render)}</div>;
  }
  return (
    <section className="ui-stack" aria-label={label}>
      <h4 className="ui-group-label">{label}</h4>
      {node.children.map(render)}
    </section>
  );
}

/**
 * Renders children side by side.
 *
 * @param props The component's props.
 * @returns The row.
 */
export function Row({ node, render }: ViewProps) {
  return <div className="ui-row">{node.children.map(render)}</div>;
}

/**
 * Renders children in equal columns.
 *
 * @param props The component's props.
 * @returns The grid.
 */
export function Grid({ node, render }: ViewProps) {
  return (
    <div className="ui-grid" data-columns={number(node, 'columns') ?? 2}>
      {node.children.map(render)}
    </div>
  );
}

/**
 * Renders tabs, one panel in view.
 *
 * @param props The component's props.
 * @returns The tab list and its panels.
 */
export function Tabs({ node, render }: ViewProps) {
  const card = useCard();
  const id = idOf(node);
  const values = tabValues(node);
  const [browsed, setBrowsed] = useState<number | null>(null);
  const answer = id === null ? -1 : values.findIndex((value) => value === card.state[id]);
  // On an open card with an id the answer is the open tab. Anywhere else it is the tab last
  // opened, starting from the answer: a locked card keeps its answer while its tabs are looked at.
  const open = id !== null && !card.frozen && answer !== -1 ? answer : (browsed ?? Math.max(answer, 0));
  const base = `${card.uid}-${node.path}`;

  /**
   * Opens a tab and moves the focus to it.
   *
   * @param index The tab's place, which wraps around at either end.
   */
  function show(index: number): void {
    const count = node.children.length;
    const next = (index + count) % count;
    setBrowsed(next);
    if (id !== null) {
      card.set(id, values[next]);
    }
    document.getElementById(`${base}-tab-${next}`)?.focus();
  }

  /**
   * Moves between tabs by the keyboard.
   *
   * @param event The key press on a tab.
   */
  function onKeyDown(event: KeyboardEvent): void {
    const moves: Record<string, number> = {
      ArrowRight: open + 1,
      ArrowLeft: open - 1,
      Home: 0,
      End: node.children.length - 1,
    };
    const target = moves[event.key];
    if (target !== undefined) {
      event.preventDefault();
      show(target);
    }
  }

  return (
    <div className="ui-tabs">
      <div className="ui-tablist" role="tablist" aria-label={text(node, 'label') ?? 'Views'}>
        {node.children.map((tab, index) => (
          <button
            key={tab.path}
            id={`${base}-tab-${index}`}
            type="button"
            role="tab"
            className="ui-tab"
            aria-selected={index === open}
            aria-controls={`${base}-panel-${index}`}
            tabIndex={index === open ? 0 : -1}
            data-answer={id !== null && index === answer ? 'true' : undefined}
            onClick={() => {
              show(index);
            }}
            onKeyDown={onKeyDown}
          >
            {text(tab, 'label')}
          </button>
        ))}
      </div>
      {node.children.map((tab, index) => (
        <div
          key={tab.path}
          id={`${base}-panel-${index}`}
          role="tabpanel"
          aria-labelledby={`${base}-tab-${index}`}
          className={cx('ui-stack', index !== open && 'hidden')}
        >
          {tab.children.map(render)}
        </div>
      ))}
    </div>
  );
}

/**
 * Renders one tab's children; `Tabs` draws them itself, so this serves a tab found anywhere else.
 *
 * @param props The component's props.
 * @returns The children as a stack.
 */
export function Tab({ node, render }: ViewProps) {
  return <div className="ui-stack">{node.children.map(render)}</div>;
}
