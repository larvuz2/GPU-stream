/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * How the pages write money, credits, durations, dates, and a catalog name inside a sentence.
 * @module
 */

const dollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const wholeDollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const count = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
const date = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

/**
 * Writes an amount of US dollars, without cents when there are none.
 *
 * @param amount The amount.
 * @returns Text such as `$1.80` or `$10`.
 */
export function usd(amount: number): string {
  return Number.isInteger(amount) ? wholeDollars.format(amount) : dollars.format(amount);
}

/**
 * Writes a catalog name, such as a format, as it reads inside a sentence: its first letter lowered
 * and the rest as written, so "Concept art" is "concept art" and "3D object" keeps its D.
 *
 * @param name The name, as the catalog writes it.
 * @returns The name for the middle of a sentence.
 */
export function midSentence(name: string): string {
  return name.charAt(0).toLowerCase() + name.slice(1);
}

/**
 * Writes a price that is compared with others, always to the cent so a column of them lines up.
 *
 * @param amount The amount in US dollars.
 * @returns Text such as `$3.00`.
 */
export function price(amount: number): string {
  return dollars.format(amount);
}

/**
 * Writes a number of credits with thousands separators.
 *
 * @param credits The number of credits.
 * @returns Text such as `2,750`.
 */
export function creditCount(credits: number): string {
  return count.format(credits);
}

/**
 * Writes a number of tokens as briefly as a line of small print allows.
 *
 * @param tokens The number of tokens.
 * @returns Text such as `940`, `6.1K`, or `1.2M`.
 */
export function tokenCount(tokens: number): string {
  return compact.format(tokens);
}

/** The units a size on disk is written in, each a thousand of the one before. */
const SIZE_UNITS = ['bytes', 'KB', 'MB', 'GB', 'TB'] as const;

/**
 * Writes a size on disk in the largest unit it reaches, as a file manager would.
 *
 * @param bytes The size in bytes.
 * @returns Text such as `2.4 GB` or `512 bytes`.
 */
export function sizeText(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < SIZE_UNITS.length - 1) {
    value /= 1000;
    unit += 1;
  }
  return `${count.format(value)} ${SIZE_UNITS[unit] ?? 'bytes'}`;
}

/**
 * Writes a fraction as a whole percentage.
 *
 * @param fraction The fraction, `0.1` for ten percent.
 * @returns Text such as `10%`.
 */
export function percentage(fraction: number): string {
  return percent.format(fraction);
}

/**
 * Writes a span of minutes the way a person would say it.
 *
 * @param minutes Whole minutes.
 * @returns Text such as `45 min`, `1 hr`, or `2 hr 30 min`.
 */
export function minutesText(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) {
    return `${rest} min`;
  }
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`;
}

/**
 * Writes an elapsed time as a running clock.
 *
 * @param milliseconds The elapsed time; a negative one reads as zero.
 * @returns Text such as `4:07` or `1:02:33`.
 */
export function clock(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  const pad = (value: number): string => String(value).padStart(2, '0');
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds % 60)}` : `${minutes}:${pad(seconds % 60)}`;
}

/**
 * Parses a timestamp of the control plane.
 *
 * @param iso An ISO 8601 timestamp, or `null`.
 * @returns Milliseconds since the epoch, or `null` for a missing or unreadable timestamp.
 */
export function timestamp(iso: string | null): number | null {
  if (iso === null) {
    return null;
  }
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * Writes a timestamp as a short date and time in the reader's time zone.
 *
 * @param iso An ISO 8601 timestamp, or `null`.
 * @returns Text such as `Nov 21, 2:05 PM`, or a dash for a missing or unreadable timestamp.
 */
export function shortDateTime(iso: string | null): string {
  const parsed = timestamp(iso);
  return parsed === null ? '—' : dateTime.format(parsed);
}

/**
 * Writes a timestamp as a date in the reader's time zone.
 *
 * @param iso An ISO 8601 timestamp, or `null`.
 * @returns Text such as `Nov 21, 2026`, or a dash for a missing or unreadable timestamp.
 */
export function shortDate(iso: string | null): string {
  const parsed = timestamp(iso);
  return parsed === null ? '—' : date.format(parsed);
}

/**
 * Writes how long something lasted, to the minute once it is past one.
 *
 * @param milliseconds The span; a negative one reads as zero.
 * @returns Text such as `40 sec`, `12 min`, or `1 hr 5 min`.
 */
export function spanText(milliseconds: number): string {
  const seconds = Math.max(0, Math.round(milliseconds / 1000));
  return seconds < 60 ? `${seconds} sec` : minutesText(Math.round(seconds / 60));
}
