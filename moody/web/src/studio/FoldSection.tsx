/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A section inside a panel that folds: its small heading, which is the control, and its body.
 *
 * The heading reads as it did before sections folded. The arrow beside it is quiet (`.fold-arrow`
 * in `studio.css`): it shows while the pointer or the keyboard is on the heading, and stays
 * faintly while the section is folded. What is folded is the workspace's to remember
 * (`folds.ts`); the body is unmounted while folded, so a folded section does no work.
 * @module
 */
import { useId, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { useFold } from './folds';

/** Props of {@link FoldSection}. */
interface FoldSectionProps {
  /** The section's id among what folds in the right column, such as `environment.engines`. */
  id: string;
  /** The heading: the section's name, with its mark or its count where it has one. */
  label: ReactNode;
  /** The body. */
  children: ReactNode;
}

/**
 * Renders a section that folds.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function FoldSection({ id, label, children }: FoldSectionProps) {
  const { open, toggle } = useFold(id);
  const bodyId = useId();
  return (
    <div>
      <h3 className="section-label">
        <button type="button" className="fold-head" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
          {label}
          <ChevronDown className="fold-arrow" aria-hidden="true" />
        </button>
      </h3>
      {open ? <div id={bodyId}>{children}</div> : null}
    </div>
  );
}
