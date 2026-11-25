/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Images that may not be there: the decorative art and the apps' official logos.
 *
 * Both are files delivered apart from the code (`lib/media.ts`). Art is drawn over a frame that
 * already paints the pixel grid (the `art` class), invisible until it has loaded and removed if it
 * fails, so a missing file leaves a finished panel. It rests in grayscale and blooms to color under
 * the pointer of a `bloom` ancestor (`styles.css`). A logo that fails gives way to the app's name
 * in text. Art is concept imagery, not a picture of the product, so it carries an empty `alt`;
 * a logo is content and says whose it is.
 * @module
 */
import { useState } from 'react';
import type { CatalogApp } from '../lib/catalog';
import { cx } from '../lib/cx';
import { appLogo } from '../lib/media';

/** Props of {@link ArtImage}. */
interface ArtImageProps {
  /** The address of the image. */
  src: string;
  /** The image's width in pixels, which with the height reserves its proportions. */
  width: number;
  /** The image's height in pixels. */
  height: number;
  /** Whether the image is the page's main visual: fetched at once and first, instead of lazily. */
  priority?: boolean;
  /** Extra classes for the image. */
  className?: string;
  /** Called when the image cannot be loaded, for a parent that draws something in its place. */
  onMissing?: () => void;
}

/**
 * Renders a decorative image that fills its frame once it has loaded.
 *
 * @param props The component's props.
 * @returns The image, or nothing after it failed to load.
 */
export function ArtImage({ src, width, height, priority = false, className, onMissing }: ArtImageProps) {
  const [state, setState] = useState<'pending' | 'loaded' | 'missing'>('pending');
  if (state === 'missing') {
    return null;
  }
  return (
    <img
      src={src}
      alt=""
      width={width}
      height={height}
      loading={priority ? 'eager' : 'lazy'}
      fetchPriority={priority ? 'high' : 'auto'}
      decoding="async"
      data-loaded={state === 'loaded'}
      className={cx('art-image', className)}
      onLoad={() => {
        setState('loaded');
      }}
      onError={() => {
        setState('missing');
        onMissing?.();
      }}
    />
  );
}

/** Props of {@link AppName}. */
interface AppNameProps {
  /** The app to name. */
  app: CatalogApp;
  /**
   * Classes for the logo, which set its height; its width follows from the artwork's proportions,
   * so the logo is never stretched or cropped.
   */
  logoClassName: string;
  /** Classes for the name when it is written as text. */
  textClassName: string;
}

/**
 * Names an app by its official logo where one was delivered, and in text otherwise.
 *
 * The logo is shown as its owner drew it: no recolor, no filter, its own proportions.
 *
 * @param props The component's props.
 * @returns The logo image or the name.
 */
export function AppName({ app, logoClassName, textClassName }: AppNameProps) {
  const logo = appLogo(app.id);
  const [failed, setFailed] = useState(false);
  if (logo === undefined || failed) {
    return <span className={textClassName}>{app.name}</span>;
  }
  return (
    <img
      src={logo.src}
      alt={`${app.name} logo`}
      width={logo.width}
      height={logo.height}
      decoding="async"
      className={cx('w-auto max-w-none object-contain', logoClassName)}
      onError={() => {
        setFailed(true);
      }}
    />
  );
}
