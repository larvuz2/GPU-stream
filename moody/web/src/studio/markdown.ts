/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The small subset of Markdown the agent writes in, parsed into plain data.
 *
 * The agent's text is model output, so it is never handed to the browser as HTML: it is parsed
 * here into blocks and inline runs, and `Prose.tsx` builds React elements from them, which escape
 * every character of text. Anything outside the subset reads as the characters it is.
 *
 * Blocks: paragraphs (a single line break inside one is kept), headings (`#` to `###`, deeper ones
 * read as the third level), bulleted and numbered lists, fenced code, quotes, and rules. Inline:
 * `code`, **strong**, *emphasis* (or `_emphasis_` between non-word characters), links whose
 * address is `http` or `https` (any other scheme is left as text), bare `https://` addresses, and
 * library tags (`@mara`), which the conversation turns into references to the library.
 *
 * The parser scans with `indexOf` rather than backtracking expressions, so a hostile or merely
 * long reply costs time in proportion to its length times its nesting, never exponentially.
 * @module
 */

/** A run of inline content. */
export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'em'; children: Inline[] }
  | { kind: 'link'; href: string; children: Inline[] }
  | { kind: 'tag'; tag: string };

/** A block of the text. */
export type Block =
  | { kind: 'paragraph'; lines: Inline[][] }
  | { kind: 'heading'; level: 1 | 2 | 3; content: Inline[] }
  | { kind: 'list'; ordered: boolean; start: number; items: Inline[][] }
  | { kind: 'code'; text: string }
  | { kind: 'quote'; lines: Inline[][] }
  | { kind: 'rule' };

