/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The parts every tab of Settings is laid out with: its heading, and the blocks under it.
 * @module
 */
import type { ReactNode } from 'react';

/** Props of {@link TabHeading}. */
interface TabHeadingProps {
  /** The tab's name. */
  title: string;
  /** What the tab holds, in a sentence. */
  children: ReactNode;
}

/**
 * Renders a tab's heading and the sentence under it.
 *
 * @param props The component's props.
 * @returns The heading.
 */
export function TabHeading({ title, children }: TabHeadingProps) {
  return (
    <header className="pr-10">
      <h3 className="text-xl font-semibold tracking-tight">{title}</h3>
      <p className="lede mt-1.5 text-sm">{children}</p>
    </header>
  );
}

/** Props of {@link Block}. */
interface BlockProps {
  /** The block's label, where it has one. */
  label?: string;
  /** The block's content. */
  children: ReactNode;
}

/**
 * Renders one block of a tab: a part of it under a small label, set off from the one before by a
 * line.
 *
 * @param props The component's props.
 * @returns The block.
 */
export function Block({ label, children }: BlockProps) {
  return (
    <section className="settings-block">
      {label === undefined ? null : <h4 className="section-label mb-3">{label}</h4>}
      {children}
    </section>
  );
}
