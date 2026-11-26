/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The inputs of a card that choose among tiles: `pick`, one or several options shown as tiles,
 * and `reorder`, items the person puts in order.
 *
 * `pick` is a radio group, or checkboxes with `many`, whose labels are the tiles, so it is
 * chosen with the keyboard as any radio group is and the chosen one is told to assistive
 * technology by the control itself; the lime frame is what a sighted person sees of the same
 * state. A tile is drawn over one of four things: a picture, a pixel icon (such tiles are
 * squares, the icon over its words, level with the icons beside it), a sound, or its words alone.
 *
 * A tile with a sound plays it: the player sits on the tile, over the control that chooses it,
 * so each take is heard where it is chosen and two or three are compared by ear. The player's
 * button and the choice are two controls, both reached by the keyboard, and the card plays one
 * sound at a time (`Audio.tsx`). Such tiles are never narrower than a waveform and its time
 * need: `columns` is then the most to a row, and a narrow card shows one take under another.
 *
 * On an instant card a press is the answer, so its tiles are buttons, not a selection to move
 * through: the arrow keys of a radio group would choose, and so lock the card, on the way to
 * the option meant.
 *
 * `reorder` moves an item three ways that all end in the same change of the list. Dragging its
 * handle follows the pointer, the item changing places with the neighbor whose middle the pointer
 * crosses, so the list is always a valid order and letting go needs no drop target. The arrow
 * buttons move it one place. With the handle focused, the arrow keys do the same. Each move is
 * announced ("Lighthouse, 2 of 5"), since the item's new place is otherwise only seen.
 * @module
 */
import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { ArrowDown, ArrowRight, ArrowUp, Check, GripVertical } from 'lucide-react';
import { useCard } from '../context';
import { flag, number, options, type Scalar, type UiOption } from '../tree';
import { useInput, type ViewProps } from '../view';
import { Missing } from './Adjusted';
import { Sound } from './Audio';
import { PixelIcon } from './PixelIcon';

/**
 * Renders options as tiles to choose from.
 *
 * @param props The component's props.
 * @returns The group of choices.
 */