const FENCE = /^\s*```/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d{1,9})[.)]\s+(.*)$/;
const QUOTE = /^\s*>\s?(.*)$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const CONTINUATION = /^\s{2,}\S/;

/**
 * Parses text into blocks.
 *
 * @param source The text.
 * @returns Its blocks, in order.
 */
export function parseMarkdown(source: string): Block[] {
  const lines = source.replaceAll('\r\n', '\n').split('\n');
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flush = (): void => {
    if (paragraph.length > 0) {
      blocks.push({ kind: 'paragraph', lines: paragraph.map(parseInline) });
      paragraph = [];
    }
  };

  let index = 0;
  while (index < lines.length) {
    const line = lines[index] ?? '';
    if (FENCE.test(line)) {
      flush();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !FENCE.test(lines[index] ?? '')) {
        body.push(lines[index] ?? '');
        index += 1;
      }
      blocks.push({ kind: 'code', text: body.join('\n') });
      index += 1;
      continue;
    }
    if (line.trim() === '') {
      flush();
      index += 1;
      continue;
    }
    if (RULE.test(line)) {
      flush();
      blocks.push({ kind: 'rule' });
      index += 1;
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading !== null) {
      flush();
      const depth = heading[1]?.length ?? 1;
      blocks.push({
        kind: 'heading',
        level: depth === 1 ? 1 : depth === 2 ? 2 : 3,
        content: parseInline(heading[2] ?? ''),
      });
      index += 1;
      continue;
    }
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);
    if (bullet !== null || numbered !== null) {
      flush();
      const ordered = bullet === null;
      const items: string[] = [];
      while (index < lines.length) {
        const current = lines[index] ?? '';
        const item = ordered ? NUMBERED.exec(current) : BULLET.exec(current);
        if (item !== null) {
          items.push((ordered ? item[2] : item[1]) ?? '');
        } else if (CONTINUATION.test(current) && items.length > 0) {
          items.push(`${items.pop() ?? ''} ${current.trim()}`);
        } else {
          break;
        }
        index += 1;
      }
      blocks.push({
        kind: 'list',
        ordered,
        start: numbered === null ? 1 : Number(numbered[1]),
        items: items.map(parseInline),
      });
      continue;
    }
    const quote = QUOTE.exec(line);
    if (quote !== null) {
      flush();
      const quoted: string[] = [];
      while (index < lines.length) {
        const match = QUOTE.exec(lines[index] ?? '');
        if (match === null) {
          break;
        }
        quoted.push(match[1] ?? '');
        index += 1;
      }
      blocks.push({ kind: 'quote', lines: quoted.map(parseInline) });
      continue;
    }
    paragraph.push(line);
    index += 1;
  }
  flush();
  return blocks;
}

/**
 * Whether a character is a letter, a digit, or an underscore.
 *
 * @param character One character, or `undefined` past either end of the text.
 * @returns `true` for a word character.
 */
function isWordCharacter(character: string | undefined): boolean {
  return character !== undefined && /[\p{L}\p{N}_]/u.test(character);
}

/**
 * Whether an address may be linked to: only the web's own schemes are.
 *
 * @param href The address.
 * @returns `true` for an absolute `http` or `https` address.
 */
function isSafeHref(href: string): boolean {
  if (!URL.canParse(href)) {
    return false;
  }
  const { protocol } = new URL(href);
  return protocol === 'https:' || protocol === 'http:';
}

/** Characters a bare address does not end on, since prose puts them after one. */
const TRAILING_PUNCTUATION = /[.,;:!?)'"\]]+$/;

/**
 * Parses one line or item into inline runs.
 *
 * @param text The text.
 * @returns Its runs, in order.
 */
function parseInline(text: string): Inline[] {
  const runs: Inline[] = [];
  let plain = '';
  const pushPlain = (): void => {
    if (plain !== '') {
      runs.push({ kind: 'text', text: plain });
      plain = '';
    }
  };
  const push = (run: Inline): void => {
    pushPlain();
    runs.push(run);
  };

  let index = 0;
  while (index < text.length) {
    const character = text.charAt(index);
    const before = index > 0 ? text.charAt(index - 1) : undefined;

    if (character === '`') {
      const end = text.indexOf('`', index + 1);
      if (end > index + 1) {
        push({ kind: 'code', text: text.slice(index + 1, end) });
        index = end + 1;
        continue;
      }
    }

    if (text.startsWith('**', index) || text.startsWith('__', index)) {
      const marker = text.slice(index, index + 2);
      const end = text.indexOf(marker, index + 2);
      if (end > index + 2) {
        push({ kind: 'strong', children: parseInline(text.slice(index + 2, end)) });
        index = end + 2;
        continue;
      }
    }

    if (
      (character === '*' || (character === '_' && !isWordCharacter(before))) &&
      text.charAt(index + 1).trim() !== ''
    ) {
      const end = text.indexOf(character, index + 1);
      const closes =
        end > index + 1 &&
        text.charAt(end - 1).trim() !== '' &&
        (character === '*' || !isWordCharacter(text.charAt(end + 1)));
      if (closes) {
        push({ kind: 'em', children: parseInline(text.slice(index + 1, end)) });
        index = end + 1;
        continue;
      }
    }

    if (character === '[') {
      const close = text.indexOf('](', index + 1);
      const end = close === -1 ? -1 : text.indexOf(')', close + 2);
      if (close > index + 1 && end > close + 2) {
        const href = text.slice(close + 2, end).trim();
        if (isSafeHref(href)) {
          push({ kind: 'link', href, children: parseInline(text.slice(index + 1, close)) });
          index = end + 1;
          continue;
        }
      }
    }

    if ((text.startsWith('https://', index) || text.startsWith('http://', index)) && !isWordCharacter(before)) {
      let end = index;
      while (end < text.length && !/\s/.test(text.charAt(end))) {
        end += 1;
      }
      const href = text.slice(index, end).replace(TRAILING_PUNCTUATION, '');
      if (isSafeHref(href)) {
        push({ kind: 'link', href, children: [{ kind: 'text', text: href }] });
        index += href.length;
        continue;
      }
    }

    if (character === '@' && !isWordCharacter(before) && before !== '@') {
      const match = /^[\p{L}\p{N}][\p{L}\p{N}_-]*/u.exec(text.slice(index + 1, index + 65));
      if (match !== null) {
        const tag = match[0].replace(/-+$/, '');
        push({ kind: 'tag', tag });
        index += 1 + tag.length;
        continue;
      }
    }

    plain += character;
    index += 1;
  }
  pushPlain();
  return runs;
}
