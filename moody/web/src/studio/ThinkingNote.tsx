/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The agent's reasoning, as a quiet note the person can unfold (`thinking` in `moody/STUDIO.md`).
 *
 * It is not the answer and must not read as one: a single small line, folded, that says the agent
 * thought and how the thought begins. While the note is still being written the line is the
 * activity's own label from the catalog and follows the note's latest words instead, so the
 * person sees the reasoning move without it taking the page; the conversation plays the pixel
 * eyes beside it ({@link ThinkingEyes}). Unfolded, it is the whole note, small and muted, beside
 * a lavender rule.
 * @module
 */
import { ChevronRight, Sparkle } from 'lucide-react';
import { MoodyEyes } from '../components/MoodyEyes';
import { Prose } from './Prose';
import { showActivity } from './activity';

/** How much of a note its folded line shows, in characters. */
const PREVIEW_LENGTH = 140;

/** The catalog activity a note still being written is labeled with. */
const THINKING = 'thinking';

/**
 * The start of a note, for its folded line.
 *
 * @param text The note.
 * @returns Its first line, cut to the preview's length.
 */
function head(text: string): string {
  const line = text.trimStart().split('\n', 1)[0] ?? '';
  return line.length > PREVIEW_LENGTH ? `${line.slice(0, PREVIEW_LENGTH).trimEnd()}…` : line;
}

/**
 * The latest words of a note still being written, for its folded line.
 *
 * @param text The note so far.
 * @returns Its end, cut at a word to the preview's length.
 */
function tail(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  if (flat.length <= PREVIEW_LENGTH) {
    return flat;
  }
  const cut = flat.slice(-PREVIEW_LENGTH);
  return `…${cut.slice(cut.indexOf(' ') + 1)}`;
}

/**
 * Renders the eyes of an agent that is thinking, lavender as the intelligence at work is.
 *
 * @returns The eyes.
 */
export function ThinkingEyes() {
  return <MoodyEyes expression={showActivity(THINKING).expression} tone="active" />;
}

/** Props of {@link ThinkingNote}. */
interface ThinkingNoteProps {
  /** The reasoning, in the Markdown subset. */
  text: string;
  /** Whether it is still being written. */
  streaming: boolean;
}

/**
 * Renders a note of the agent's reasoning.
 *
 * @param props The component's props.
 * @returns The note, folded.
 */
export function ThinkingNote({ text, streaming }: ThinkingNoteProps) {
  return (
    <details className="thinking-note" data-streaming={streaming ? true : undefined}>
      <summary>
        {streaming ? null : <Sparkle className="size-3 flex-none" aria-hidden="true" />}
        <span className="thinking-label">{streaming ? `${showActivity(THINKING).label}…` : 'Thought'}</span>
        <span className="thinking-preview">{streaming ? tail(text) : head(text)}</span>
        <ChevronRight className="tool-chevron size-3.5 flex-none" aria-hidden="true" />
      </summary>
      <div className="thinking-body">
        <Prose text={text} />
      </div>
    </details>
  );
}
