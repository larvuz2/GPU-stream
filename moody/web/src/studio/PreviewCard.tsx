/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A preview: work in progress the agent shows in the conversation (`preview` in `moody/STUDIO.md`).
 *
 * The card is the intelligence's, so it is lavender (`.ai-card`, `.ai-label`), compact, and
 * labeled "Work in progress": it must never read as a deliverable, which is the plain bordered
 * tile a tool's finished media gets. It shows whatever the agent chose to render, of any kind
 * and length: a picture that opens larger, sound and video that play in place, a before and
 * after pair, and any other file as a row that opens it.
 *
 * A long turn can show many previews, and each address is a signed one fetched on demand, so the
 * card stays light. A picture loads lazily. Sound and video are given their address only once
 * the card is near the view ({@link useNearView}), and then only their metadata is fetched: the
 * first frame and the length, never the file, until the person plays it. Nothing autoplays. A
 * file that fails to load says so quietly; its address is its identity here, so one the log later
 * returns under a fresh address is loaded again.
 *
 * A pair of pictures is compared under one slider: the "after" picture lies under the "before",
 * which is clipped at the handle. The slider is a native range input laid over the pair, so it
 * works by pointer, touch, and the arrow keys with no handler of its own. A pair of anything
 * else sits side by side under "Before" and "After".
 * @module
 */
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from 'react';
import { FileText, ImageOff, Maximize2, Music } from 'lucide-react';
import { Dialog } from '../components/Dialog';
import type { PreviewItem } from '../lib/api';
import { cx } from '../lib/cx';

/** How far outside the view, in CSS pixels, a card's sound and video are given their address. */
const NEAR_VIEW_MARGIN = '600px';

/** The shape a frame takes for a file whose size on screen is not known. */
const DEFAULT_ASPECT = '16 / 9';

/**
 * Says whether an element has come near the view, and stays true once it has.
 *
 * @returns The ref to put on the element, and whether it has been near the view.
 */
function useNearView<T extends Element>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (element === null || near) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
        }
      },
      { rootMargin: NEAR_VIEW_MARGIN },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, [near]);
  return [ref, near];
}

/**
 * Writes a length as a person reads one: `0:07`, `3:49`, `1:02:10`.
 *
 * @param seconds The length in seconds.
 * @returns The length as minutes and seconds, with hours where there are any.
 */
function clock(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = String(whole % 60).padStart(2, '0');
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

/**
 * The shape of a file's frame, from its size on screen where that is known.
 *
 * @param file The file.
 * @returns A CSS `aspect-ratio` value.
 */
function aspect(file: PreviewItem): string {
  return file.width !== undefined && file.height !== undefined && file.width > 0 && file.height > 0
    ? `${file.width} / ${file.height}`
    : DEFAULT_ASPECT;
}

/** Props of {@link PreviewCard}. */
interface PreviewCardProps {
  /** What the preview shows, in the agent's words. */
  caption: string;
  /** The files, in the order to show them. */
  files: PreviewItem[];
  /** Whether two files are a before and after pair, the one before first. */
  compare: boolean;
  /** The name of the engine they came from, where it is known. */
  engine: string | null;
}

/**
 * Renders one preview as a work-in-progress card.
 *
 * @param props The component's props.
 * @returns The card.
 */
export function PreviewCard({ caption, files, compare, engine }: PreviewCardProps) {
  const [before, after] = files;
  const pair = compare && files.length === 2 && before !== undefined && after !== undefined;
  const pictures = files.filter((file) => file.kind === 'image');
  const others = files.filter((file) => file.kind !== 'image');
  return (
    <figure className="ai-card preview-card max-w-lg rounded-2xl p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="ai-label">Work in progress</p>
        {engine === null ? null : <span className="mono truncate text-[0.6875rem] text-faint">{engine}</span>}
      </div>
      <figcaption className="mt-1.5 text-sm leading-snug text-fg/90">{caption}</figcaption>
      {files.length === 0 ? (
        <Gone name="This preview" />
      ) : pair && before.kind === 'image' && after.kind === 'image' ? (
        <ComparePictures key={`${before.url} ${after.url}`} before={before} after={after} />
      ) : pair ? (
        <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Side label="Before">
            <PreviewFile key={before.url} file={before} />
          </Side>
          <Side label="After">
            <PreviewFile key={after.url} file={after} />
          </Side>
        </div>
      ) : (
        <div className="mt-2.5 grid grid-cols-1 gap-2">
          {pictures.length === 0 ? null : (
            <div className={cx('grid gap-2', pictures.length > 1 ? 'grid-cols-2' : 'grid-cols-1')}>
              {pictures.map((file, index) => (
                // A preview's files never reorder, and two of them may share an address.
                <PreviewFile key={`${index}:${file.url}`} file={file} />
              ))}
            </div>
          )}
          {others.map((file, index) => (
            <PreviewFile key={`${index}:${file.url}`} file={file} />
          ))}
        </div>
      )}
    </figure>
  );
}

/** Props of {@link Side}. */
interface SideProps {
  /** Which side of the pair it is. */
  label: string;
  /** The file. */
  children: ReactNode;
}

/**
 * Renders one side of a before and after pair that is not two pictures.
 *
 * @param props The component's props.
 * @returns The labeled side.
 */
function Side({ label, children }: SideProps) {
  return (
    <div className="min-w-0">
      <p className="mono mb-1 text-[0.6875rem] tracking-wider text-faint uppercase">{label}</p>
      {children}
    </div>
  );
}

/** Props of {@link Gone}. */
interface GoneProps {
  /** What is no longer there. */
  name: string;
}

/**
 * Renders the quiet placeholder of a file whose address no longer serves it.
 *
 * @param props The component's props.
 * @returns The placeholder.
 */
function Gone({ name }: GoneProps) {
  return (
    <div className="mt-2 flex items-center gap-2 rounded-lg bg-ink-800 px-3 py-2 text-xs text-faint">
      <ImageOff className="size-4 flex-none" aria-hidden="true" />
      <span className="min-w-0 truncate">{name} is no longer available here.</span>
    </div>
  );
}

/** Props of {@link PreviewFile}. */
interface PreviewFileProps {
  /** The file. */
  file: PreviewItem;
}

/**
 * Renders one file of a preview by its kind.
 *
 * @param props The component's props.
 * @returns The file's view.
 */
function PreviewFile({ file }: PreviewFileProps) {
  switch (file.kind) {
    case 'image':
      return <PreviewPicture file={file} />;
    case 'audio':
      return <PreviewSound file={file} />;
    case 'video':
      return <PreviewVideo file={file} />;
    case 'file':
      return (
        <a href={file.url} target="_blank" rel="noopener noreferrer" className="preview-row hover:border-white/25">
          <FileText className="size-4 flex-none text-muted" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate">{file.name}</span>
          <span className="text-xs text-faint">Open</span>
        </a>
      );
  }
}

/**
 * Renders a picture that opens larger in a dialog.
 *
 * @param props The component's props.
 * @returns The picture, or its placeholder once it fails to load.
 */
function PreviewPicture({ file }: PreviewFileProps) {
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const title = useId();
  if (failed) {
    return <Gone name={file.name} />;
  }
  return (
    <>
      <button
        type="button"
        className="preview-frame group relative block w-full"
        style={{ aspectRatio: aspect(file) }}
        aria-label={`Open ${file.name} larger`}
        onClick={() => {
          setOpen(true);
        }}
      >
        <img
          src={file.url}
          alt={file.name}
          loading="lazy"
          decoding="async"
          className="size-full object-contain"
          onError={() => {
            setFailed(true);
          }}
        />
        <span className="preview-badge right-1.5 bottom-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <Maximize2 className="size-3" aria-hidden="true" />
        </span>
      </button>
      <Dialog
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        labelledBy={title}
        wide
      >
        <p id={title} className="mono truncate pr-10 text-xs text-muted">
          {file.name}
          {file.width === undefined || file.height === undefined ? '' : ` · ${file.width} × ${file.height}`}
        </p>
        <img src={file.url} alt={file.name} className="mt-3 max-h-[72dvh] w-full rounded-lg bg-black object-contain" />
      </Dialog>
    </>
  );
}

/**
 * Renders a sound as a named player.
 *
 * @param props The component's props.
 * @returns The player, or its placeholder once the file fails to load.
 */
function PreviewSound({ file }: PreviewFileProps) {
  const [frame, near] = useNearView<HTMLDivElement>();
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <Gone name={file.name} />;
  }
  return (
    <div ref={frame} className="preview-row flex-col items-stretch gap-2">
      <span className="flex items-center gap-2">
        <Music className="size-4 flex-none text-lavender" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">{file.name}</span>
        {file.seconds === undefined ? null : <span className="mono text-xs text-faint">{clock(file.seconds)}</span>}
      </span>
      <audio
        src={near ? file.url : undefined}
        controls
        preload="metadata"
        aria-label={file.name}
        className="h-9 w-full"
        onError={() => {
          setFailed(true);
        }}
      />
    </div>
  );
}

