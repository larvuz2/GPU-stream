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
 *   `onSubmit`. A required choice not yet made holds the button and names what is missing. Once
 *   anything differs from how the card opened, the foot offers the way back to that.
 * - **Open but not live**: the controls still work, so the card can be explored, but it cannot be
 *   answered now (the agent is working, or the conversation moved past it), and it says so.
 * - **Locked**: the controls show what was locked in and take no change, and the card lists it.
 *
 * A card may be `instant`: it has one input, a single choice, and no lock-in button. Its choices
 * are buttons, and pressing one sends the card's state at once. Until the log shows it locked,
 * the card holds the choice and takes no second one; while it cannot be answered, its choices
 * cannot be pressed.
 *
 * The state lives here, not in the event: the page's event log is append-only and polled, and a
 * card's data may arrive again with fresh signed addresses, which must not reset what the person
 * set. The tree is keyed by each node's place in it, so a card re-read keeps its controls.
 * @module
 */
import { useId, useMemo, useState } from 'react';
import { isRecord } from '../../lib/narrow';
import { changed, inputsOf, missing, startState, summarize, wordsOf } from './answer';
import { CardContext, type Card, type UploadFile } from './context';
import { useSending } from './hooks';
import { HtmlCard } from './HtmlCard';
import { LockBar } from './LockBar';
import { NodeView } from './NodeView';
import { instantOf, readTree, type UiData, type UiMedia } from './tree';
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
  /**
   * What the person had already changed on a `components` card, by input id, where whoever draws
   * the card kept it: the card shows these in place of the values it opens with, and still knows
   * how it opened. The gallery shows a card in the middle of a decision with it.
   */
  draft?: Record<string, unknown>;
  /**
   * Takes a file the person gave a card's `upload` input into the project's library. A page that
   * passes none cannot take files, and such an input says so.
   */
  onUpload?: UploadFile;
}

/**
 * Renders an interactive card.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function UiCard({ ui, locked, live, onSubmit, draft, onUpload }: UiCardProps) {
  const title = useId();
  const asks = ui.submit !== null || instantOf(ui);
  const state = locked !== null ? 'Locked in' : !asks ? 'Take a look' : live ? 'Your call' : 'On hold';
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
        <ComponentsCard ui={ui} locked={locked} live={live} onSubmit={onSubmit} draft={draft} onUpload={onUpload} />
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
function ComponentsCard({ ui, locked, live, onSubmit, draft, onUpload }: UiCardProps) {
  const uid = useId();
  const root = useMemo(() => readTree(ui.spec), [ui.spec]);
  const inputs = useMemo(() => (root === null ? new Map<string, never>() : inputsOf(root)), [root]);
  const start = useMemo(() => startState(inputs), [inputs]);
  const [changes, setChanges] = useState<Record<string, unknown>>(() => draft ?? {});
  const files = useMemo(() => new Map(ui.media.map((file): [string, UiMedia] => [file.name, file])), [ui.media]);
  const [sounds] = useState(() => new Set<HTMLAudioElement>());
  const [sending, send] = useSending();

  const frozen = locked !== null;
  // Only a card of one input can lock on a choice: there is nothing else to set first.
  const instant = instantOf(ui) && inputs.size === 1;
  const state = useMemo(
    () => ({ ...start, ...(locked === null ? changes : isRecord(locked.value) ? locked.value : {}) }),
    [start, changes, locked],
  );
  const card = useMemo(
    (): Card => ({
      state,
      set: (id, value) => {
        if (frozen || (instant && (!live || sending))) {
          return;
        }
        setChanges((current) => ({ ...current, [id]: value }));
        if (instant) {
          send();
          onSubmit({ ...state, [id]: value });
        }
      },
      media: (name) => (typeof name === 'string' ? (files.get(name) ?? null) : null),
      // An instant card that cannot be answered, or whose choice is on its way, takes no press.
      frozen: frozen || (instant && (!live || sending)),
      instant,
      upload: onUpload ?? null,
      sounds,
      words: (id) => {
        const node = inputs.get(id);
        return node === undefined ? '' : wordsOf(node, state[id]);
      },
      uid,
    }),
    [state, frozen, instant, live, sending, send, onSubmit, onUpload, sounds, files, inputs, uid],
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
        label={instant ? null : ui.submit}
        instant={instant ? (sending ? 'sending' : 'open') : undefined}
        locked={frozen}
        live={live}
        blocked={unchosen === null ? null : `Still to choose: ${unchosen}`}
        summary={frozen ? summarize(root, inputs, state) : []}
        changed={!frozen && !instant && changed(inputs, state, start)}
        onDefault={() => {
          setChanges({});
        }}
        onLock={() => {
          onSubmit(state);
        }}
      />
    </CardContext>
  );
}
