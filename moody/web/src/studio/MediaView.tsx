/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Media the agent generated or the person uploaded: images, videos, audio, and other files.
 *
 * Every address is a signed one that expires, so a file that no longer loads gives way to a quiet
 * placeholder naming it rather than a broken image. A video shows its first frame and plays
 * inline only when asked; it never autoplays with sound.
 * @module
 */
import { useState } from 'react';
import { FileText, ImageOff, Music } from 'lucide-react';
import type { Media } from '../lib/api';
import { cx } from '../lib/cx';

/** Props of {@link MediaView}. */
interface MediaViewProps {
  /** The file. */
  media: Media;
  /** A name for it when the file carries none, such as the asset's. */
  label?: string;
  /** Extra classes for the frame. */
  className?: string;
  /** Whether the view fills its frame, cropping, rather than showing the whole file. */
  cover?: boolean;
  /** Is handed the element that plays a video or a sound, and `null` when it goes, for a caller that follows its clock. */
  onPlayer?: (player: HTMLMediaElement | null) => void;
}

/**
 * Renders one file.
 *
 * @param props The component's props.
 * @returns The file's view.
 */
export function MediaView({ media, label, className, cover = false, onPlayer }: MediaViewProps) {
  const [failed, setFailed] = useState(false);
  const name = media.name ?? label ?? media.kind;
  const fail = (): void => {
    setFailed(true);
  };

  if (failed) {
    return (
      <div className={cx('grid place-items-center gap-1 bg-ink-800 p-4 text-center text-xs text-faint', className)}>
        <ImageOff className="size-5" aria-hidden="true" />
        <span>{name} is no longer available here.</span>
      </div>
    );
  }
  switch (media.kind) {
    case 'image':
      return (
        <img
          src={media.url}
          alt={name}
          loading="lazy"
          decoding="async"
          className={cx('block bg-ink-800', cover ? 'object-cover' : 'object-contain', className)}
          onError={fail}
        />
      );
    case 'video':
      return (
        <video
          ref={onPlayer}
          src={media.url}
          controls
          playsInline
          preload="metadata"
          aria-label={name}
          className={cx('block bg-black', cover ? 'object-cover' : 'object-contain', className)}
          onError={fail}
        />
      );
    case 'audio':
      return (
        <div className={cx('flex flex-col gap-2 rounded-xl border border-line bg-white/[0.03] p-3', className)}>
          <span className="flex items-center gap-2 text-sm text-muted">
            <Music className="size-4" aria-hidden="true" />
            <span className="truncate">{name}</span>
          </span>
          <audio ref={onPlayer} src={media.url} controls preload="metadata" className="w-full" onError={fail} />
        </div>
      );
    case 'file':
      return (
        <a
          href={media.url}
          target="_blank"
          rel="noopener noreferrer"
          className={cx('flex items-center gap-2 rounded-xl border border-line bg-white/[0.03] p-3 text-sm', className)}
        >
          <FileText className="size-4 text-muted" aria-hidden="true" />
          <span className="truncate">{name}</span>
        </a>
      );
  }
}
