/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * An interactive card: what the agent shows when the answer is something to see, play with, and
 * lock in (the `ui` event of `moody/STUDIO.md`).
 *
 * The card is the intelligence's, so its frame is the conversation's lavender one (`.ai-card`),
 * and the one lime thing in it is the person's: the lock-in button. A card is one of two kinds
 * under the same frame. A `components` card is a tree of the catalog's components
 * (`moody/ui.json`), drawn here by the table of renderers (`registry.ts`) over one piece of state,
 * `{id: value}`, which every input writes and every picture, text, and condition reads
 * (`context.ts`). An `html` card is a document of the agent's own, run in a sandboxed frame
 * (`HtmlCard.tsx`).
 *
 * A card has three states, and says which it is in:
 *
 * - **Open and live**: the controls change the card, and the lock-in button sends its state to
 *   `onSubmit`. A required choice not yet made holds the button and names what is missing.
 * - **Open but not live**: the controls still work, so the card can be explored, but it cannot be
 *   answered now (the agent is working, or the conversation moved past it), and it says so.
 * - **Locked**: the controls show what was locked in and take no change, and the card lists it.
 *
 * The state lives here, not in the event: the page's event log is append-only and polled, and a
 * card's data may arrive again with fresh signed addresses, which must not reset what the person
 * set. The tree is keyed by each node's place in it, so a card re-read keeps its controls.
 * @module
 */
import { useId, useMemo, useState } from 'react';
import { isRecord } from '../../lib/narrow';
import { inputsOf, missing, startState, summarize, wordsOf } from './answer';
import { CardContext, type Card } from './context';
import { HtmlCard } from './HtmlCard';
import { LockBar } from './LockBar';
import { NodeView } from './NodeView';
import { readTree, type UiData, type UiMedia } from './tree';
import './ui.css';

/** Props of {@link UiCard}. */
export interface UiCardProps {
  /** The `ui` event's data. */
  ui: UiData;
  /** What the person locked in, `null` while the card is open. */
  locked: { value: unknown } | null;
  /** Whether the card can be answered now. */
  live: boolean;
  /** Locks the card in with its value. */
  onSubmit: (value: unknown) => void;
}

/**
 * Renders an interactive card.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function UiCard({ ui, locked, live, onSubmit }: UiCardProps) {
  const title = useId();
  const state = locked !== null ? 'Locked in' : ui.submit === null ? 'Take a look' : live ? 'Your call' : 'On hold';
  return (
    <section
      className="ai-card ui-card"
      aria-labelledby={title}
      data-kind={ui.kind}
      data-locked={locked !== null}
      data-ui={ui.ui_id}
    >
      <header className="ui-card-head">
        <p className="ai-label">{state}</p>
        <h3 id={title} className="ui-card-title">
          {ui.title}
        </h3>
      </header>
      {ui.kind === 'html' ? (
        <HtmlCard ui={ui} locked={locked} live={live} onSubmit={onSubmit} />
      ) : (
        <ComponentsCard ui={ui} locked={locked} live={live} onSubmit={onSubmit} />
      )}
    </section>
  );
}

/**
 * Renders a card made of the catalog's components, over the state its inputs share.
 *
 * @param props The component's props.
 * @returns The components and the lock-in bar.
 */
function ComponentsCard({ ui, locked, live, onSubmit }: UiCardProps) {
  const uid = useId();
  const root = useMemo(() => readTree(ui.spec), [ui.spec]);
  const inputs = useMemo(() => (root === null ? new Map<string, never>() : inputsOf(root)), [root]);
  const start = useMemo(() => startState(inputs), [inputs]);
  const [changes, setChanges] = useState<Record<string, unknown>>({});
  const files = useMemo(() => new Map(ui.media.map((file): [string, UiMedia] => [file.name, file])), [ui.media]);

  const frozen = locked !== null;
  const state = useMemo(
    () => ({ ...start, ...(locked === null ? changes : isRecord(locked.value) ? locked.value : {}) }),
    [start, changes, locked],
  );
  const card = useMemo(
    (): Card => ({
      state,
      set: (id, value) => {
        if (!frozen) {
          setChanges((current) => ({ ...current, [id]: value }));
        }
      },
      media: (name) => (typeof name === 'string' ? (files.get(name) ?? null) : null),
      frozen,
      words: (id) => {
        const node = inputs.get(id);
        return node === undefined ? '' : wordsOf(node, state[id]);
      },
      uid,
    }),
    [state, frozen, files, inputs, uid],
  );

  if (root === null) {
    return <p className="ui-text-muted">This card cannot be shown here.</p>;
  }
  const unchosen = missing(root, inputs, state);
  return (
    <CardContext value={card}>
      <div className="ui-body">
        <NodeView node={root} />
      </div>
      <LockBar
        label={ui.submit}
        locked={frozen}
        live={live}
        blocked={unchosen === null ? null : `Still to choose: ${unchosen}`}
        summary={frozen ? summarize(inputs, state) : []}
        onLock={() => {
          onSubmit(state);
        }}
      />
    </CardContext>
  );
}
