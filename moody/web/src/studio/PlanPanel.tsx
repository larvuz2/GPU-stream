/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Plan panel's body: the agent's steps for the project, each with its state, under a bar of
 * how many are done. The agent writes the plan (`plan` events); the panel only shows it.
 * @module
 */
import { Check, CircleAlert, Circle, LoaderCircle } from 'lucide-react';
import type { PlanItem, PlanStatus } from '../lib/api';
import { cx } from '../lib/cx';

/** How each state of a step is drawn and said. */
const STEP: Readonly<Record<PlanStatus, { label: string; className: string }>> = {
  pending: { label: 'To do', className: 'text-faint' },
  active: { label: 'In progress', className: 'text-fg' },
  done: { label: 'Done', className: 'text-ok' },
  blocked: { label: 'Blocked', className: 'text-warn' },
};

/** Props of {@link PlanBody}. */
interface PlanBodyProps {
  /** The plan. */
  items: PlanItem[];
}

/**
 * Renders the plan.
 *
 * @param props The component's props.
 * @returns The steps.
 */
export function PlanBody({ items }: PlanBodyProps) {
  if (items.length === 0) {
    return <p className="text-sm text-faint">The agent writes its plan here as the work takes shape.</p>;
  }
  const done = items.filter((item) => item.status === 'done').length;
  return (
    <div>
      <div
        className="plan-bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={items.length}
        aria-valuenow={done}
        aria-label="Plan progress"
      >
        <span style={{ width: `${(done / items.length) * 100}%` }} />
      </div>
      <ol className="mt-3 grid grid-cols-1 gap-0.5">
        {items.map((item) => {
          const step = STEP[item.status];
          const Icon =
            item.status === 'done'
              ? Check
              : item.status === 'active'
                ? LoaderCircle
                : item.status === 'blocked'
                  ? CircleAlert
                  : Circle;
          return (
            <li
              key={item.id}
              className={cx(
                'flex items-start gap-2.5 rounded-lg px-2 py-1.5 text-sm',
                item.status === 'active' && 'bg-ink-800',
              )}
            >
              <Icon
                className={cx(
                  'mt-0.5 size-3.5 flex-none',
                  step.className,
                  item.status === 'active' && 'animate-spin [animation-duration:2.4s]',
                )}
                aria-label={step.label}
              />
              <span className={cx('min-w-0 flex-1', item.status === 'done' ? 'text-muted' : 'text-fg/90')}>
                {item.title}
              </span>
              {item.status === 'blocked' || item.status === 'active' ? (
                <span className={cx('text-[0.6875rem] font-medium', step.className)}>{step.label}</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
