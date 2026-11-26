/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's `upload` input: a file the person drops or picks, which goes into the project's
 * library, and which the card then shows.
 *
 * The card cannot store a file itself; the page showing it can (`UiCardProps.onUpload`, which
 * the card's components reach as `card.upload`). So the input has four states, each said in
 * words:
 *
 * - **Empty**: a place to drop a file, with a button that opens the device's picker, which is
 *   how the keyboard and a screen reader give one. A file of a kind the input does not take is
 *   refused here, before anything is sent, by its type or, where the browser tells none, by the
 *   ending of its name (the catalog's `media_kinds`).
 * - **Sending**: the file's name and size beside a bar that moves without a measure, since the
 *   page is told when the file is in, not how far along it is.
 * - **Refused**: what the page said went wrong, in its own words, with the place to drop
 *   another.
 * - **In the library**: the file itself (a player for a sound, the picture, the video) with its
 *   name and the tag the library gave it, and a button to give another in its place.
 *
 * The input's value is the entry the file became, `{tag, name, kind}`, which is what the agent
 * reads; the address the page plays the file from is kept here, for as long as the card is on
 * the page. A card shown on a page that cannot take files says so in the input's place.
 *
 * While a file is on its way the input holds the card open (`Card.hold`), so an answer is never
 * locked in a moment before the file it was meant to carry. An input that left the card
 * meanwhile (its condition stopped holding) takes no value from a file that arrives after.
 * @module
 */
import { useEffect, useRef, useState, type DragEvent } from 'react';
import { FileIcon, Upload as UploadIcon } from 'lucide-react';
import { CATALOG } from '../catalog';
import { useCard } from '../context';
import { text } from '../tree';
import { isUploadedFile } from '../values';
import { useInput, type ViewProps } from '../view';
import { Sound } from './Audio';

/** What each kind of file an input takes is called, where the input asks for one. */
const WANTS: Readonly<Record<string, string>> = {
  any: 'a file',
  audio: 'a sound',
  image: 'a picture',
  video: 'a video',
};

/**
 * Whether a file is of the kind an input takes.
 *
 * A vendor's own format is of no kind, whatever family its type is registered under: a browser
 * reports a DXF drawing as `image/vnd.dxf`, and it is not a picture. The library tells an upload
 * the same way (`media_kind` in the control plane's `service.py`).
 *
 * @param accept The kind: `audio`, `image`, `video`, or `any`.
 * @param file The file.
 * @returns `true` by the file's type, or by its name's ending where the browser tells no type.
 */
function takes(accept: string, file: File): boolean {
  if (accept === 'any') {
    return true;
  }
  if (file.type !== '') {
    return file.type.startsWith(`${accept}/`) && !file.type.startsWith(`${accept}/vnd.`);
  }
  return (CATALOG.media_kinds[accept] ?? []).some((ending) => file.name.toLowerCase().endsWith(ending));
}

/**
 * Writes a file's size as a person reads one.
 *
 * @param bytes The size.
 * @returns The size in the largest unit that keeps it above one, such as `3.2 MB`.
 */
function sizeOf(bytes: number): string {
  const units = ['bytes', 'KB', 'MB', 'GB'];
  const unit = Math.min(units.length - 1, bytes > 0 ? Math.floor(Math.log(bytes) / Math.log(1000)) : 0);
  const amount = bytes / 1000 ** unit;
  return `${unit === 0 ? String(bytes) : amount.toFixed(amount < 10 ? 1 : 0)} ${units[unit] ?? 'bytes'}`;
}

/** What the input is doing, besides holding its value. */
type Phase = { name: 'idle' } | { name: 'sending'; file: string; size: number } | { name: 'refused'; why: string };

/**
 * Renders an input that takes a file into the project's library.
 *
 * @param props The component's props.
 * @returns The input in the state it is in.
 */
export function Upload({ node }: ViewProps) {
  const card = useCard();
  const input = useInput(node);
  const picker = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>({ name: 'idle' });
  const [over, setOver] = useState(false);
  // Where the file in the library is played from, by its tag: known for a file given on this page.
  const [shown, setShown] = useState<{ tag: string; url: string } | null>(null);
  const given = text(node, 'accept') ?? 'any';
  const accept = given in WANTS ? given : 'any';
  const wanted = WANTS[accept] ?? 'a file';
  const value = isUploadedFile(input.value) ? input.value : null;
  const upload = card.upload;
  const hold = card.hold;
  const key = input.domId;
  // Whether the input is still on the card: one that left while its file was on its way takes no value.
  const shownNow = useRef(true);
  useEffect(() => {
    shownNow.current = true;
    return () => {
      shownNow.current = false;
      hold(key, null);
    };
  }, [hold, key]);

  /**
   * Sends a file to the library and takes the entry it became as the input's value.
   *
   * @param file The file the person gave.
   */
  async function take(file: File): Promise<void> {
    if (upload === null || input.frozen) {
      return;
    }
    if (!takes(accept, file)) {
      setPhase({ name: 'refused', why: `This takes ${wanted}, and ${file.name} is not one.` });
      return;
    }
    setPhase({ name: 'sending', file: file.name, size: file.size });
    hold(key, `Still adding ${file.name}`);
    try {
      const entry = await upload(file, { section: text(node, 'section') });
      if (shownNow.current) {
        setShown({ tag: entry.tag, url: entry.url });
        input.set({ tag: entry.tag, name: entry.name, kind: entry.kind });
        setPhase({ name: 'idle' });
      }
    } catch (failure) {
      const why = failure instanceof Error && failure.message !== '' ? failure.message : `${file.name} could not be added.`;
      setPhase({ name: 'refused', why });
    } finally {
      hold(key, null);
    }
  }

  /**
   * Takes the file dropped on the input.
   *
   * @param event The drop.
   */
  function onDrop(event: DragEvent): void {
    event.preventDefault();
    setOver(false);
    const file = event.dataTransfer.files[0];
    if (file !== undefined) {
      void take(file);
    }
  }

  const heading = input.labeled ? <p className="ui-label">{input.label}</p> : null;
  if (upload === null && value === null) {
    return (
      <div className="ui-input" role="group" aria-label={input.label}>
        {heading}
        <p className="ui-missing">This card cannot take a file here.</p>
      </div>
    );
  }
  const url = value !== null && shown?.tag === value.tag ? shown.url : null;
  const sending = phase.name === 'sending';
  return (
    <div className="ui-input" role="group" aria-label={input.label}>
      {heading}
      <input
        ref={picker}
        type="file"
        hidden
        accept={accept === 'any' ? undefined : [`${accept}/*`, ...(CATALOG.media_kinds[accept] ?? [])].join(',')}
        onChange={(event) => {
          const file = event.target.files?.[0];
          // The same file can be picked again after a refusal.
          event.target.value = '';
          if (file !== undefined) {
            void take(file);
          }
        }}
      />
      {value === null ? null : (
        <div className="ui-upload-file">
          {url !== null && value.kind === 'audio' ? (
            <Sound url={url} name={value.name} />
          ) : url !== null && value.kind === 'image' ? (
            <img src={url} alt={value.name} className="ui-upload-picture" />
          ) : url !== null && value.kind === 'video' ? (
            <video src={url} controls preload="metadata" aria-label={value.name} className="ui-upload-picture" />
          ) : null}
          <p className="ui-upload-line">
            <FileIcon className="size-3.5 flex-none" aria-hidden="true" />
            {/* A sound's player already carries its name. */}
            {url !== null && value.kind === 'audio' ? null : <span className="ui-upload-name">{value.name}</span>}
            <span className="ui-upload-tag">In the library as {value.tag}</span>
          </p>
        </div>
      )}
      {sending ? (
        <div className="ui-drop" data-state="sending">
          <p className="ui-upload-line" role="status">
            <span className="spinner size-3.5 flex-none" aria-hidden="true" />
            <span className="ui-upload-name">Adding {phase.file}</span>
            <span className="ui-upload-tag">{sizeOf(phase.size)}</span>
          </p>
          <div className="ui-progress" role="progressbar" aria-label={`Adding ${phase.file} to the library`} />
        </div>
      ) : input.frozen ? (
        value === null ? (
          <p className="ui-missing">No file was given.</p>
        ) : null
      ) : (
        <div
          className="ui-drop"
          data-over={over ? 'true' : undefined}
          data-filled={value === null ? undefined : 'true'}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => {
            setOver(false);
          }}
          onDrop={onDrop}
        >
          {value === null ? (
            <>
              <UploadIcon className="size-5 flex-none" aria-hidden="true" />
              <span>Drop {wanted} here, or</span>
            </>
          ) : null}
          <button
            type="button"
            className="ui-drop-button"
            // The name carries the words in view and says what the file is for.
            aria-label={`${value === null ? `Choose ${wanted}` : 'Choose another'} for ${input.label}`}
            onClick={() => {
              picker.current?.click();
            }}
          >
            {value === null ? `Choose ${wanted}` : 'Choose another'}
          </button>
        </div>
      )}
      {phase.name === 'refused' ? (
        <p className="ui-upload-refused" role="alert">
          {phase.why}
        </p>
      ) : null}
    </div>
  );
}
