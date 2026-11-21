/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Guards that check an `unknown` value into a type.
 *
 * A response body is `unknown` where it is parsed and reaches a typed value only through these, so
 * nothing in the site asserts a shape it did not check.
 * @module
 */

/** A guard for one type. */
export type Guard<T> = (value: unknown) => value is T;

/**
 * Whether a value is a plain object whose fields can be read.
 *
 * @param value The value to check.
 * @returns `true` for a non-null object that is not an array.
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Whether a value is a string.
 *
 * @param value The value to check.
 * @returns `true` for a string.
 */
export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

/**
 * Whether a value is a finite number.
 *
 * @param value The value to check.
 * @returns `true` for a number that is neither `NaN` nor infinite.
 */
export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Whether a value is a boolean.
 *
 * @param value The value to check.
 * @returns `true` for `true` or `false`.
 */
export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

/**
 * Widens a guard to accept `null` as well.
 *
 * @param guard The guard for the non-null type.
 * @returns A guard for that type or `null`.
 */
export function nullable<T>(guard: Guard<T>): Guard<T | null> {
  return (value: unknown): value is T | null => value === null || guard(value);
}

/**
 * Builds a guard for an array whose every item passes a guard.
 *
 * @param guard The guard for one item.
 * @returns A guard for the array.
 */
export function arrayOf<T>(guard: Guard<T>): Guard<T[]> {
  return (value: unknown): value is T[] => Array.isArray(value) && value.every(guard);
}
