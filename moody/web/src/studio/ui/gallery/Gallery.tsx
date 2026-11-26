/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The development gallery of interactive cards: every example as it would sit in a conversation.
 *
 * Each card is drawn in a column laid out as the studio's conversation is (the person's message
 * on the right, the agent's mark, prose, and card in its gutter), on the studio's own stylesheet,
 * so what is seen here is what the product shows. The gallery stands in for the agent's loop:
 * locking a card in keeps the value it was handed, renders the card locked, and shows the message
 * the conversation would send, with the value as JSON beneath it. That is also what the
 * end-to-end checks read (`data-answer`).
 *
 * `?only=<id>` shows one card alone, for a screenshot or a check of that card, and
 * `#card=<a show_ui call>` shows the card that call would make (`try.ts`).
 * @module
 */
import { useState } from 'react';
import { MoodyFace } from '../../../components/Moody';
import { describeAnswer } from '../answer';
import { UiCard } from '../UiCard';
import { EXAMPLES, type Example } from './examples';
import { cardFromAddress } from './try';

/** Props of {@link Exchange}. */
interface ExchangeProps {
  /** The card and the exchange it answers. */
  example: Example;
}

/**
 * Renders one exchange: the person's message, the agent's words and card, and the answer once locked in.
 *
 * @param props The component's props.
 * @returns The exchange, as entries of the conversation's list.
 */
function Exchange({ example }: ExchangeProps) {
  const [answer, setAnswer] = useState<{ value: unknown } | null>(
    example.locked === undefined ? null : { value: example.locked },
  );
  const sent = answer !== null && example.locked === undefined;
  return (
    <section id={example.id} aria-label={example.ui.title} className="grid grid-cols-1 gap-y-3">
      <div className="message-user">{example.asked}</div>
      <div className="flex gap-3">
        <span className="w-7 flex-none pt-0.5">
          <span className="agent-mark" title="Agent">
            <MoodyFace className="h-6" />
          </span>
        </span>
        <div className="grid min-w-0 flex-1 grid-cols-1 gap-y-3">
          <p className="prose-studio">{example.says}</p>
          <UiCard
            ui={example.ui}
            locked={answer}
            live={example.idle !== true}
            onSubmit={(value) => {
              setAnswer({ value });
            }}
          />
        </div>
      </div>
      {sent ? (
        <div className="message-user">
          {describeAnswer(example.ui, answer.value)}
          <pre className="mono mt-2 overflow-x-auto text-xs text-muted" data-answer={example.ui.ui_id}>
            {JSON.stringify(answer.value, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}

/**
 * Renders the gallery.
 *
 * @returns The page.
 */
export function Gallery() {
  const only = new URLSearchParams(window.location.search).get('only');
  const tried = cardFromAddress();
  const shown = tried !== null ? [tried] : only === null ? EXAMPLES : EXAMPLES.filter((example) => example.id === only);
  return (
    <main className="mx-auto w-full max-w-[46rem] px-4 pt-6 pb-16 sm:px-6">
      {only === null && tried === null ? (
        <header className="mb-8">
          <p className="eyebrow">Development</p>
          <h1 className="display mt-2 text-2xl">Interactive cards</h1>
          <p className="lede mt-2 text-sm">
            Every kind of card the agent can answer with, each as it sits in a conversation. Lock one in to see what
            goes back to the agent.
          </p>
        </header>
      ) : null}
      <div className="grid grid-cols-1 gap-y-10">
        {shown.map((example) => (
          <Exchange key={example.id} example={example} />
        ))}
      </div>
    </main>
  );
}
