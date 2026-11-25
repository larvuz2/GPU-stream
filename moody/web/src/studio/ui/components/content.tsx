/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What a card shows: text, a picture, a video, a gallery, a before and after pair, and a palette.
 *
 * A picture and a video take a look (`adjust.ts`) whose amounts can follow the card's inputs, so
 * a slider's change is seen on the same frame. A text shows inputs' values where it names them as
 * `{id}`. A before and after pair is two pictures under one divider, the after picture carrying
 * the look, which is how a card compares a grade with what it started from; the divider is a
 * native range input laid over the pair, so it moves by pointer, touch, and the arrow keys.
 * @module
 */
import { useId, useState, type ReactNode } from 'react';
import { Maximize2 } from 'lucide-react';
import { Dialog } from '../../../components/Dialog';
import { isString } from '../../../lib/narrow';
import { lookOf, type Look } from '../adjust';
import { useCard } from '../context';
import { fill, items, number, text, type UiMedia } from '../tree';
import type { ViewProps } from '../view';
import { Adjusted, Missing } from './Adjusted';

/** A look that changes nothing. */
const PLAIN: Look = { filters: [], scale: [1, 1, 1], lift: 0, grain: 0, vignette: 0 };

/** The shape a frame takes until its picture has loaded and said its own. */
const DEFAULT_ASPECT = '16 / 9';

/**
 * Renders a line or a paragraph, with inputs' values in its `{id}` places.
 *
 * @param props The component's props.
 * @returns The text.
 */
export function Text({ node }: ViewProps) {
  const card = useCard();
  const words = fill(text(node, 'text') ?? '', card.words);
  const tone = text(node, 'tone') ?? 'body';
  if (tone === 'heading') {
    return <h4 className="ui-text-heading">{words}</h4>;
  }
  // A readout changes as the person moves an input, which assistive technology is told politely.
  return (
    <p className={`ui-text-${tone}`} aria-live={tone === 'readout' ? 'polite' : undefined}>
      {words}
    </p>
  );
}

/** Props of {@link Captioned}. */
interface CaptionedProps {
  /** The words under the frame, or `null` for none. */
  caption: string | null;
  /** The frame. */
  children: ReactNode;
}

/**
 * Renders a frame with its caption under it.
 *
 * @param props The component's props.
 * @returns The figure.
 */
function Captioned({ caption, children }: CaptionedProps) {
  const card = useCard();
  return (
    <figure className="ui-figure">
      {children}
      {caption === null ? null : <figcaption className="ui-caption">{fill(caption, card.words)}</figcaption>}
    </figure>
  );
}

/**
 * Renders a picture under its look.
 *
 * @param props The component's props.
 * @returns The picture, or its placeholder where the card does not carry it.
 */
export function Image({ node }: ViewProps) {
  const card = useCard();
  const media = card.media(node.props.src);
  const caption = text(node, 'caption');
  if (media === null) {
    return <Missing name={text(node, 'src') ?? 'A picture'} />;
  }
  return (
    <Captioned caption={caption}>
      <div className="ui-frame">
        <Adjusted
          media={media}
          look={lookOf(node.props.adjust, card.state)}
          alt={caption ?? media.name}
          className="ui-picture"
        />
      </div>
    </Captioned>
  );
}

/**
 * Renders a video under its look.
 *
 * @param props The component's props.
 * @returns The player, or its placeholder where the card does not carry the file.
 */
export function Video({ node }: ViewProps) {
  const card = useCard();
  const media = card.media(node.props.src);
  const caption = text(node, 'caption');
  if (media === null) {
    return <Missing name={text(node, 'src') ?? 'A video'} />;
  }
  return (
    <Captioned caption={caption}>
      <div className="ui-frame">
        <Adjusted
          media={media}
          look={lookOf(node.props.adjust, card.state)}
          alt={caption ?? media.name}
          loop={node.props.loop === true}
          className="ui-picture"
        />
      </div>
    </Captioned>
  );
}

/** Props of {@link Thumbnail}. */
interface ThumbnailProps {
  /** The file. */
  media: UiMedia;
  /** The words under it, or `null`. */
  caption: string | null;
}

/**
 * Renders one picture of a gallery, which opens larger in a dialog.
 *
 * @param props The component's props.
 * @returns The thumbnail and its dialog.
 */
