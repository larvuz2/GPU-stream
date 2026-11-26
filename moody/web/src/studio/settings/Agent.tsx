/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Agent tab of Settings: what one turn may spend on the model, in dollars, and how many steps
 * it may take, as settings of the person's account (`Limits` in `moody/STUDIO.md`).
 *
 * Each field shows the number that applies. A limit the person has not set is the deployment's
 * default and says so; one they set says what the default is and offers the way back to it, which
 * is sent as `null`, never as the default's number, so the account follows the deployment if its
 * default moves. Beside each is the deployment's ceiling, which no account sets a limit above.
 *
 * A value is checked here before anything is sent: a spend must be above zero and no higher than
 * its ceiling, and steps a whole number from one to theirs. The control plane checks the same and
 * may still refuse (its ceiling moved, say), which the tab shows in the server's own words. Only
 * what changed is sent, and the button is there to press only while something has.
 *
 * The tab is also where the line a turn leaves in the conversation leads when it stopped at one
 * of these limits, in which case the field of that limit has the focus.
 * @module
 */
import { useEffect, useId, useRef, useState, type SubmitEvent } from 'react';
import { Check } from 'lucide-react';
import type { LimitChanges, Limits, TurnLimit } from '../../lib/api';
import { creditCount, usd } from '../../lib/format';
import { ErrorNotice } from '../Notice';
import { limitText } from '../present';

/** Props of {@link LimitsForm}. */
interface LimitsFormProps {
  /** The account's limits. */
  limits: Limits;
  /** The limit a turn just stopped at, whose field takes the focus; `null` for neither. */
  reached: TurnLimit | null;
  /** Saves the limits that changed. Rejects with an `ApiError`, 400 for a value the server refuses. */
  onSave: (changes: LimitChanges) => Promise<void>;
}

/** One of the two limits, as its field needs it. */
interface FieldSpec {
  /** Which limit of a turn it is. */
  limit: TurnLimit;
  /** The field's label. */
  label: string;
  /** What the limit bounds, in a sentence. */
  help: string;
  /** Whether only whole numbers are taken. */
  whole: boolean;
  /**
   * Says what the field takes, for a value it refuses.
   *
   * @param max The deployment's ceiling.
   * @returns The sentence.
   */
  refusal: (max: number) => string;
}

/** The two fields, the spend first. */
const FIELDS: readonly FieldSpec[] = [
  {
    limit: 'budget',
    label: 'Model spend per turn',
    help: 'What the agent’s model may cost in one turn, in US dollars.',
    whole: false,
    refusal: (max) => `Enter an amount above $0, up to ${usd(max)}.`,
  },
  {
    limit: 'steps',
    label: 'Steps per turn',
    help: 'How many times the agent may think and act in one turn.',
    whole: true,
    refusal: (max) => `Enter a whole number of steps, from 1 to ${creditCount(max)}.`,
  },
];

/** The key of each limit in the control plane's shapes. */
const KEYS = { budget: 'turn_budget_usd', steps: 'turn_limit' } as const;

/** A field as the person left it: on the deployment's default, or the text they typed. */
type Entry = { own: false } | { own: true; text: string };

/**
 * Reads what a field holds.
 *
 * @param entry The field.
 * @param spec Which limit it is.
 * @param max The deployment's ceiling for it.
 * @returns The value to save (`null` for the default), or `undefined` for text the field refuses.
 */
function valueOf(entry: Entry, spec: FieldSpec, max: number): number | null | undefined {
  if (!entry.own) {
    return null;
  }
  const text = entry.text.trim().replace(/^\$/, '');
  const value = text === '' ? Number.NaN : Number(text);
  const fits = Number.isFinite(value) && value > 0 && value <= max && (!spec.whole || Number.isInteger(value));
  return fits ? value : undefined;
}

/**
 * Renders the two limits of a turn, and what the last attempt to save them came to.
 *
 * @param props The component's props.
 * @returns The form.
 */