export function Pick({ node }: ViewProps) {
  const card = useCard();
  const input = useInput(node);
  const many = flag(node, 'many');
  const choices = options(node, 'tile');
  const chosen: unknown[] = Array.isArray(input.value) ? input.value : [input.value];

  /**
   * Chooses an option, or with `many` adds or removes it.
   *
   * @param choice The option.
   * @param on Whether it is now chosen.
   */
  function choose(choice: UiOption, on: boolean): void {
    if (!many) {
      input.set(choice.value);
      return;
    }
    // The answer keeps the options' order, whatever order they were chosen in.
    input.set(
      choices
        .map((one): Scalar => one.value)
        .filter((value) => (value === choice.value ? on : chosen.includes(value))),
    );
  }

  return (
    // Each choice is disabled by itself, not the group, so a tile's sound still plays on a locked card.
    <fieldset
      className="ui-input"
      data-frozen={input.frozen ? 'true' : undefined}
      aria-label={input.labeled ? undefined : input.label}
    >
      {input.labeled ? <legend className="ui-label">{input.label}</legend> : null}
      <div
        className="ui-grid"
        data-columns={number(node, 'columns') ?? 3}
        data-tiles={choices.some((choice) => choice.audio !== null) ? 'audio' : undefined}
      >
        {choices.map((choice) => {
          const picked = chosen.includes(choice.value);
          const words = (
            <span className="ui-pick-text">
              <span className="ui-pick-label">{choice.label}</span>
              {choice.note === null ? null : <span className="ui-pick-note">{choice.note}</span>}
            </span>
          );
          const control = (
            <input
              type={many ? 'checkbox' : 'radio'}
              className="sr-only"
              name={input.domId}
              checked={picked}
              disabled={input.frozen}
              onChange={(event) => {
                choose(choice, event.target.checked);
              }}
            />
          );
          const press = {
            type: 'button' as const,
            disabled: input.frozen,
            // The one that was pressed is told as the current one, since a button holds no choice.
            'aria-current': picked ? ('true' as const) : undefined,
            onClick: () => {
              choose(choice, true);
            },
          };
          if (choice.audio !== null) {
            const sound = card.media(choice.audio);
            return (
              <div
                key={String(choice.value)}
                className="ui-pick"
                data-art="audio"
                data-chosen={picked ? 'true' : undefined}
              >
                {sound === null ? <Missing name={choice.audio} /> : <Sound url={sound.url} name={choice.label} titled={false} />}
                {input.instant ? (
                  <button {...press} className="ui-pick-choose">
                    {words}
                    <ArrowRight className="size-4 flex-none" aria-hidden="true" />
                  </button>
                ) : (
                  <label className="ui-pick-choose">
                    {control}
                    <span className="ui-check-mark" data-round={many ? undefined : 'true'} aria-hidden="true" />
                    {words}
                  </label>
                )}
              </div>
            );
          }
          const media = card.media(choice.image);
          const art =
            choice.icon !== null ? (
              <span className="ui-pick-icon">
                <PixelIcon art={choice.icon} />
              </span>
            ) : media === null ? null : (
              <span className="ui-pick-art">
                <img src={media.url} alt="" loading="lazy" decoding="async" className="ui-cover" />
              </span>
            );
          const kind = choice.icon !== null ? 'icon' : media === null ? 'words' : 'image';
          // A tile with an icon is sized by what it holds, so its icon and words share one box.
          const face =
            choice.icon === null ? (
              <>
                {art}
                {words}
              </>
            ) : (
              <span className="ui-pick-square">
                {art}
                {words}
              </span>
            );
          return input.instant ? (
            <button
              key={String(choice.value)}
              {...press}
              className="ui-pick"
              data-art={kind}
              data-chosen={picked ? 'true' : undefined}
            >
              {face}
            </button>
          ) : (
            <label key={String(choice.value)} className="ui-pick" data-art={kind}>
              {control}
              {face}
              <span className="ui-pick-mark" aria-hidden="true">
                <Check className="size-3" />
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * Moves one item of a list to another place.
 *
 * @param list The list.
 * @param from Where the item is.
 * @param to Where it goes.
 * @returns The list with the item moved, or the list itself where either place is outside it.
 */
function moved<T>(list: readonly T[], from: number, to: number): T[] {
  const next = [...list];
  const [item] = next.splice(from, 1);
  if (item === undefined || to < 0 || to >= list.length) {
    return [...list];
  }
  next.splice(to, 0, item);
  return next;
}

/**
 * Renders items the person puts in order.
 *
 * @param props The component's props.
 * @returns The list.
 */
export function Reorder({ node }: ViewProps) {
  const card = useCard();
  const input = useInput(node);
  const choices = options(node);
  const list = useRef<HTMLOListElement>(null);
  const [dragging, setDragging] = useState<Scalar | null>(null);
  const [said, setSaid] = useState('');
  const order: unknown[] = Array.isArray(input.value) ? input.value : choices.map((choice) => choice.value);
  const ordered = order.flatMap((value) => choices.filter((choice) => choice.value === value));

  /**
   * Moves an item and says where it went.
   *
   * @param from Its place.
   * @param to The place it goes to.
   */
  function move(from: number, to: number): void {
    const item = ordered[from];
    if (item === undefined || to < 0 || to >= ordered.length || from === to) {
      return;
    }
    input.set(moved(ordered, from, to).map((choice) => choice.value));
    setSaid(`${item.label}, ${to + 1} of ${ordered.length}`);
  }

  /**
   * Follows the pointer while an item is dragged: it changes places with the neighbor whose
   * middle the pointer has crossed.
   *
   * @param event The pointer's move over the handle that captured it.
   */
  function onPointerMove(event: PointerEvent): void {
    const from = ordered.findIndex((choice) => choice.value === dragging);
    const rows = list.current === null ? [] : [...list.current.children];
    if (from === -1) {
      return;
    }
    const above = rows[from - 1]?.getBoundingClientRect();
    const below = rows[from + 1]?.getBoundingClientRect();
    if (above !== undefined && event.clientY < above.top + above.height / 2) {
      move(from, from - 1);
    } else if (below !== undefined && event.clientY > below.top + below.height / 2) {
      move(from, from + 1);
    }
  }

  /**
   * Moves the item whose handle has the focus by the arrow keys.
   *
   * @param event The key press.
   * @param index The item's place.
   */
  function onKeyDown(event: KeyboardEvent, index: number): void {
    const step = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
    if (step !== 0) {
      event.preventDefault();
      move(index, index + step);
    }
  }

  return (
    <div className="ui-input" role="group" aria-label={input.label}>
      {input.labeled ? <p className="ui-label">{input.label}</p> : null}
      <ol ref={list} className="ui-reorder">
        {ordered.map((choice, index) => {
          const media = card.media(choice.image);
          return (
            <li key={String(choice.value)} className="ui-reorder-item" data-dragging={dragging === choice.value}>
              <button
                type="button"
                className="ui-reorder-handle"
                aria-label={`Move ${choice.label}: drag, or use the up and down arrow keys`}
                disabled={input.frozen}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                  setDragging(choice.value);
                }}
                onPointerMove={dragging === choice.value ? onPointerMove : undefined}
                onPointerUp={() => {
                  setDragging(null);
                }}
                onPointerCancel={() => {
                  setDragging(null);
                }}
                onKeyDown={(event) => {
                  onKeyDown(event, index);
                }}
              >
                <GripVertical className="size-4" aria-hidden="true" />
              </button>
              <span className="ui-reorder-place" aria-hidden="true">
                {index + 1}
              </span>
              {media === null ? null : (
                <span className="ui-reorder-art">
                  <img src={media.url} alt="" loading="lazy" decoding="async" draggable={false} className="ui-cover" />
                </span>
              )}
              <span className="ui-pick-text">
                <span className="ui-pick-label">{choice.label}</span>
                {choice.note === null ? null : <span className="ui-pick-note">{choice.note}</span>}
              </span>
              <span className="ui-reorder-buttons">
                <button
                  type="button"
                  className="ui-icon-button"
                  aria-label={`Move ${choice.label} up`}
                  disabled={input.frozen || index === 0}
                  onClick={() => {
                    move(index, index - 1);
                  }}
                >
                  <ArrowUp className="size-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="ui-icon-button"
                  aria-label={`Move ${choice.label} down`}
                  disabled={input.frozen || index === ordered.length - 1}
                  onClick={() => {
                    move(index, index + 1);
                  }}
                >
                  <ArrowDown className="size-3.5" aria-hidden="true" />
                </button>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="sr-only" aria-live="polite">
        {said}
      </p>
    </div>
  );
}
