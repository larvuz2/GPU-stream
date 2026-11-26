/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The inputs of a card that are one native control each: a slider, a number, a dropdown, a
 * segmented choice, a switch, checkboxes, a text field, and a color.
 *
 * Each is the platform's own control under the card's look, so the keyboard, touch, and
 * assistive technology work as they do everywhere: a slider moves by the arrow keys, a segmented
 * choice is a radio group, a switch is a checkbox with the `switch` role. Every control is named
 * by its label, or by its id as words where the card gave none. A control writes its value to the
 * card's state (`context.ts`) on every change, which is what lets a picture follow a slider as it
 * is dragged; on a locked card the controls are disabled and show what was chosen.
 * @module
 */
import type { ReactNode } from 'react';
import { isBoolean, isNumber, isString } from '../../../lib/narrow';
import { number, options, text, type Scalar } from '../tree';
import { clamp, range, withUnit } from '../values';
import { useInput, type InputBinding, type ViewProps } from '../view';

/** Props of {@link Labeled}. */
interface LabeledProps {
  /** The input's binding, for its name and its control's id. */
  input: InputBinding;
  /** What sits at the end of the label's line, such as a slider's value. */
  readout?: ReactNode;
  /** The control. */
  children: ReactNode;
}

/**
 * Renders a control under its label.
 *
 * @param props The component's props.
 * @returns The labeled control.
 */
function Labeled({ input, readout, children }: LabeledProps) {
  return (
    <div className="ui-input">
      {input.labeled || readout !== undefined ? (
        <div className="ui-input-head">
          {input.labeled ? (
            <label htmlFor={input.domId} className="ui-label">
              {input.label}
            </label>
          ) : (
            <span />
          )}
          {readout}
        </div>
      ) : null}
      {children}
    </div>
  );
}

/**
 * Renders a slider with its value beside its label.
 *
 * @param props The component's props.
 * @returns The slider.
 */
export function Slider({ node }: ViewProps) {
  const input = useInput(node);
  const { min, max, step } = range(node);
  const low = min ?? 0;
  const high = max ?? 100;
  const value = isNumber(input.value) ? input.value : low;
  const share = (amount: number): number => (high > low ? ((clamp(amount, low, high) - low) / (high - low)) * 100 : 0);
  // The lit part of the track runs from where the range rests to the value: from zero where the
  // range spans it, so a slider of -100 to 100 reads as a push either way, else from its least.
  const rest = share(0);
  const at = share(value);
  return (
    <Labeled
      input={input}
      readout={
        <output htmlFor={input.domId} className="ui-readout">
          {withUnit(node, value)}
        </output>
      }
    >
      <input
        id={input.domId}
        type="range"
        className="ui-range"
        min={low}
        max={high}
        step={step}
        value={value}
        disabled={input.frozen}
        aria-label={input.labeled ? undefined : input.label}
        aria-valuetext={withUnit(node, value)}
        style={{ '--ui-from': `${Math.min(rest, at)}%`, '--ui-to': `${Math.max(rest, at)}%` }}
        onChange={(event) => {
          input.set(event.target.valueAsNumber);
        }}
      />
    </Labeled>
  );
}

/**
 * Renders a number the person types, with its unit.
 *
 * @param props The component's props.
 * @returns The field.
 */
export function NumberInput({ node }: ViewProps) {
  const input = useInput(node);
  const { min, max, step } = range(node);
  const unit = text(node, 'unit');
  return (
    <Labeled input={input}>
      <span className="ui-field-wrap">
        <input
          id={input.domId}
          type="number"
          inputMode="decimal"
          className="ui-field"
          min={min ?? undefined}
          max={max ?? undefined}
          step={step}
          value={isNumber(input.value) ? input.value : ''}
          disabled={input.frozen}
          aria-label={input.labeled ? undefined : input.label}
          onChange={(event) => {
            const typed = event.target.valueAsNumber;
            if (Number.isFinite(typed)) {
              input.set(clamp(typed, min ?? -Infinity, max ?? Infinity));
            }
          }}
        />
        {unit === null ? null : (
          <span className="ui-unit" aria-hidden="true">
            {unit}
          </span>
        )}
      </span>
    </Labeled>
  );
}

/**
 * Renders a dropdown of options.
 *
 * @param props The component's props.
 * @returns The dropdown.
 */
export function Select({ node }: ViewProps) {
  const input = useInput(node);
  const choices = options(node);
  const chosen = choices.findIndex((choice) => choice.value === input.value);
  return (
    <Labeled input={input}>
      <select
        id={input.domId}
        className="ui-field ui-select"
        // An option's value may be a number or a boolean, so the control carries its place instead.
        value={chosen === -1 ? '' : String(chosen)}
        disabled={input.frozen}
        aria-label={input.labeled ? undefined : input.label}
        onChange={(event) => {
          const choice = choices[Number(event.target.value)];
          if (choice !== undefined) {
            input.set(choice.value);
          }
        }}
      >
        {chosen === -1 ? <option value="">Choose…</option> : null}
        {choices.map((choice, index) => (
          <option key={String(choice.value)} value={String(index)}>
            {choice.label}
          </option>
        ))}
      </select>
    </Labeled>
  );
}

