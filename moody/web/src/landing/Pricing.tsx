/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's pricing: what a project spends credits on, every tier an engine runs on with
 * its hourly price, and the credit packs.
 *
 * No figure is written here. A tier's price per hour is its credits per minute times sixty times
 * what a credit is worth; a pack's bonus is what its credits exceed its price by at that worth.
 * What the page says is billed is what the catalog prices today, the engines' time; it promises no
 * price for the agent's own model or for generation, which the catalog does not list yet.
 * @module
 */
import { ArrowRight, Bot, Check, Coins, Gift, MonitorPlay } from 'lucide-react';
import {
  brand,
  catalog,
  IDLE_SHUTDOWN_MINUTES,
  cheapestTier,
  gpuLabel,
  hourlyUsd,
  minutesFor,
  packBonus,
  type CreditPack,
  type Tier,
} from '../lib/catalog';
import { creditCount, minutesText, percentage, price, usd } from '../lib/format';
import { SectionHeading } from './SectionHeading';
import { CREATE_HASH } from './studio';

/** What a project spends, in three parts. */
const PARTS = [
  {
    icon: Bot,
    title: 'The agent',
    body: 'One per project. It plans with you, builds the library, and opens the engines the work needs, asking before each decision that is yours.',
  },
  {
    icon: MonitorPlay,
    title: 'The engines',
    body: `Each runs on the tier you choose and spends credits by the minute while it runs. After ${IDLE_SHUTDOWN_MINUTES} idle minutes it shuts itself off.`,
  },
  {
    icon: Coins,
    title: 'Credits',
    body: `One balance for all of it, with no subscription. One credit is ${usd(catalog.credit_usd)}, and packs carry a bonus.`,
  },
] as const;

/**
 * Renders the pricing section.
 *
 * @returns The section.
 */
export function Pricing() {
  return (
    <section id="pricing" className="section" aria-labelledby="pricing-title">
      <div className="shell">
        <SectionHeading
          id="pricing-title"
          eyebrow="Pricing"
          title="Pay for the engine time you use"
          lede="An agent, the engines it opens, and one balance of credits. No subscription, and engines stop themselves when you step away."
        />

        <ul className="mt-12 grid gap-4 md:grid-cols-3">
          {PARTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="glass flex gap-4 p-5">
              <span className="icon-tile">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <span>
                <span className="block font-semibold tracking-tight">{title}</span>
                <span className="lede mt-1 block text-sm">{body}</span>
              </span>
            </li>
          ))}
        </ul>

        <h3 className="eyebrow mt-14">Engine tiers</h3>
        <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {catalog.tiers.map((tier) => (
            <li key={tier.id} className="flex">
              <TierCard tier={tier} />
            </li>
          ))}
        </ul>

        <div className="mt-5 grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,2fr)]">
          <div className="glass relative overflow-hidden border-line-strong p-7">
            <div className="relative">
              <span className="icon-tile">
                <Gift className="size-5" aria-hidden="true" />
              </span>
              <h3 className="display mt-5 text-3xl">
                {creditCount(catalog.signup_credits)} credits, free
              </h3>
              <p className="lede mt-3 text-[0.9375rem]">
                Every new {brand} account starts with them
                {cheapestTier === undefined
                  ? '.'
                  : `: ${minutesText(minutesFor(catalog.signup_credits, cheapestTier))} of engine time on ${cheapestTier.name} to try a real project before you spend anything.`}
              </p>
              <a href={CREATE_HASH} className="btn btn-primary mt-6">
                Start creating
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
            </div>
          </div>

          <div className="glass p-7">
            <h3 className="text-lg font-semibold tracking-tight">Credit packs</h3>
            <p className="mt-1 text-sm text-muted">
              Top up when you need more. Bigger packs carry a bonus, and each shows the engine time it buys.
            </p>
            <ul className="mt-5 grid gap-3 sm:grid-cols-3">
              {catalog.credit_packs.map((pack) => (
                <li key={pack.id}>
                  <PackCard pack={pack} />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Props of {@link TierCard}. */
interface TierCardProps {
  /** The tier the card prices. */
  tier: Tier;
}

/**
 * Renders one tier: its price per hour, its rate in credits, and its hardware.
 *
 * @param props The component's props.
 * @returns The card.
 */
function TierCard({ tier }: TierCardProps) {
  const specs = [gpuLabel(tier), `${tier.cpu} vCPU`, `${tier.memory_gb} GB memory`];
  return (
    <article className="glass glass-hover flex w-full flex-col p-6">
      <h3 className="eyebrow text-fg">{tier.name}</h3>
      <p className="mt-4 flex items-baseline gap-1.5">
        <span className="display text-[2.6rem]">{price(hourlyUsd(tier))}</span>
        <span className="text-sm text-muted">/ hour</span>
      </p>
      <p className="mt-1 text-sm text-faint">
        {creditCount(tier.credits_per_minute)} {tier.credits_per_minute === 1 ? 'credit' : 'credits'} per minute
      </p>
      <p className="lede mt-4 flex-1 text-sm">{tier.blurb}</p>
      <ul className="mt-5 grid gap-2.5 border-t border-line pt-5 text-sm">
        {specs.map((spec) => (
          <li key={spec} className="flex items-center gap-2.5">
            <Check className="size-4 flex-none text-fg" aria-hidden="true" />
            {spec}
          </li>
        ))}
      </ul>
    </article>
  );
}

/** How many tiers, cheapest first, a pack spells its session time out for. */
const PACK_EXAMPLE_TIERS = 2;

/** Props of {@link PackCard}. */
interface PackCardProps {
  /** The credit pack the card shows. */
  pack: CreditPack;
}

/**
 * Renders one credit pack: its credits, its price, its bonus when it has one, and the session time
 * it buys on the first tiers.
 *
 * @param props The component's props.
 * @returns The card.
 */
function PackCard({ pack }: PackCardProps) {
  const bonus = packBonus(pack);
  return (
    <div className="relative flex h-full flex-col rounded-lg border border-line bg-ink-950 p-5">
      {bonus > 0 ? (
        <span className="pill mono absolute top-3.5 right-3.5 h-6 border-fg bg-fg text-[0.6875rem] text-ink-950">
          +{percentage(bonus)}
        </span>
      ) : null}
      <p className="display text-3xl">{usd(pack.usd)}</p>
      <p className="mt-2 text-sm font-medium">{creditCount(pack.credits)} credits</p>
      <p className="mt-0.5 text-xs text-faint">{bonus > 0 ? 'Bonus credits included' : 'The plain rate'}</p>
      <ul className="mt-4 grid gap-1.5 border-t border-line pt-4 text-xs text-muted">
        {catalog.tiers.slice(0, PACK_EXAMPLE_TIERS).map((tier) => (
          <li key={tier.id} className="flex items-baseline justify-between gap-2">
            <span>{tier.name}</span>
            <span className="font-medium text-fg tabular-nums">{minutesText(minutesFor(pack.credits, tier))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
