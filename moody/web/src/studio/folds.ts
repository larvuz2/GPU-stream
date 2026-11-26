/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What is folded away in a project's right column: its modules (the Screen, Latest, Environment,
 * the Plan, the Library) and the sections inside Environment.
 *
 * Each part that folds has an id: a module's is its name (`environment`), a section's is its
 * module's and its own (`environment.engines`). The ids folded are remembered in this browser per
 * project, so a project opens the way it was left. One never opened here starts the way the last
 * project was left, so a person who always folds the same thing away does not fold it again in
 * every project.
 *
 * The workspace holds the state ({@link useFolds}) and offers it to what it draws
 * ({@link FoldsContext}), so a section deep in a panel folds itself ({@link useFold}) without the
 * panels between passing anything down.
 * @module
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { arrayOf, isString } from '../lib/narrow';
import { readPreference, writePreference } from './hooks';

/** The preference that holds what the last project was left with folded. */
const LAST = 'folds';

const isIds = arrayOf(isString);

/** What is folded in a project's right column, and how it changes. */
export interface Folds {
  /** The ids of the parts folded away. */
  folded: ReadonlySet<string>;
  /** Folds a part that is unfolded, and unfolds one that is folded. */
  toggle: (id: string) => void;
  /** Unfolds a part, as leading the person to something inside it does. */
  unfold: (id: string) => void;
}

/**
 * Holds what is folded in a project's right column, remembered in this browser.
 *
 * @param projectId The project.
 * @returns What is folded, and how it changes.
 */
export function useFolds(projectId: string): Folds {
  const key = `${LAST}.${projectId}`;
  const [folded, setFolded] = useState<ReadonlySet<string>>(
    () => new Set(readPreference(key, isIds) ?? readPreference(LAST, isIds) ?? []),
  );
  const keep = useCallback(
    (next: ReadonlySet<string>): void => {
      const ids = [...next].sort();
      setFolded(next);
      writePreference(key, ids);
      writePreference(LAST, ids);
    },
    [key],
  );
  return useMemo(
    () => ({
      folded,
      toggle: (id) => {
        const next = new Set(folded);
        if (!next.delete(id)) {
          next.add(id);
        }
        keep(next);
      },
      unfold: (id) => {
        if (folded.has(id)) {
          const next = new Set(folded);
          next.delete(id);
          keep(next);
        }
      },
    }),
    [folded, keep],
  );
}

/** What is folded in the open project's right column, for the parts inside it; `null` outside one. */
export const FoldsContext = createContext<Folds | null>(null);

/**
 * Says whether one part is unfolded, and folds or unfolds it.
 *
 * @param id The part's id.
 * @returns Whether it is unfolded, and the function that changes that. Outside a workspace the
 *   part is unfolded and stays so.
 */
export function useFold(id: string): { open: boolean; toggle: () => void } {
  const folds = useContext(FoldsContext);
  return {
    open: folds?.folded.has(id) !== true,
    toggle: () => {
      folds?.toggle(id);
    },
  };
}
