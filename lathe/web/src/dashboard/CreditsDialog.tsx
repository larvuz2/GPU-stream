/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's "Add credits" dialog: the catalog's credit packs, each a button that starts a
 * checkout.
 *
 * The checkout itself is hosted elsewhere: the control plane returns its address and the browser
 * goes there. A control plane without billing configured answers 503, which the dialog says in
 * plain words rather than as an error.
 * @module
 */
import { useId, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Dialog } from '../components/Dialog';
import { ApiError } from '../lib/api';
import { catalog, packBonus, type CreditPack } from '../lib/catalog';
import { creditCount, percentage, usd } from '../lib/format';
import { NOT_CONFIGURED } from './messages';
import { ErrorNotice, Notice } from './Notice';

/** Props of {@link CreditsDialog}. */
interface CreditsDialogProps {
  /** Whether the dialog is shown. */
  open: boolean;
  /** Closes the dialog. */
  onClose: () => void;
  /** Starts a checkout for a pack and returns the page to send the browser to. */
  onCheckout: (pack: string) => Promise<string>;
}

/**
 * Renders the dialog.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function CreditsDialog({ open, onClose, onCheckout }: CreditsDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={open} onClose={onClose} labelledBy={titleId} wide>
      <Packs titleId={titleId} onCheckout={onCheckout} />
    </Dialog>
  );
}

/** Props of {@link Packs}. */
interface PacksProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** Starts a checkout for a pack. */
  onCheckout: (pack: string) => Promise<string>;
}

/**
 * Renders the dialog's content: the packs, and what the last attempt to buy one came to.
 *
 * @param props The component's props.
 * @returns The content.
 */
function Packs({ titleId, onCheckout }: PacksProps) {
  const [buying, setBuying] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  /**
   * Starts the checkout for a pack and sends the browser to it.
   *
   * @param pack The pack to buy.
   */
  async function buy(pack: CreditPack): Promise<void> {
    setBuying(pack.id);
    setError(null);
    try {
      window.location.assign(await onCheckout(pack.id));
    } catch (failure) {
      setError(failure);
      setBuying(null);
    }
  }

  const paymentsOff = error instanceof ApiError && error.status === NOT_CONFIGURED;
  return (
    <div>
      <h2 id={titleId} className="display pr-10 text-[1.7rem]">
        Add credits
      </h2>
      <p className="lede mt-2 text-[0.9375rem]">
        1 credit is {usd(catalog.credit_usd)}. Credits are spent by the minute while a session runs.
      </p>
      <ul className="mt-6 grid gap-3 sm:grid-cols-3">
        {catalog.credit_packs.map((pack) => {
          const bonus = packBonus(pack);
          return (
            <li key={pack.id}>
              <button
                type="button"
                className="choice h-full w-full flex-col items-start p-5 text-left focus-visible:rounded-2xl"
                disabled={buying !== null}
                onClick={() => {
                  void buy(pack);
                }}
              >
                <span className="flex w-full items-center justify-between gap-2">
                  <span className="display text-3xl">{usd(pack.usd)}</span>
                  {bonus > 0 ? (
                    <span className="pill h-6 border-ember/40 bg-ember/10 text-[0.6875rem] text-ember-200 backdrop-blur-none">
                      +{percentage(bonus)}
                    </span>
                  ) : null}
                </span>
                <span className="mt-2 text-sm font-medium">{creditCount(pack.credits)} credits</span>
                <span className="mt-4 flex items-center gap-1.5 text-sm font-semibold text-ember-300">
                  {buying === pack.id ? <span className="spinner" aria-hidden="true" /> : null}
                  {buying === pack.id ? 'Opening checkout…' : 'Buy'}
                  {buying === pack.id ? null : <ArrowRight className="size-4" aria-hidden="true" />}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="mt-5">
        {paymentsOff ? (
          <Notice tone="info" title="Payments are not switched on yet." announce>
            Your balance is unchanged. Check back soon.
          </Notice>
        ) : (
          <ErrorNotice error={error} />
        )}
      </div>
    </div>
  );
}
