/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The site's build-time configuration, read in this one place.
 *
 * Every variable is optional: a build with none of them still renders both pages in full, with
 * sign-up shown as opening soon and the dashboard as not connected. A variable set to an empty
 * string counts as unset, so a blank field in a host's settings does not turn a feature half on.
 * @module
 */

/** What the Supabase client needs to reach a project. */
export interface SupabaseConfig {
  /** The project's URL. */
  url: string;
  /** The project's publishable key, the one that is safe in a page. */
  publishableKey: string;
}

/**
 * Reads one variable as a trimmed value.
 *
 * @param value What Vite inlined for the variable.
 * @returns The value, or `null` when it is unset or blank.
 */
function setting(value: string | undefined): string | null {
  const trimmed = value?.trim() ?? '';
  return trimmed === '' ? null : trimmed;
}

const supabaseUrl = setting(import.meta.env.VITE_SUPABASE_URL);
const supabasePublishableKey = setting(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY);

/** The Supabase project, or `null` when either half of it is missing: sign-up is then not open. */
export const supabaseConfig: SupabaseConfig | null =
  supabaseUrl !== null && supabasePublishableKey !== null
    ? { url: supabaseUrl, publishableKey: supabasePublishableKey }
    : null;

/** The control plane's base URL without a trailing slash, or `null` when it is not connected. */
export const apiUrl: string | null = setting(import.meta.env.VITE_MOODY_API_URL)?.replace(/\/+$/, '') ?? null;

/**
 * The address of the document a custom card's frame is opened on, which the control plane serves
 * with a policy of its own (`studio/ui/sandbox.ts`), or `null` when no control plane is connected.
 */
export const cardFrameUrl: string | null = apiUrl === null ? null : `${apiUrl}/v1/card-frame`;
