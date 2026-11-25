/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * An `html` card: a document the agent wrote, for what the catalog cannot express (a simulation,
 * sound made in the browser, a canvas of its own), run where it can reach nothing.
 *
 * The document runs in a sandboxed frame inside a sandboxed shell, with no origin, no network,
 * and no way to navigate out (`sandbox.ts` says how and why). This component is the page's end of
 * the bridge (`bridge.ts`):
 *
 * - It takes messages only from the card's own window, the shell's one child frame, and only
 *   those that carry this card's id.
 * - `recommend` is the value the document opened on, the agent's recommendation. It is the
 *   card's value until the person changes something, so the card can be locked in untouched, and
 *   it is what every later value is held against: the foot says the card stands as recommended
 *   or what was changed, and offers the way back. Going back builds the frame anew, since the
 *   document's own starting state is the recommendation and the page cannot reach into it to set
 *   one; the same document then opens as it first did.
 * - `state` is kept as the card's value, which the lock-in button sends; `submit` locks in at
 *   once, but only on a card that has a lock-in button, while it can be answered, and while the
 *   person is in it (the frame holds the focus), so a document cannot answer for someone who
 *   never touched it.
 * - `load` is answered with one of the card's own files as bytes, fetched here, since the frame
 *   cannot fetch. A name the card does not carry is refused.
 * - `height` sizes the frame to the document, within the catalog's limits.
 * - `gone` means the document was unloaded, which it only is by trying to navigate away. The
 *   shell refused the navigation, so nothing left, but the document is no more: the card says so
 *   in the frame's place and can no longer be locked in.
 *
 * The frame is built once per card. The event's data may arrive again with fresh signed
 * addresses, and rebuilding the document for that would throw away what the person did in it, so
 * the document keeps the addresses it started with while `load` reads the current ones. A card
 * locked while it is open is told so through the bridge and made inert, rather than rebuilt.
 * @module
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { isNumber, isRecord, isString } from '../../lib/narrow';
import { departuresOfValue, summarizeValue } from './answer';
import { limit } from './catalog';
import { LockBar } from './LockBar';
import { cardDocument, mediaAddresses, policy, readPageFont, shellDocument, themeDeclarations, type FrameFont } from './sandbox';
import type { UiCardProps } from './UiCard';
import { clamp, sameValue } from './values';

/** How long the frame waits for the page's font before it is built without it. */
const FONT_WAIT_MS = 1200;

/**
 * Finds a card's window: the one frame inside its shell.
 *
 * @param shell The shell's frame element.
 * @returns The card's window, or `null` before the shell has loaded it.
 */
function cardWindow(shell: HTMLIFrameElement | null): Window | null {
  const outer = shell?.contentWindow;
  try {
    // A window from another origin gives its frames by number, and nothing where there is none.
    return outer !== null && outer !== undefined && outer.length > 0 ? (outer[0] ?? null) : null;
  } catch {
    return null;
  }
}

/**
 * Renders a card that is a document of the agent's own.
 *
 * @param props The component's props.
 * @returns The frame and the lock-in bar.
 */
