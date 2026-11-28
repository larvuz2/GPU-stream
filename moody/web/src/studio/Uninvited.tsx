/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The page a signed-in person sees in place of the studio when the control plane does not serve
 * their account: a deployment open by invitation, and an address that is not on its list.
 *
 * The control plane refuses such an account everything, so a studio around that would be a frame
 * of failed requests. This says the one thing that is true instead, in the control plane's own
 * words, which name the address the person signed in with: the usual cause is the right person
 * on the wrong address. They can ask again, once invited, or sign out to use another address.
 * @module
 */
import { Mail } from 'lucide-react';
import { BrandMark } from '../components/Brand';
import { brand } from '../lib/catalog';

/** Props of {@link Uninvited}. */
interface UninvitedProps {
  /** What the control plane said when it refused the account. */
  message: string;
  /** Asks the control plane again. */
  onRetry: () => void;
  /** Signs the person out. */
  onSignOut: () => void;
}

/**
 * Renders the page of an account that is not invited.
 *
 * @param props The component's props.
 * @returns The page.
 */
export function Uninvited({ message, onRetry, onSignOut }: UninvitedProps) {
  return (
    <main className="grid min-h-dvh place-items-center px-6 py-12">
      <div className="w-full max-w-md text-center">
        <BrandMark className="mx-auto h-6 text-fg" />
        <span className="icon-tile mx-auto mt-8 size-14">
          <Mail className="size-6" aria-hidden="true" />
        </span>
        <h1 className="display mt-5 text-2xl">{brand} is open by invitation</h1>
        <p className="lede mt-3 text-[0.9375rem] break-words" role="status">
          {message}
        </p>
        <div className="mt-7 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            Try again
          </button>
          <button type="button" className="btn btn-ghost" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </div>
    </main>
  );
}
