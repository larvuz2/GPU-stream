/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The frame an `html` card runs in: the two documents it is made of, and the policy that confines it.
 *
 * A card's document is code the agent wrote, and what an agent writes can be steered by what it
 * read, so the document is given nothing to lose and no way to send anything anywhere:
 *
 * - **No origin.** The frame is sandboxed with scripts allowed and nothing else, so it has an
 *   origin of its own: it cannot read the page, its cookies, or its storage, open a window, or
 *   navigate the tab.
 * - **No network.** A content security policy allows inline script and style, and pictures and
 *   sound from `data:`, `blob:`, and the exact addresses of the card's own files. Nothing else
 *   loads: no fetch, no socket, no beacon, no remote image, script, style, font, or frame.
 * - **No way out by leaving.** A sandboxed frame may still navigate itself, and a navigation
 *   carries whatever its address says. So the card's document is not the frame the page embeds:
 *   it is a frame inside that one. The outer frame is a shell whose policy allows no frame to
 *   load anything (`frame-src 'none'`), and a navigation of the inner frame is checked against
 *   the policy of the document that embeds it. The card's document is the shell's `srcdoc`,
 *   which that policy does not stop, and anywhere it tries to go is refused before a request is
 *   made. Both documents inherit the policy, so the card can embed nothing either.
 *
 * Where the shell comes from decides whether a card runs at all. A document a page writes into
 * a frame (`srcdoc`) also runs under the page's own policy, and a site that keeps its pages to
 * scripts from its own files, as the deployed site does (`netlify.toml`), thereby stops the
 * card's script; allowing inline script on the page to let cards through would undo that
 * protection for the page itself. So with a control plane connected, the shell is a document it
 * serves (`cardFrameUrl`, the control plane's `genui.CARD_FRAME`): it arrives with headers of its
 * own, answers to those and not to the page, and its policy is the one above. It holds nothing.
 * The page hands it the card's document by a message once it says it is ready, and it takes one
 * document, from the window that frames it alone. With no control plane (the demo in
 * development), the page writes the shell itself ({@link shellDocument}), which runs wherever
 * the page has no policy to pass down.
 *
 * What the card may do instead goes through the bridge (`bridge.ts`), whose source is written into
 * the document ahead of the agent's own, with the card's value and files. The page reaches the
 * card's window as the shell's only child frame, and takes messages from that window alone.
 *
 * The frame is made to look like the conversation: the site's design tokens are read from the
 * page as it is styled now and given to the document as `--moody-*` variables
 * ({@link THEME}), over a small sheet that sets the page's type and gives buttons, fields, and
 * sliders the conversation's look, and the page's own font file is handed in as a `data:`
 * address, since the frame could not fetch it. The document's background is left clear, so the
 * card's own surface shows through and the frame has no edge.
 * @module
 */
import { bridge, type BridgeInit } from './bridge';
import type { UiMedia } from './tree';

/** The variables a card's document is given, each from one of the site's tokens (`styles.css`). */
export const THEME: Readonly<Record<string, string>> = {
  '--moody-bg': '--color-ink-950',
  '--moody-surface': '--color-ink-800',
  '--moody-raised': '--color-ink-700',
  '--moody-line': '--color-line',
  '--moody-line-strong': '--color-line-strong',
  '--moody-fg': '--color-fg',
  '--moody-soft': '--color-soft',
  '--moody-muted': '--color-muted',
  '--moody-faint': '--color-faint',
  '--moody-lime': '--color-lime',
  '--moody-lavender': '--color-lavender',
  '--moody-ok': '--color-ok',
  '--moody-warn': '--color-warn',
  '--moody-bad': '--color-bad',
  '--moody-info': '--color-info',
  '--moody-font': '--font-sans',
  '--moody-mono': '--font-mono',
};

/**
 * The clear band around a card's document, in pixels: room for a focus ring on a control that
 * sits at the document's edge, which the frame would otherwise cut off. The page widens the frame
 * by as much on every side (`HtmlCard.tsx`), so the document still lines up with the card.
 */
export const FRAME_GUTTER = 4;

/** The sheet under a card's own styles: the conversation's type, and its look for native controls. */
const BASE_STYLE = `
:root{color-scheme:dark}
*,*::before,*::after{box-sizing:border-box}
html{background:transparent;color:var(--moody-fg);font-family:var(--moody-font);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
body{margin:0;padding:${FRAME_GUTTER}px}
canvas,img,svg,video{max-width:100%}
button{height:2.1rem;padding:0 .8rem;border:1px solid var(--moody-line-strong);border-radius:.5rem;background:var(--moody-raised);color:var(--moody-fg);font:inherit;font-weight:600;cursor:pointer}
button:hover{border-color:var(--moody-muted)}
button:disabled{opacity:.5;cursor:default}
input:not([type]),input[type=text],input[type=number],select,textarea{height:2.1rem;padding:0 .6rem;border:1px solid var(--moody-line-strong);border-radius:.5rem;background:var(--moody-surface);color:var(--moody-fg);font:inherit}
textarea{height:auto;padding:.5rem .6rem}
label{color:var(--moody-soft);font-size:.8125rem}
input[type=checkbox],input[type=radio]{accent-color:var(--moody-lime)}
input[type=range]{width:100%;height:1.25rem;margin:0;background:transparent;cursor:pointer;-webkit-appearance:none;appearance:none}
input[type=range]::-webkit-slider-runnable-track{height:.25rem;background:linear-gradient(to right,var(--moody-lime) var(--moody-fill,0%),var(--moody-line-strong) var(--moody-fill,0%))}
input[type=range]::-moz-range-track{height:.25rem;background:linear-gradient(to right,var(--moody-lime) var(--moody-fill,0%),var(--moody-line-strong) var(--moody-fill,0%))}
input[type=range]::-webkit-slider-thumb{width:.9rem;height:.9rem;margin-top:-.325rem;border:2px solid var(--moody-bg);border-radius:.15rem;background:var(--moody-fg);box-shadow:0 0 0 1px var(--moody-line-strong);-webkit-appearance:none;appearance:none}
input[type=range]::-moz-range-thumb{width:.65rem;height:.65rem;border:2px solid var(--moody-bg);border-radius:.15rem;background:var(--moody-fg);box-shadow:0 0 0 1px var(--moody-line-strong)}
:focus-visible{outline:2px solid var(--moody-lime);outline-offset:2px}
::selection{background:var(--moody-lime);color:var(--moody-bg)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
`;

/** The shell's own sheet: its one frame fills it. */
const SHELL_STYLE = ':root{color-scheme:dark}html,body{height:100%;margin:0;background:transparent}iframe{display:block;width:100%;height:100%;border:0}';

/** What a font file handed to the frame is: the family it is, and its `data:` address. */
export interface FrameFont {
  family: string;
  address: string;
}

/**
 * Writes a string as the value of a double-quoted HTML attribute.
 *
 * @param value The string.
 * @returns The string with the two characters that would end or alter the attribute escaped.
 */
function attribute(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;');
}

/**
 * Writes one of a card's files as a source the policy allows.
 *
 * A policy's source is an address without its query, and `;` and `,` would end it, so the query
 * is dropped (a path that ends without a slash matches that one file, whatever its query) and
 * those two are encoded.
 *
 * @param url The file's address.
 * @returns The source, or `null` for an address that is not `http` or `https`.
 */
function source(url: string): string | null {
  try {
    const parsed = new URL(url, window.location.href);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
      return null;
    }
    return `${parsed.origin}${parsed.pathname}`.replaceAll(';', '%3B').replaceAll(',', '%2C');
  } catch {
    return null;
  }
}

