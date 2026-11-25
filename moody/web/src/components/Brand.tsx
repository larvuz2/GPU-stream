/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The product's own mark and wordmark.
 *
 * The mark is two open rings around a center, a workpiece turning on a moody, drawn inline so it
 * needs no file. The name beside it is the catalog's.
 * @module
 */
import { useId } from 'react';
import { brand } from '../lib/catalog';
import { cx } from '../lib/cx';

/** Props of {@link BrandMark}. */
interface BrandMarkProps {
  /** Classes that size the mark. */
  className?: string;
}

/**
 * Renders the mark alone, as decoration.
 *
 * @param props The component's props.
 * @returns The mark.
 */
export function BrandMark({ className }: BrandMarkProps) {
  const gradient = useId();
  const paint = `url(#${gradient})`;
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradient} x1="3" y1="3" x2="29" y2="29" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffc48f" />
          <stop offset="0.45" stopColor="#ff7a1a" />
          <stop offset="1" stopColor="#a678ff" />
        </linearGradient>
      </defs>
      <circle
        cx="16"
        cy="16"
        r="13"
        stroke={paint}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeDasharray="60 21.7"
        transform="rotate(-58 16 16)"
      />
      <circle
        cx="16"
        cy="16"
        r="7.4"
        stroke={paint}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeDasharray="30 16.5"
        transform="rotate(118 16 16)"
      />
      <circle cx="16" cy="16" r="2.7" fill={paint} />
    </svg>
  );
}

/** Props of {@link Brand}. */
interface BrandProps {
  /** Where the logo links to. */
  href: string;
  /** Extra classes for the link. */
  className?: string;
}

/**
 * Renders the mark and the product's name as a link home.
 *
 * @param props The component's props.
 * @returns The link.
 */
export function Brand({ href, className }: BrandProps) {
  return (
    <a
      href={href}
      aria-label={`${brand} home`}
      className={cx('inline-flex items-center gap-2.5 rounded-lg text-[1.15rem] font-semibold tracking-tight', className)}
    >
      <BrandMark className="size-7" />
      <span>{brand}</span>
    </a>
  );
}