export function LimitsForm({ limits, reached, onSave }: LimitsFormProps) {
  const [entries, setEntries] = useState<Record<TurnLimit, Entry>>(() => ({
    budget: limits.own.turn_budget_usd === null ? { own: false } : { own: true, text: String(limits.own.turn_budget_usd) },
    steps: limits.own.turn_limit === null ? { own: false } : { own: true, text: String(limits.own.turn_limit) },
  }));
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // What saving would send, or `null` while a field holds what it refuses.
  let changes: LimitChanges | null = {};
  for (const spec of FIELDS) {
    const key = KEYS[spec.limit];
    const value = valueOf(entries[spec.limit], spec, limits.max[key]);
    if (value === undefined) {
      changes = null;
      break;
    }
    if (value !== limits.own[key]) {
      changes[key] = value;
    }
  }
  const unchanged = changes !== null && Object.keys(changes).length === 0;

  /**
   * Saves what changed, or shows which field refuses its value.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setChecked(true);
    setError(null);
    if (changes === null || unchanged) {
      return;
    }
    setBusy(true);
    try {
      await onSave(changes);
      setSaved(true);
      setChecked(false);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <div className="grid grid-cols-1 gap-5 sm:max-w-md">
        {FIELDS.map((spec) => {
          const key = KEYS[spec.limit];
          return (
            <LimitField
              key={spec.limit}
              spec={spec}
              entry={entries[spec.limit]}
              fallback={limits.default[key]}
              max={limits.max[key]}
              checked={checked}
              focused={reached === spec.limit}
              onEntry={(entry) => {
                setEntries({ ...entries, [spec.limit]: entry });
                setError(null);
                setSaved(false);
              }}
            />
          );
        })}
      </div>
      {error === null ? null : (
        <div className="mt-4 sm:max-w-md">
          <ErrorNotice error={error} />
        </div>
      )}
      <div className="mt-6 flex items-center gap-3">
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || unchanged}>
          {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : null}
          Save limits
        </button>
        <p className="flex items-center gap-1.5 text-sm text-muted" role="status">
          {saved && unchanged ? (
            <>
              <Check className="size-4 text-ok" aria-hidden="true" />
              Saved. Your next turn runs under these.
            </>
          ) : null}
        </p>
      </div>
    </form>
  );
}

/** Props of {@link LimitField}. */
interface LimitFieldProps {
  /** Which limit the field sets. */
  spec: FieldSpec;
  /** What the field holds. */
  entry: Entry;
  /** The deployment's default, which applies while the person has set nothing. */
  fallback: number;
  /** The deployment's ceiling. */
  max: number;
  /** Whether saving was tried, after which a refused value says so. */
  checked: boolean;
  /** Whether the field takes the focus when the tab opens. */
  focused: boolean;
  /** Replaces what the field holds. */
  onEntry: (entry: Entry) => void;
}

/**
 * Renders one limit: its field, whether it is on the default, the way back to the default, and
 * its ceiling.
 *
 * @param props The component's props.
 * @returns The field.
 */
function LimitField({ spec, entry, fallback, max, checked, focused, onEntry }: LimitFieldProps) {
  const fieldId = useId();
  const helpId = useId();
  const refusalId = useId();
  const field = useRef<HTMLInputElement>(null);
  const refused = checked && valueOf(entry, spec, max) === undefined;
  useEffect(() => {
    if (!focused) {
      return;
    }
    // The dialog gives its first control the focus as it opens; this field takes it a frame later.
    const frame = window.requestAnimationFrame(() => {
      field.current?.select();
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [focused]);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={fieldId} className="text-sm font-medium">
          {spec.label}
        </label>
        {entry.own ? (
          <button
            type="button"
            className="link text-xs"
            onClick={() => {
              onEntry({ own: false });
              field.current?.focus();
            }}
          >
            Use the default ({limitText(spec.limit, fallback)})
          </button>
        ) : (
          <span className="pill h-5 border-line px-1.5 text-[0.6875rem] font-medium text-muted">Default</span>
        )}
      </div>
      <div className="relative mt-1.5">
        {spec.whole ? null : (
          <span className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted" aria-hidden="true">
            $
          </span>
        )}
        <input
          ref={field}
          id={fieldId}
          className={spec.whole ? 'field tabular-nums' : 'field pl-7 tabular-nums'}
          inputMode={spec.whole ? 'numeric' : 'decimal'}
          autoComplete="off"
          aria-describedby={refused ? `${helpId} ${refusalId}` : helpId}
          aria-invalid={refused}
          value={entry.own ? entry.text : String(fallback)}
          onChange={(event) => {
            onEntry({ own: true, text: event.target.value });
          }}
        />
      </div>
      <p id={helpId} className="mt-1.5 text-xs leading-relaxed text-faint">
        {spec.help} Up to {limitText(spec.limit, max)}.
      </p>
      {refused ? (
        <p id={refusalId} className="mt-1 text-xs text-bad" role="alert">
          {spec.refusal(max)}
        </p>
      ) : null}
    </div>
  );
}