/**
 * Writes the policy a card's frame runs under.
 *
 * @param media The card's files, the only addresses the frame may load from.
 * @returns The content security policy.
 */
export function policy(media: readonly UiMedia[]): string {
  const files = [...new Set(media.map((file) => source(file.url)).filter((one) => one !== null))].join(' ');
  return [
    "default-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    `img-src data: blob: ${files}`.trim(),
    `media-src data: blob: ${files}`.trim(),
    'font-src data:',
    "frame-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
  ].join('; ');
}

/**
 * Reads the site's tokens as the variables a card's document is given.
 *
 * @returns The declarations of `:root`, one per variable of {@link THEME} the page defines.
 */
export function themeDeclarations(): string {
  const styles = window.getComputedStyle(document.documentElement);
  return Object.entries(THEME)
    .map(([name, token]) => [name, styles.getPropertyValue(token).trim()])
    .filter(([, value]) => value !== '')
    .map(([name, value]) => `${name}:${value}`)
    .join(';');
}

/**
 * Gives each of a card's files the address the frame loads it from.
 *
 * @param media The card's files.
 * @returns The addresses by name, each absolute, since the frame has no address of its own to resolve against.
 */
export function mediaAddresses(media: readonly UiMedia[]): Record<string, string> {
  return Object.fromEntries(
    media.map((file): [string, string] => {
      try {
        return [file.name, new URL(file.url, window.location.href).href];
      } catch {
        return [file.name, file.url];
      }
    }),
  );
}

