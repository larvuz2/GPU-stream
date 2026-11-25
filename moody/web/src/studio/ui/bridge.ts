/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The bridge an `html` card's document talks to the page through: `window.moody`.
 *
 * {@link bridge} runs inside the card's frame, not in the page: `sandbox.ts` writes its source
 * into the card's document, ahead of anything the agent wrote, and calls it with the card's
 * {@link BridgeInit}. So the function stands alone. It reads nothing outside its own body (no
 * import, no constant of this module), since none of that exists where it runs; this file is
 * TypeScript so that the bridge is checked and linted like the rest, and only its compiled text
 * crosses.
 *
 * The frame has no network and an origin of its own (`sandbox.ts`), so the bridge is the card's
 * only way out, and it is narrow. Out go the card's value (`setState`, which the page keeps for
 * the lock-in button, and `submit`, which locks in at once), a request for one of the card's own
 * files as bytes (`load`), the document's height, and a last word when the document is unloaded
 * (`gone`), which only happens when it tried to navigate away: the page then says so in the
 * card's place, rather than leaving the browser's refusal there. In come the bytes asked for and
 * the word that the card was locked. Every message carries the card's id, and the bridge listens
 * to the page alone: a message from any other window is dropped.
 *
 * A value is passed through JSON on its way out, so what reaches the agent is plain data
 * whatever the document held (a function, a DOM node, or a cycle is an error where the card
 * calls, not a surprise later).
 *
 * The bridge also keeps the lit part of every range input's track in step with its value
 * (`--moody-fill`), which is what makes a plain `<input type="range">` in a card look like a
 * slider of the conversation with no script of the card's own.
 * @module
 */

/** What a card's frame starts with. */
export interface BridgeInit {
  /** The card's id in the page, which every message carries. */
  id: string;
  /** The card's value: `null` at first, else what was last set or locked in. */
  state: unknown;
  /** Whether the card is locked in. */
  locked: boolean;
  /** The card's files by name, each an address an element can load. */
  media: Record<string, string>;
}

/** What the card's document finds as `window.moody`. */
export interface MoodyBridge {
  /** The card's value: `null` at first, else what was last set or locked in. */
  state: unknown;
  /** Whether the card is locked in: show the value and change nothing. */
  readonly locked: boolean;
  /** The card's files by name, each an address for an `img`, `audio`, or `video` element. */
  readonly media: Readonly<Record<string, string>>;
  /** Reports the card's value, which the lock-in button sends. */
  setState: (value: unknown) => void;
  /** Locks the card in with a value at once. */
  submit: (value: unknown) => void;
  /** Reads one of the card's files as bytes, for decoding sound or reading pixels. */
  load: (name: string) => Promise<ArrayBuffer>;
}

/**
 * Sets up `window.moody` in a card's frame. See the module's docblock for why it stands alone.
 *
 * @param init What the frame starts with.
 */
export function bridge(init: BridgeInit): void {
  // The page is two windows up: the frame's parent is the shell that confines it.
  const page = window.parent.parent;
  const waiting = new Map<number, { resolve: (bytes: ArrayBuffer) => void; reject: (reason: Error) => void }>();
  let requests = 0;
  let locked = init.locked;

  const post = (message: Record<string, unknown>): void => {
    page.postMessage({ moodyCard: init.id, ...message }, '*');
  };
  const plain = (value: unknown): unknown => (value === undefined ? null : JSON.parse(JSON.stringify(value)));

  const api: MoodyBridge = {
    state: init.state,
    get locked() {
      return locked;
    },
    media: Object.freeze({ ...init.media }),
    setState(value) {
      const sent = plain(value);
      api.state = sent;
      post({ type: 'state', value: sent });
    },
    submit(value) {
      const sent = plain(value);
      api.state = sent;
      post({ type: 'submit', value: sent });
    },
    load(name) {
      return new Promise((resolve, reject) => {
        requests += 1;
        waiting.set(requests, { resolve, reject });
        post({ type: 'load', name, request: requests });
      });
    },
  };
  Object.defineProperty(window, 'moody', { value: api, enumerable: true });

  window.addEventListener('message', (event: MessageEvent<unknown>) => {
    const data = event.data;
    if (event.source !== page || typeof data !== 'object' || data === null) {
      return;
    }
    const message: Record<string, unknown> = { ...data };
    if (message.moodyCard !== init.id) {
      return;
    }
    if (message.type === 'loaded' && typeof message.request === 'number') {
      const asked = waiting.get(message.request);
      waiting.delete(message.request);
      if (message.bytes instanceof ArrayBuffer) {
        asked?.resolve(message.bytes);
      } else {
        asked?.reject(new Error(typeof message.error === 'string' ? message.error : 'The file could not be read.'));
      }
    } else if (message.type === 'lock') {
      locked = true;
      api.state = message.value;
      document.documentElement.dataset.locked = 'true';
      window.dispatchEvent(new CustomEvent('moodylock', { detail: message.value }));
    }
  });

  const lit = (target: EventTarget | null): void => {
    if (target instanceof HTMLInputElement && target.type === 'range') {
      const low = Number(target.min === '' ? 0 : target.min);
      const high = Number(target.max === '' ? 100 : target.max);
      const share = high > low ? ((Number(target.value) - low) / (high - low)) * 100 : 0;
      target.style.setProperty('--moody-fill', `${share}%`);
    }
  };
  document.addEventListener(
    'input',
    (event) => {
      lit(event.target);
    },
    true,
  );

  let reported = 0;
  const measure = (): void => {
    document.querySelectorAll('input[type="range"]').forEach(lit);
    const height = Math.ceil(document.documentElement.getBoundingClientRect().height);
    if (height !== reported) {
      reported = height;
      post({ type: 'height', height });
    }
  };
  new ResizeObserver(measure).observe(document.documentElement);
  window.addEventListener('load', measure);
  // Said as the navigation starts: once the document is unloaded, its frame holds another window,
  // which the page does not take messages from.
  window.addEventListener('beforeunload', () => {
    post({ type: 'gone' });
  });
  document.addEventListener('DOMContentLoaded', () => {
    if (locked) {
      document.documentElement.dataset.locked = 'true';
    }
    measure();
    post({ type: 'ready' });
  });
}
