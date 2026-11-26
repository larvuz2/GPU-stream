/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The shell every panel of the right column shares: a header that folds the panel away, with room
 * for a count and the panel's own actions, over its body.
 *
 * The body is unmounted while folded, so a folded panel does no work. The arrow that folds it is
 * quiet (`.panel-chevron` in `studio.css`): it shows while the pointer or the keyboard is on the
 * header, and stays faintly while the panel is folded.
 * @module
 */
import { useId, type ReactNode } from 'react';
import { ChevronDown, type LucideIcon } from 'lucide-react';

/** Props of {@link Panel}. */
interface PanelProps {
  /** The panel's title. */
  title: string;
  /** Its icon. */
  icon: LucideIcon;
  /** Whether it is unfolded. */
  open: boolean;
  /** Folds or unfolds it. */
  onToggle: () => void;
  /** A short note after the title, such as a count. */
  badge?: ReactNode;
  /** Controls at the header's end, shown while unfolded. */
  actions?: ReactNode;
  /** The body. */
  children: ReactNode;
  /** Extra classes for the section. */
  className?: string;
}

/**
 * Renders a foldable panel.
 *
 * @param props The component's props.
 * @returns The panel.
 */
export function Panel({ title, icon: Icon, open, onToggle, badge, actions, children, className }: PanelProps) {
  const bodyId = useId();
  return (
    <section className={className === undefined ? 'panel' : `panel ${className}`} data-open={open} aria-label={title}>
      <div className="panel-header">
        <button type="button" className="panel-toggle" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
          <Icon aria-hidden="true" />
          <span className="truncate">{title}</span>
          {badge === undefined ? null : <span className="text-xs font-medium text-faint">{badge}</span>}
          <ChevronDown className="panel-chevron" aria-hidden="true" />
        </button>
        {open ? actions : null}
      </div>
      {open ? (
        <div id={bodyId} className="panel-body">
          {children}
        </div>
      ) : null}
    </section>
  );
}
