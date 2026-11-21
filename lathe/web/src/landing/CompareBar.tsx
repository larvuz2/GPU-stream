/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The bar above the landing page's navigation that switches between its two takes.
 *
 * It is a tool for whoever is deciding between the takes, not part of either: slim, tinted apart
 * from the page's own calls to action, and the same on both. The switch is a group of two native
 * radio buttons drawn as a segmented control, so the arrow keys move it and a screen reader
 * announces it as a choice of one.
 *
 * The bar sticks to the top of the viewport and the navigation sticks beneath it. The stylesheet
 * reads the bar's presence to move the navigation and the anchor offset down by its height
 * (`--compare-bar` in `styles.css`), so a page without the bar needs no change.
 * @module
 */
import { useId } from 'react';
import { SplitSquareHorizontal } from 'lucide-react';
import type { LandingOption } from './option';

/** The two takes, as the switch names them. */
const CHOICES: readonly { option: LandingOption; name: string; approach: string }[] = [
  { option: 1, name: 'Option 1', approach: 'Technical' },
  { option: 2, name: 'Option 2', approach: 'Creative' },
];

/** Props of {@link CompareBar}. */
interface CompareBarProps {
  /** The take being shown. */
  option: LandingOption;
  /** Called with the take the reader picked. */
  onChoose: (option: LandingOption) => void;
}

/**
 * Renders the comparison bar.
 *
 * @param props The component's props.
 * @returns The bar.
 */
export function CompareBar({ option, onChoose }: CompareBarProps) {
  const labelId = useId();
  return (
    <aside className="compare-bar" aria-label="Landing page comparison">
      <div className="shell flex h-full items-center justify-center gap-4">
        <p
          id={labelId}
          className="flex items-center gap-2 text-[0.6875rem] font-semibold tracking-[0.16em] text-iris-300 uppercase max-sm:sr-only"
        >
          <SplitSquareHorizontal className="size-3.5" aria-hidden="true" />
          Comparing landing pages
        </p>
        <div role="radiogroup" aria-labelledby={labelId} className="segmented">
          {CHOICES.map((choice) => (
            <label key={choice.option} className="segment">
              <input
                type="radio"
                name="landing-option"
                value={choice.option}
                className="sr-only"
                checked={choice.option === option}
                onChange={() => {
                  onChoose(choice.option);
                }}
              />
              <span>{choice.name}</span>
              <span className="opacity-45" aria-hidden="true">
                ·
              </span>
              <span className="font-medium">{choice.approach}</span>
            </label>
          ))}
        </div>
      </div>
    </aside>
  );
}