/**
 * Renders a video that plays in place.
 *
 * @param props The component's props.
 * @returns The player, or its placeholder once the file fails to load.
 */
function PreviewVideo({ file }: PreviewFileProps) {
  const [frame, near] = useNearView<HTMLDivElement>();
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <Gone name={file.name} />;
  }
  return (
    <div ref={frame} className="preview-frame relative" style={{ aspectRatio: aspect(file) }}>
      <video
        src={near ? file.url : undefined}
        controls
        playsInline
        preload="metadata"
        aria-label={file.name}
        className="size-full bg-black object-contain"
        onError={() => {
          setFailed(true);
        }}
      />
      {file.seconds === undefined ? null : (
        <span className="preview-badge top-1.5 right-1.5">{clock(file.seconds)}</span>
      )}
    </div>
  );
}

/** Props of {@link ComparePictures}. */
interface ComparePicturesProps {
  /** The picture before the change. */
  before: PreviewItem;
  /** The picture after it. */
  after: PreviewItem;
}

/**
 * Renders two pictures under one slider: left of the handle is before, right of it after.
 *
 * @param props The component's props.
 * @returns The pair, or its placeholder once either picture fails to load.
 */
function ComparePictures({ before, after }: ComparePicturesProps) {
  const [split, setSplit] = useState(50);
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <Gone name={`${before.name} and ${after.name}`} />;
  }
  const fail = (): void => {
    setFailed(true);
  };
  return (
    <div className="preview-frame relative mt-2.5 select-none" style={{ aspectRatio: aspect(after) }}>
      <img src={after.url} alt={`After: ${after.name}`} loading="lazy" decoding="async" className="size-full object-contain" onError={fail} />
      <img
        src={before.url}
        alt={`Before: ${before.name}`}
        loading="lazy"
        decoding="async"
        className="absolute inset-0 size-full object-contain"
        style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
        onError={fail}
      />
      <span className="compare-divider" style={{ left: `${split}%` }} aria-hidden="true" />
      <span className="preview-badge top-1.5 left-1.5" aria-hidden="true">
        Before
      </span>
      <span className="preview-badge top-1.5 right-1.5" aria-hidden="true">
        After
      </span>
      <input
        type="range"
        min={0}
        max={100}
        value={split}
        aria-label="How much of the picture shows as it was before"
        className="compare-range"
        onChange={(event) => {
          setSplit(event.target.valueAsNumber);
        }}
      />
    </div>
  );
}
