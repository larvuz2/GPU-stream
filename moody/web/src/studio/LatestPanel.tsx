/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The body of the Latest module of the right column: the newest version of the piece, at hand
 * whatever the conversation has moved on to.
 *
 * It plays the newest version the session showed and names it (`versions` in `transcript.ts`:
 * the previews the agent called a version, or failing one the newest video or sound). The
 * versions before it are listed under it, each one press away: the one pressed plays in the
 * newest one's place, until the person goes back or a newer version arrives. A second control
 * leads to where the version was shown in the conversation.
 *
 * Full screen is the browser's own, asked of the player's frame: a video or a picture fills the
 * screen, and a sound, which has nothing to fill it with, is shown under the version's name and
 * what the agent said of it. A browser that offers none (a phone's, which gives a video its own
 * full screen control) is not offered the button. Nothing plays by itself.
 * @module
 */
import { useRef, useState } from 'react';
import { AudioLines, Film, Image, Maximize2, MessageSquare, type LucideIcon } from 'lucide-react';
import type { Media } from '../lib/api';
import { MediaView } from './MediaView';
import type { Version } from './transcript';

/** The icon that says what kind of file a version is. */
const KIND_ICONS: Readonly<Record<Media['kind'], LucideIcon>> = {
  video: Film,
  audio: AudioLines,
  image: Image,
  file: Film,
};

/** Props of {@link LatestBody}. */
interface LatestBodyProps {
  /** The versions the session showed, the newest first. */
  versions: readonly Version[];
  /** Leads to where a version was shown in the conversation. */
  onShow: (version: Version) => void;
}

/**
 * Renders the newest version with its player, and the versions before it.
 *
 * @param props The component's props.
 * @returns The module's body, or nothing while there is no version.
 */
export function LatestBody({ versions, onShow }: LatestBodyProps) {
  const frame = useRef<HTMLDivElement>(null);
  // The version pressed in the list plays until a newer one arrives, which the newest's key tells.
  const [picked, setPicked] = useState<{ key: string; newest: string } | null>(null);
  const newest = versions[0];
  if (newest === undefined) {
    return null;
  }
  const playing =
    (picked?.newest === newest.key ? versions.find((version) => version.key === picked.key) : undefined) ?? newest;

  return (
    <div className="grid grid-cols-1 gap-3">
      <div ref={frame} className="latest-frame" data-kind={playing.media.kind}>
        <div className="latest-name">
          <p className="text-2xl font-semibold tracking-tight">{playing.label ?? 'The newest the session showed'}</p>
          <p className="mt-2 text-sm leading-relaxed text-muted">{playing.caption}</p>
        </div>
        <MediaView
          key={playing.key}
          media={playing.media}
          label={playing.label ?? playing.caption}
          className={playing.media.kind === 'audio' ? 'border-0 bg-transparent' : 'aspect-video w-full'}
        />
      </div>
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold tracking-tight">
            {playing.label ?? 'The newest the session showed'}
            {playing === newest ? null : <span className="font-normal text-faint"> · an earlier version</span>}
          </p>
          <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted">{playing.caption}</p>
        </div>
        <button
          type="button"
          className="icon-btn icon-btn-sm"
          aria-label="Show it in the conversation"
          title="Show it in the conversation"
          onClick={() => {
            onShow(playing);
          }}
        >
          <MessageSquare aria-hidden="true" />
        </button>
        {document.fullscreenEnabled ? (
          <button
            type="button"
            className="icon-btn icon-btn-sm"
            aria-label="Full screen"
            title="Full screen"
            onClick={() => {
              frame.current?.requestFullscreen().catch(() => {
                // Refused by the browser: the player stays where it is.
              });
            }}
          >
            <Maximize2 aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {versions.length < 2 ? null : (
        <div>
          <h3 className="section-label">
            Versions <span className="font-normal tracking-normal tabular-nums">{versions.length}</span>
          </h3>
          <ul className="mt-1.5 grid grid-cols-1 gap-0.5">
            {versions.map((version) => {
              const Icon = KIND_ICONS[version.media.kind];
              return (
                <li key={version.key}>
                  <button
                    type="button"
                    className="version-row"
                    aria-current={version === playing ? 'true' : undefined}
                    onClick={() => {
                      setPicked(version === newest ? null : { key: version.key, newest: newest.key });
                    }}
                  >
                    <Icon className="size-3.5 flex-none text-faint" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">{version.label ?? version.caption}</span>
                    {version === newest ? <span className="text-[0.6875rem] text-faint">Latest</span> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
