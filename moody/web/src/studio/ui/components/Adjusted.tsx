/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A picture or a video drawn with a look (`adjust.ts`), and the placeholder of a file that is gone.
 *
 * The look is CSS on the element: its filter functions, a color matrix where it scales or lifts
 * the channels (an inline SVG filter the element's `filter` names), and two layers over it for
 * grain and vignette. Nothing is drawn to a canvas, so a file from another origin shows as it
 * would in any `img`.
 *
 * Every address is a signed one that expires, and a card's file can be deleted from the library
 * after the card was shown, so a file that does not load gives way to {@link Missing}.
 * @module
 */
import { useId, useState, type ReactNode } from 'react';
import { ImageOff } from 'lucide-react';
import { hasMatrix, matrixOf, type Look } from '../adjust';
import type { UiMedia } from '../tree';

/** Props of {@link Missing}. */
interface MissingProps {
  /** What is not there, as the card named it. */
  name: string;
}

/**
 * Renders the quiet placeholder of a file the card names but cannot show.
 *
 * @param props The component's props.
 * @returns The placeholder.
 */
export function Missing({ name }: MissingProps) {
  return (
    <div className="ui-missing" role="img" aria-label={`${name} is not available here`}>
      <ImageOff className="size-4 flex-none" aria-hidden="true" />
      <span className="min-w-0 truncate">{name} is not available here.</span>
    </div>
  );
}

/** Props of {@link Adjusted}. */
interface AdjustedProps {
  /** The file, an image or a video. */
  media: UiMedia;
  /** What it is drawn with. */
  look: Look;
  /** What the picture is, for someone who cannot see it. */
  alt: string;
  /** Whether a video starts over when it ends. */
  loop?: boolean;
  /** Extra classes for the element. */
  className?: string;
  /** Called with the picture's own width and height once it has loaded. */
  onSize?: (width: number, height: number) => void;
}

/**
 * Renders a picture or a video under a look.
 *
 * @param props The component's props.
 * @returns The element with its layers, or the placeholder once it fails to load.
 */
export function Adjusted({ media, look, alt, loop = false, className, onSize }: AdjustedProps): ReactNode {
  const [failed, setFailed] = useState(false);
  // An id from React holds characters a CSS `url(#...)` would need escaped.
  const filterId = `ui-look-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  if (failed) {
    return <Missing name={media.name} />;
  }
  const matrix = hasMatrix(look);
  const filter = [matrix ? `url(#${filterId})` : null, ...look.filters].filter((part) => part !== null).join(' ');
  const style = filter === '' ? undefined : { filter };
  const fail = (): void => {
    setFailed(true);
  };
  return (
    <span className="ui-adjusted">
      {matrix ? (
        <svg className="ui-filter-defs" aria-hidden="true" focusable="false">
          <filter id={filterId} colorInterpolationFilters="sRGB">
            <feColorMatrix type="matrix" values={matrixOf(look)} />
          </filter>
        </svg>
      ) : null}
      {media.kind === 'video' ? (
        <video
          src={media.url}
          controls
          playsInline
          loop={loop}
          preload="metadata"
          aria-label={alt}
          className={className}
          style={style}
          onError={fail}
        />
      ) : (
        <img
          src={media.url}
          alt={alt}
          decoding="async"
          draggable={false}
          className={className}
          style={style}
          onError={fail}
          onLoad={(event) => {
            onSize?.(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight);
          }}
        />
      )}
      {look.grain > 0 ? <span className="ui-grain" style={{ opacity: look.grain }} aria-hidden="true" /> : null}
      {look.vignette > 0 ? (
        <span className="ui-vignette" style={{ opacity: look.vignette }} aria-hidden="true" />
      ) : null}
    </span>
  );
}
