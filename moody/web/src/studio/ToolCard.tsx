/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A tool call in the conversation: one line that unfolds to what the call came to, with the media
 * it produced below. The agent's own calls and a subagent's, inside its card, are drawn the same,
 * but for the size of the media: `compact` keeps a subagent's small, so its card stays a card.
 * @module
 */
import { Check, ChevronRight, CircleStop, LoaderCircle, X } from 'lucide-react';
import type { Media } from '../lib/api';
import { cx } from '../lib/cx';
import { MediaView } from './MediaView';
import type { ToolState } from './transcript';

/** How each state of a tool call is drawn and said. */
const TOOL_STATES: Readonly<Record<ToolState, { label: string; className: string }>> = {
  running: { label: 'Running', className: 'text-fg' },
  ok: { label: 'Done', className: 'text-ok' },
  failed: { label: 'Failed', className: 'text-bad' },
  stopped: { label: 'Stopped', className: 'text-faint' },
};

/** Props of {@link ToolCard}. */
interface ToolCardProps {
  /** What the call does. */
  title: string;
  /** The tool's name. */
  tool: string;
  /** Where the call stands. */
  state: ToolState;
  /** What it came to. */
  summary: string | null;
  /** What it produced. */
  media: Media[];
  /** Whether its media are shown small. */
  compact?: boolean;
}

/**
 * Renders a tool call as one line that unfolds to its outcome, with its media below.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function ToolCard({ title, tool, state, summary, media, compact = false }: ToolCardProps) {
  const look = TOOL_STATES[state];
  const Icon = state === 'running' ? LoaderCircle : state === 'ok' ? Check : state === 'failed' ? X : CircleStop;
  return (
    <div>
      <details className="tool-card">
        <summary className="flex min-h-9 items-center gap-2.5 px-3 py-1.5 text-sm">
          <Icon
            className={cx('size-3.5 flex-none', look.className, state === 'running' && 'animate-spin')}
            aria-label={look.label}
          />
          <span className="min-w-0 flex-1 truncate text-fg/90">{title}</span>
          {tool === '' ? null : <span className="mono hidden truncate text-xs text-faint sm:inline">{tool}</span>}
          <ChevronRight className="tool-chevron size-3.5 flex-none text-faint" aria-hidden="true" />
        </summary>
        <div className="border-t border-line px-3 py-2.5 text-sm text-muted">
          <p className="flex items-center gap-2">
            <span className={cx('font-medium', look.className)}>{look.label}</span>
            {tool === '' ? null : <span className="mono text-xs text-faint">{tool}</span>}
          </p>
          {summary === null || summary === '' ? null : <p className="mt-1.5 whitespace-pre-wrap">{summary}</p>}
        </div>
      </details>
      {media.length === 0 ? null : (
        <div className={cx('mt-2 grid gap-2', media.length > 1 && 'grid-cols-2', compact && 'max-w-64')}>
          {media.map((file, index) => (
            // A call's files never reorder, and two of them may share an address.
            <MediaTile key={`${index}:${file.url}`} media={file} single={media.length === 1} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Props of {@link MediaTile}. */
interface MediaTileProps {
  /** The file. */
  media: Media;
  /** Whether it is the only one, shown larger. */
  single: boolean;
}

/**
 * Renders one file a tool produced: an image opens full size in a new tab, a video plays inline.
 *
 * @param props The component's props.
 * @returns The tile.
 */
function MediaTile({ media, single }: MediaTileProps) {
  const frame = cx('overflow-hidden rounded-xl border border-line', single ? 'max-w-md' : '');
  if (media.kind === 'image') {
    return (
      <a href={media.url} target="_blank" rel="noopener noreferrer" className={cx('block', frame)}>
        <MediaView
          media={media}
          cover
          className="aspect-[3/2] w-full transition-transform duration-300 hover:scale-[1.02]"
        />
      </a>
    );
  }
  return (
    <div className={frame}>
      <MediaView media={media} className={media.kind === 'video' ? 'aspect-video w-full' : 'w-full'} />
    </div>
  );
}