export function HtmlCard({ ui, locked, live, onSubmit }: UiCardProps) {
  const frame = useRef<HTMLIFrameElement>(null);
  const least = limit('height_min', 120);
  const most = limit('height_max', 900);
  const [id] = useState(() => crypto.randomUUID());
  const [first] = useState(() => ({ media: ui.media, locked }));
  const [font, setFont] = useState<FrameFont | null | undefined>(undefined);
  const [height, setHeight] = useState(() => clamp(ui.height ?? limit('height_default', 360), least, most));
  const [value, setValue] = useState<unknown>(first.locked?.value ?? null);
  const [recommended, setRecommended] = useState<{ value: unknown } | null>(null);
  const [reported, setReported] = useState(false);
  const [gone, setGone] = useState(false);
  // Which building of the frame this is: going back to the recommendation builds it anew.
  const [run, setRun] = useState(0);
  const html = ui.html ?? '';

  useEffect(() => {
    let waiting = true;
    const give = (found: FrameFont | null): void => {
      if (waiting) {
        waiting = false;
        setFont(found);
      }
    };
    const timer = window.setTimeout(() => {
      give(null);
    }, FONT_WAIT_MS);
    void readPageFont().then(give);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  const srcdoc = useMemo(() => {
    if (font === undefined) {
      return null;
    }
    const csp = policy(first.media);
    const init = {
      id,
      state: first.locked?.value ?? null,
      locked: first.locked !== null,
      media: mediaAddresses(first.media),
    };
    return shellDocument(cardDocument(html, init, csp, themeDeclarations(), font), csp, ui.title);
  }, [html, id, first, font, ui.title]);

  const files = useRef(ui.media);
  const answerable = useRef({ live: live && ui.submit !== null, open: locked === null, onSubmit });
  useEffect(() => {
    files.current = ui.media;
    answerable.current = { live: live && ui.submit !== null, open: locked === null, onSubmit };
  });

  useEffect(() => {
    /**
     * Answers the card's request for one of its files.
     *
     * @param name The file's name in the card.
     * @param request The request's number, which the answer carries.
     */
    async function load(name: string, request: unknown): Promise<void> {
      const file = files.current.find((one) => one.name === name);
      const card = cardWindow(frame.current);
      try {
        if (file === undefined) {
          throw new Error(`This card carries no file named ${name}.`);
        }
        const response = await fetch(file.url);
        if (!response.ok) {
          throw new Error(`${name} could not be read.`);
        }
        const bytes = await response.arrayBuffer();
        card?.postMessage({ moodyCard: id, type: 'loaded', request, bytes }, '*', [bytes]);
      } catch (failure) {
        const error = failure instanceof Error ? failure.message : `${name} could not be read.`;
        card?.postMessage({ moodyCard: id, type: 'loaded', request, error }, '*');
      }
    }

    /**
     * Takes a message from the card's window.
     *
     * @param event The message.
     */
    function onMessage(event: MessageEvent<unknown>): void {
      const message = event.data;
      if (!isRecord(message) || message.moodyCard !== id || event.source !== cardWindow(frame.current)) {
        return;
      }
      if (message.type === 'height' && isNumber(message.height)) {
        // The document may be shorter than the least a card may ask to start at, down to a line of text.
        setHeight(clamp(message.height, limit('frame_min', 40), most));
      } else if (message.type === 'recommend') {
        const opened: unknown = message.value;
        setRecommended({ value: opened });
        // Until the person changes something, the recommendation is the card's value; a card
        // shown locked keeps the value it was locked in with.
        setValue((current: unknown) => current ?? opened);
      } else if (message.type === 'state') {
        setValue(message.value);
        setReported(true);
      } else if (message.type === 'submit') {
        setValue(message.value);
        setReported(true);
        const { live: canAnswer, open, onSubmit: submit } = answerable.current;
        if (canAnswer && open && document.activeElement === frame.current) {
          submit(message.value);
        }
      } else if (message.type === 'load' && isString(message.name)) {
        void load(message.name, message.request);
      } else if (message.type === 'gone') {
        setGone(true);
      }
    }

    window.addEventListener('message', onMessage);
    return () => {
      window.removeEventListener('message', onMessage);
    };
  }, [id, most]);

  // A card locked while it is open is told so; one that started locked was built that way.
  const lockedValue = locked?.value;
  const nowLocked = locked !== null && first.locked === null;
  useEffect(() => {
    if (nowLocked) {
      cardWindow(frame.current)?.postMessage({ moodyCard: id, type: 'lock', value: lockedValue }, '*');
    }
  }, [nowLocked, lockedValue, id]);

  // A locked card stands by what was locked in, whatever the document reported since.
  const held = locked === null ? value : locked.value;
  const kept = recommended !== null && sameValue(held, recommended.value);
  return (
    <>
      <div className="ui-body">
        {gone ? (
          <p className="ui-missing" role="status">
            This card stopped: its document tried to leave its frame, which a card may not do. Nothing was sent.
          </p>
        ) : srcdoc === null ? (
          <div className="ui-html-frame" style={{ height }} role="status" aria-label={`Opening ${ui.title}`} />
        ) : (
          <iframe
            key={run}
            ref={frame}
            title={ui.title}
            className="ui-html-frame"
            sandbox="allow-scripts"
            srcDoc={srcdoc}
            style={{ height }}
            inert={locked !== null}
          />
        )}
      </div>
      <LockBar
        label={ui.submit}
        locked={locked !== null}
        live={live}
        blocked={gone ? 'This card stopped, so there is nothing to lock in.' : reported || value !== null ? null : 'Change something in the card first.'}
        summary={locked === null ? [] : summarizeValue(locked.value)}
        advice={recommended === null ? null : { kept, changed: departuresOfValue(held, recommended.value) }}
        onReturn={() => {
          setValue(null);
          setReported(false);
          setRecommended(null);
          setRun((count) => count + 1);
        }}
        onLock={() => {
          onSubmit(value);
        }}
      />
    </>
  );
}
