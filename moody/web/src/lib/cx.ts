/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Class list assembly.
 * @module
 */

/**
 * Joins the class names that apply.
 *
 * @param names Class names, with `false`, `null`, or `undefined` for one that does not apply.
 * @returns The names that apply, separated by spaces.
 */
export function cx(...names: (string | false | null | undefined)[]): string {
  return names.filter((name) => typeof name === 'string' && name !== '').join(' ');
}