function Thumbnail({ media, caption }: ThumbnailProps) {
  const [open, setOpen] = useState(false);
  const title = useId();
  const name = caption ?? media.name;
  return (
    <figure className="ui-figure">
      <button
        type="button"
        className="ui-frame ui-thumb group"
        aria-label={`Open ${name} larger`}
        onClick={() => {
          setOpen(true);
        }}
      >
        {media.kind === 'video' ? (
          <video src={media.url} muted playsInline preload="metadata" className="ui-cover" />
        ) : (
          <img src={media.url} alt="" loading="lazy" decoding="async" className="ui-cover" />
        )}
        <span className="ui-badge right-1.5 bottom-1.5 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100">
          <Maximize2 className="size-3" aria-hidden="true" />
        </span>
      </button>
      {caption === null ? null : <figcaption className="ui-caption">{caption}</figcaption>}
      <Dialog
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        labelledBy={title}
        wide
      >
        <p id={title} className="mono truncate pr-10 text-xs text-muted">
          {name}
        </p>
        <div className="mt-3">
          <Adjusted media={media} look={PLAIN} alt={name} className="max-h-[72dvh] w-full rounded-lg bg-black object-contain" />
        </div>
      </Dialog>
    </figure>
  );
}

/**
 * Renders pictures in a grid.
 *
 * @param props The component's props.
 * @returns The gallery.
 */
export function Gallery({ node }: ViewProps) {
  const card = useCard();
  return (
    <div className="ui-grid" data-columns={number(node, 'columns') ?? 3}>
      {items(node, 'items', 'picture').map((item, index) => {
        const media = card.media(item.src);
        // A gallery's pictures never reorder, and two of them may be the same file.
        const key = `${index}:${isString(item.src) ? item.src : ''}`;
        return media === null ? (
          <Missing key={key} name={isString(item.src) ? item.src : 'A picture'} />
        ) : (
          <Thumbnail key={key} media={media} caption={isString(item.caption) ? item.caption : null} />
        );
      })}
    </div>
  );
}

/**
 * Renders two pictures under one divider: before on its left, after, with the look, on its right.
 *
 * @param props The component's props.
 * @returns The pair, or a placeholder where the card does not carry both.
 */
export function Compare({ node }: ViewProps) {
  const card = useCard();
  const [split, setSplit] = useState(50);
  const [aspect, setAspect] = useState(DEFAULT_ASPECT);
  const before = card.media(node.props.before);
  const after = card.media(node.props.after);
  if (before === null || after === null) {
    return <Missing name="The before and after pair" />;
  }
  return (
    <div className="ui-frame ui-compare" style={{ aspectRatio: aspect }}>
      <Adjusted
        media={after}
        look={lookOf(node.props.adjust, card.state)}
        alt={`After: ${after.name}`}
        className="ui-fill"
        onSize={(width, height) => {
          if (width > 0 && height > 0) {
            setAspect(`${width} / ${height}`);
          }
        }}
      />
      <div className="ui-compare-before" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
        <Adjusted media={before} look={PLAIN} alt={`Before: ${before.name}`} className="ui-fill" />
      </div>
      <span className="ui-compare-divider" style={{ left: `${split}%` }} aria-hidden="true" />
      <span className="ui-badge top-1.5 left-1.5" aria-hidden="true">
        Before
      </span>
      <span className="ui-badge top-1.5 right-1.5" aria-hidden="true">
        After
      </span>
      <input
        type="range"
        min={0}
        max={100}
        value={split}
        aria-label="How much of the picture shows as it was before"
        className="ui-compare-range"
        onChange={(event) => {
          setSplit(event.target.valueAsNumber);
        }}
      />
    </div>
  );
}

/**
 * Renders a palette: its name, and each color with what it is called.
 *
 * @param props The component's props.
 * @returns The palette.
 */
export function Swatches({ node }: ViewProps) {
  const label = text(node, 'label');
  const colors = items(node, 'colors', 'swatch').flatMap((item) =>
    isString(item.color) ? [{ color: item.color, label: isString(item.label) ? item.label : null }] : [],
  );
  return (
    <div className="ui-palette">
      {label === null ? null : <p className="ui-label">{label}</p>}
      <ul className="ui-swatches" aria-label={label ?? 'Palette'}>
        {colors.map((swatch, index) => (
          // A palette's colors never reorder, and it may hold one color twice.
          <li key={`${index}:${swatch.color}`} className="ui-swatch">
            <span className="ui-swatch-color" style={{ background: swatch.color }} aria-hidden="true" />
            <span className="ui-swatch-name">{swatch.label ?? swatch.color.toUpperCase()}</span>
            {swatch.label === null ? null : <span className="ui-swatch-hex">{swatch.color.toUpperCase()}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
