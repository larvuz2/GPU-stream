/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Billing tab of Settings: the credit balance, what a credit is worth, and buying more.
 *
 * Every figure is the catalog's: a credit's worth in dollars, what each tier of engine spends a
 * minute and so costs an hour, how long the balance lasts on it, and the packs credits are sold
 * in. Buying a pack starts a checkout hosted elsewhere: the control plane returns its address and
 * the browser goes there. Where the control plane sells no credits (its health says so, or the
 * checkout answers 503), the tab says that in plain words and offers nothing to press.
 * @module
 */
import { useState } from 'react';
import { ArrowRight, Coins } from 'lucide-react';
import { ApiError, type Health, type Me } from '../../lib/api';
import { catalog, gpuLabel, hourlyUsd, minutesFor, packBonus, type CreditPack } from '../../lib/catalog';
import { creditCount, minutesText, percentage, usd } from '../../lib/format';
import { NOT_CONFIGURED } from '../messages';
import { ErrorNotice, Notice } from '../Notice';
import { Block, TabHeading } from './parts';

/** Props of {@link BillingTab}. */
interface BillingTabProps {
  /** The account, or `null` until it has loaded. */
  me: Me | null;
  /** What the control plane can do, or `null` until it answers. */
  health: Health | null;
  /** Starts a checkout for a pack and returns the page to send the browser to. */
  onCheckout: (pack: string) => Promise<string>;
}

/**
 * Renders the Billing tab.
 *
 * @param props The component's props.
 * @returns The tab's content.
 */
export function BillingTab({ me, health, onCheckout }: BillingTabProps) {
  const [buying, setBuying] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const refused = error instanceof ApiError && error.status === NOT_CONFIGURED;
  const paymentsOff = health?.billing === false || refused;
  const tiers = catalog.tiers.filter((tier) => health?.tiers?.includes(tier.id) ?? true);

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

  return (
    <>
      <TabHeading title="Billing">Your credits, what they are worth, and more of them.</TabHeading>
      <Block label="Balance">
        <p className="flex items-baseline gap-2.5">
          <Coins className="size-5 self-center text-fg" aria-hidden="true" />
          <span className="display text-4xl tabular-nums">{me === null ? '—' : creditCount(me.credits)}</span>
          <span className="text-sm text-muted">
            credits{me === null ? '' : `, worth ${usd(me.credits * catalog.credit_usd)}`}
          </span>
        </p>
      </Block>
      <Block label="What a credit is worth">
        <p className="text-sm leading-relaxed text-muted">
          1 credit is {usd(catalog.credit_usd)}. An engine spends credits each minute it runs, at the rate of the
          machine it runs on, and nothing once it has stopped.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="settings-table">
            <thead>
              <tr>
                <th scope="col">Machine</th>
                <th scope="col">A minute</th>
                <th scope="col">An hour</th>
                <th scope="col">Balance lasts</th>
              </tr>
            </thead>
            <tbody>
              {tiers.map((tier) => (
                <tr key={tier.id}>
                  <th scope="row">
                    {tier.name}
                    <span className="block text-xs font-normal text-faint">{gpuLabel(tier)}</span>
                  </th>
                  <td>
                    {creditCount(tier.credits_per_minute)} {tier.credits_per_minute === 1 ? 'credit' : 'credits'}
                  </td>
                  <td>{usd(hourlyUsd(tier))}</td>
                  <td>{me === null ? '—' : minutesText(minutesFor(me.credits, tier))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>
      <Block label="Buy credits">
        {paymentsOff ? (
          <div className="mb-4">
            <Notice tone="info" title="Payments are not switched on here yet." announce={refused}>
              Credits cannot be bought on this server for now. Your balance is unchanged, and the packs below are what
              will be offered.
            </Notice>
          </div>
        ) : null}
        <ul className="grid gap-3 sm:grid-cols-3">
          {catalog.credit_packs.map((pack) => {
            const bonus = packBonus(pack);
            return (
              <li key={pack.id}>
                <button
                  type="button"
                  className="choice h-full w-full flex-col items-start p-4 text-left focus-visible:rounded-2xl"
                  disabled={buying !== null || paymentsOff}
                  onClick={() => {
                    void buy(pack);
                  }}
                >
                  <span className="flex w-full items-center justify-between gap-2">
                    <span className="display text-2xl">{usd(pack.usd)}</span>
                    {bonus > 0 ? (
                      <span className="pill h-6 border-line-strong bg-ink-700 text-[0.6875rem] text-fg">
                        +{percentage(bonus)}
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1.5 text-sm font-medium">{creditCount(pack.credits)} credits</span>
                  {paymentsOff ? null : (
                    <span className="mt-3 flex items-center gap-1.5 text-sm font-semibold text-fg">
                      {buying === pack.id ? <span className="spinner" aria-hidden="true" /> : null}
                      {buying === pack.id ? 'Opening checkout…' : 'Buy'}
                      {buying === pack.id ? null : <ArrowRight className="size-4" aria-hidden="true" />}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
        {refused || error === null ? null : (
          <div className="mt-4">
            <ErrorNotice error={error} />
          </div>
        )}
      </Block>
    </>
  );
}