/** Props of {@link Group}. */
interface GroupProps {
  /** The input's binding, for its name. */
  input: InputBinding;
  /** The classes of the frame that holds the choices. */
  className: string;
  /** The choices. */
  children: ReactNode;
}

/**
 * Renders a set of choices under one name.
 *
 * @param props The component's props.
 * @returns The fieldset.
 */
function Group({ input, className, children }: GroupProps) {
  return (
    <fieldset className="ui-input" disabled={input.frozen} aria-label={input.labeled ? undefined : input.label}>
      {input.labeled ? <legend className="ui-label">{input.label}</legend> : null}
      <div className={className}>{children}</div>
    </fieldset>
  );
}

/**
 * Renders two to five options side by side, one of them chosen.
 *
 * @param props The component's props.
 * @returns The radio group.
 */
export function Segmented({ node }: ViewProps) {
  const input = useInput(node);
  return (
    <Group input={input} className="ui-segmented">
      {options(node).map((choice) => (
        <label key={String(choice.value)} className="ui-segment">
          <input
            type="radio"
            className="sr-only"
            name={input.domId}
            checked={input.value === choice.value}
            onChange={() => {
              input.set(choice.value);
            }}
          />
          <span>{choice.label}</span>
        </label>
      ))}
    </Group>
  );
}

/**
 * Renders a switch.
 *
 * @param props The component's props.
 * @returns The switch with its label.
 */
export function Toggle({ node }: ViewProps) {
  const input = useInput(node);
  return (
    <label className="ui-toggle">
      <input
        id={input.domId}
        type="checkbox"
        role="switch"
        className="sr-only"
        checked={isBoolean(input.value) ? input.value : false}
        disabled={input.frozen}
        onChange={(event) => {
          input.set(event.target.checked);
        }}
      />
      <span className="ui-switch" aria-hidden="true" />
      <span className="ui-label">{input.label}</span>
    </label>
  );
}

/**
 * Renders options of which any may be chosen.
 *
 * @param props The component's props.
 * @returns The checkboxes.
 */
export function Checkboxes({ node }: ViewProps) {
  const input = useInput(node);
  const chosen: unknown[] = Array.isArray(input.value) ? input.value : [];
  const choices = options(node);
  return (
    <Group input={input} className="ui-checks">
      {choices.map((choice) => (
        <label key={String(choice.value)} className="ui-check">
          <input
            type="checkbox"
            className="sr-only"
            checked={chosen.includes(choice.value)}
            onChange={(event) => {
              // The answer keeps the options' order, whatever order they were ticked in.
              const next = choices
                .map((one): Scalar => one.value)
                .filter((value) => (value === choice.value ? event.target.checked : chosen.includes(value)));
              input.set(next);
            }}
          />
          <span className="ui-check-mark" aria-hidden="true" />
          <span>{choice.label}</span>
        </label>
      ))}
    </Group>
  );
}

/**
 * Renders a field for words: one line, or several.
 *
 * @param props The component's props.
 * @returns The field.
 */
export function Field({ node }: ViewProps) {
  const input = useInput(node);
  const lines = number(node, 'lines') ?? 1;
  const shared = {
    id: input.domId,
    className: 'ui-field',
    placeholder: text(node, 'placeholder') ?? undefined,
    value: isString(input.value) ? input.value : '',
    disabled: input.frozen,
    'aria-label': input.labeled ? undefined : input.label,
  };
  return (
    <Labeled input={input}>
      {lines > 1 ? (
        <textarea
          {...shared}
          rows={lines}
          onChange={(event) => {
            input.set(event.target.value);
          }}
        />
      ) : (
        <input
          {...shared}
          type="text"
          onChange={(event) => {
            input.set(event.target.value);
          }}
        />
      )}
    </Labeled>
  );
}

/**
 * Renders a color: suggestions to pick from, and the platform's picker for any other.
 *
 * @param props The component's props.
 * @returns The color input.
 */
export function ColorInput({ node }: ViewProps) {
  const input = useInput(node);
  const value = isString(input.value) ? input.value : '';
  const given: unknown = node.props.suggest;
  const suggested = Array.isArray(given) ? given.filter(isString) : [];
  return (
    <Labeled
      input={input}
      readout={
        <output htmlFor={input.domId} className="ui-readout">
          {value.toUpperCase()}
        </output>
      }
    >
      <div className="ui-colors">
        {suggested.map((color) => (
          <button
            key={color}
            type="button"
            className="ui-swatch-button"
            style={{ background: color }}
            aria-label={`Use ${color}`}
            aria-pressed={color.toLowerCase() === value.toLowerCase()}
            disabled={input.frozen}
            onClick={() => {
              input.set(color);
            }}
          />
        ))}
        <input
          id={input.domId}
          type="color"
          className="ui-color"
          value={value}
          disabled={input.frozen}
          aria-label={input.labeled ? undefined : input.label}
          onChange={(event) => {
            input.set(event.target.value);
          }}
        />
      </div>
    </Labeled>
  );
}