/**
 * Writes the document a card's code runs in.
 *
 * @param html The document the agent wrote, whole or a fragment.
 * @param init What the bridge starts with.
 * @param csp The frame's policy.
 * @param theme The declarations of the theme's variables.
 * @param font The page's font, where it could be read.
 * @returns The document: the policy, the theme, and the bridge, then the agent's own.
 */
export function cardDocument(html: string, init: BridgeInit, csp: string, theme: string, font: FrameFont | null): string {
  const face =
    font === null
      ? ''
      : `@font-face{font-family:${JSON.stringify(font.family)};font-style:normal;font-weight:100 900;src:url("${font.address}")}`;
  // The card's value sits in a script, where `<` could end it early: written as an escape, it cannot.
  const start = JSON.stringify(init).replaceAll('<', '\\u003c');
  return [
    '<!doctype html><html lang="en"><head><meta charset="utf-8">',
    `<meta http-equiv="Content-Security-Policy" content="${attribute(csp)}">`,
    '<meta name="color-scheme" content="dark">',
    `<style>${face}:root{${theme}}${BASE_STYLE}</style>`,
    `<script>(${bridge.toString()})(${start});</script>`,
    '</head><body>',
    html,
    '</body></html>',
  ].join('');
}

/**
 * Writes the shell that confines a card's document: one frame, under the policy that lets it go nowhere.
 *
 * @param card The card's document.
 * @param csp The frame's policy.
 * @param title What the card is, for the frame's accessible name.
 * @returns The shell's document.
 */
export function shellDocument(card: string, csp: string, title: string): string {
  return [
    '<!doctype html><html lang="en"><head><meta charset="utf-8">',
    `<meta http-equiv="Content-Security-Policy" content="${attribute(csp)}">`,
    '<meta name="color-scheme" content="dark">',
    `<style>${SHELL_STYLE}</style>`,
    '</head><body>',
    `<iframe sandbox="allow-scripts" title="${attribute(title)}" srcdoc="${attribute(card)}"></iframe>`,
    '</body></html>',
  ].join('');
}

/** The page's font as the frame takes it, read once. */
let pageFont: Promise<FrameFont | null> | null = null;

/**
 * Reads the page's own font file as a `data:` address, for a frame that cannot fetch it.
 *
 * The file is the face of the page's first font family that covers basic Latin, found among the
 * page's style sheets, which the browser already holds, so reading it costs no download.
 *
 * @returns The font, or `null` where the page declares no such face or it cannot be read.
 */
export function readPageFont(): Promise<FrameFont | null> {
  pageFont ??= (async (): Promise<FrameFont | null> => {
    const wanted = window
      .getComputedStyle(document.documentElement)
      .getPropertyValue('--font-sans')
      .split(',')[0]
      ?.trim()
      .replace(/^["']|["']$/g, '');
    if (wanted === undefined || wanted === '') {
      return null;
    }
    for (const sheet of document.styleSheets) {
      let rules: CSSRuleList;
      try {
        rules = sheet.cssRules;
      } catch {
        // A sheet from another origin keeps its rules to itself.
        continue;
      }
      for (const rule of rules) {
        if (!(rule instanceof CSSFontFaceRule)) {
          continue;
        }
        const family = rule.style.getPropertyValue('font-family').trim().replace(/^["']|["']$/g, '');
        const covers = rule.style.getPropertyValue('unicode-range');
        const address = /url\(["']?([^"')]+)["']?\)/.exec(rule.style.getPropertyValue('src'))?.[1];
        if (family !== wanted || address === undefined || !(covers === '' || /U\+0{1,4}-0{0,2}FF/i.test(covers))) {
          continue;
        }
        try {
          const file = await (await fetch(new URL(address, sheet.href ?? window.location.href))).blob();
          const read = new FileReader();
          const loaded = new Promise<string | null>((resolve) => {
            read.onload = () => {
              resolve(typeof read.result === 'string' ? read.result : null);
            };
            read.onerror = () => {
              resolve(null);
            };
          });
          read.readAsDataURL(file);
          const data = await loaded;
          return data === null ? null : { family, address: data };
        } catch {
          return null;
        }
      }
    }
    return null;
  })();
  return pageFont;
}
