/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard's launch panel: pick an app, a tier, and a region, and start a session.
 *
 * The three pickers are the catalog, so only an available app can be chosen and a tier shows the
 * price its credits come to. A tier the control plane's health check does not list as startable is
 * shown but cannot be chosen, and the selection starts on the first one that can.
 *
 * The panel advises (how long the balance lasts, a session limit about to be hit) but leaves the
 * verdict to the control plane, whose refusal it words inline: the balance and the limits are the
 * control plane's to judge, and a guess here could block a launch it would have allowed.
 * @module
 */
import { useId, useState, type SubmitEvent } from 'react';
import { Rocket } from 'lucide-react';
import { ArtImage } from '../components/Art';
import type { LaunchRequest, Me } from '../lib/api';
import {
  AUTO_REGION,
  catalog,
  gpuLabel,
  hourlyUsd,
  isAvailable,
  liveApps,
  minutesFor,
  type CatalogApp,
  type Tier,
} from '../lib/catalog';
import { creditCount, minutesText, price } from '../lib/format';
import { appImage } from '../lib/media';
import { ErrorNotice, Notice } from './Notice';

/** Props of {@link LaunchPanel}. */
interface LaunchPanelProps {
  /** The signed-in account, or `null` while it is not known. */
  me: Me | null;
  /** How many of the account's sessions are queued, starting, or running. */
  activeCount: number;
  /** The identifiers of the tiers that can be started right now, or `null` when every tier can. */
  openTiers: ReadonlySet<string> | null;
  /** Whether a control plane is connected; without one the panel cannot launch. */
  connected: boolean;
  /** Starts a session; rejects with what the control plane refused it for. */
  onLaunch: (request: LaunchRequest) => Promise<void>;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
}

/**
 * Renders the launch panel.
 *
 * @param props The component's props.
 * @returns The panel.
 */
export function LaunchPanel({ me, activeCount, openTiers, connected, onLaunch, onAddCredits }: LaunchPanelProps) {
  const titleId = useId();
  const regionId = useId();
  const [appId, setAppId] = useState(liveApps[0]?.id ?? '');
  const [pickedTierId, setPickedTierId] = useState<string | null>(null);
  const [region, setRegion] = useState(
    catalog.regions.find((candidate) => candidate.id === AUTO_REGION)?.id ?? catalog.regions[0]?.id ?? '',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const app = catalog.apps.find((candidate) => candidate.id === appId);
  const isOpen = (candidate: Tier): boolean => openTiers === null || openTiers.has(candidate.id);
  // The user's pick while it can be started, else the first tier that can: the list of open tiers
  // arrives after the form is on screen, and may not include the pick.
  const tier =
    catalog.tiers.find((candidate) => candidate.id === pickedTierId && isOpen(candidate)) ??
    catalog.tiers.find(isOpen);
  const ready = connected && app !== undefined && tier !== undefined && region !== '';

  /**
   * Starts the session the form describes and shows a refusal inline.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!ready) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onLaunch({ app: app.id, tier: tier.id, region });
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="glass p-5 sm:p-7" aria-labelledby={titleId}>
      <h2 id={titleId} className="display text-2xl">
        Launch a session
      </h2>
      <form
        className="mt-6 grid gap-7"
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <fieldset>
          <legend className="text-sm font-semibold text-muted">App</legend>
          <div className="mt-3 grid grid-cols-1 gap-3 min-[26rem]:grid-cols-2 xl:grid-cols-3">
            {catalog.apps.map((candidate) => (
              <AppChoice
                key={candidate.id}
                app={candidate}
                checked={candidate.id === appId}
                onChoose={() => {
                  setAppId(candidate.id);
                }}
              />
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-semibold text-muted">Tier</legend>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {catalog.tiers.map((candidate) => (
              <TierChoice
                key={candidate.id}
                tier={candidate}
                open={isOpen(candidate)}
                checked={candidate.id === tier?.id}
                onChoose={() => {
                  setPickedTierId(candidate.id);
                }}
              />
            ))}
          </div>
        </fieldset>

        <div className="grid items-end gap-4 sm:grid-cols-[minmax(0,14rem)_1fr]">
          <div>
            <label htmlFor={regionId} className="text-sm font-semibold text-muted">
              Region
            </label>
            <select
              id={regionId}
              className="field mt-3"
              value={region}
              onChange={(event) => {
                setRegion(event.target.value);
              }}
            >
              {catalog.regions.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary btn-lg h-[2.9rem] w-full" disabled={!ready || busy}>
            {busy ? <span className="spinner" aria-hidden="true" /> : <Rocket className="size-4" aria-hidden="true" />}
            {busy ? 'Reserving a workstation…' : `Launch ${app?.name ?? 'session'}`}
          </button>
        </div>

        {tier === undefined ? (
          <Notice tone="warn">No tier is switched on right now. Check back shortly.</Notice>
        ) : null}
        <Advice me={me} tier={tier} activeCount={activeCount} />
        <ErrorNotice error={error} onAddCredits={onAddCredits} />
      </form>
    </section>
  );
}

/** Props of {@link Advice}. */
interface AdviceProps {
  /** The signed-in account, or `null` while it is not known. */
  me: Me | null;
  /** The tier chosen. */
  tier: Tier | undefined;
  /** How many of the account's sessions are active. */
  activeCount: number;
}

/**
 * Renders what the panel can tell before launching: how long the balance lasts on the tier, or
 * that the balance or the session limit is likely to stop the launch.
 *
 * @param props The component's props.
 * @returns A line of advice, or nothing while the account is unknown.
 */
function Advice({ me, tier, activeCount }: AdviceProps) {
  if (me === null || tier === undefined) {
    return null;
  }
  if (activeCount >= me.max_sessions) {
    return (
      <Notice tone="warn">
        You have {activeCount} of {me.max_sessions} sessions in use. Stop one to make room for another.
      </Notice>
    );
  }
  const minutes = minutesFor(me.credits, tier);
  if (minutes < 1) {
    return (
      <Notice tone="warn">
        Your balance of {creditCount(me.credits)} credits does not cover a minute on {tier.name}.
      </Notice>
    );
  }
  return (
    <p className="text-sm text-muted">
      Your {creditCount(me.credits)} credits run {tier.name} for about{' '}
      <strong className="font-semibold text-fg">{minutesText(minutes)}</strong>. The stream opens in a new tab.
    </p>
  );
}

/** Props of {@link AppChoice}. */
interface AppChoiceProps {
  /** The app the option stands for. */
  app: CatalogApp;
  /** Whether it is the chosen app. */
  checked: boolean;
  /** Chooses it. */
  onChoose: () => void;
}

/**
 * Renders one app of the picker as a radio card with its art as a thumbnail; an app that is not
 * available yet is shown but cannot be chosen.
 *
 * @param props The component's props.
 * @returns The option.
 */
function AppChoice({ app, checked, onChoose }: AppChoiceProps) {
  const live = isAvailable(app);
  return (
    <label className="choice items-center gap-3 p-2.5" style={{ '--accent': app.accent }}>
      <input
        type="radio"
        name="app"
        value={app.id}
        className="sr-only"
        checked={checked}
        disabled={!live}
        onChange={onChoose}
      />
      <span className="art h-12 w-[4.5rem] flex-none rounded-lg">
        <ArtImage src={appImage(app.id)} width={1200} height={800} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm leading-tight font-semibold">{app.name}</span>
        <span className="mt-0.5 block truncate text-xs text-muted">
          {live ? app.version || 'Available' : 'Coming soon'}
        </span>
      </span>
    </label>
  );
}

/** Props of {@link TierChoice}. */
interface TierChoiceProps {
  /** The tier the option stands for. */
  tier: Tier;
  /** Whether the tier can be started right now; one that cannot is shown but cannot be chosen. */
  open: boolean;
  /** Whether it is the chosen tier. */
  checked: boolean;
  /** Chooses it. */
  onChoose: () => void;
}

/**
 * Renders one tier of the picker as a radio card with its hardware and its price per hour.
 *
 * @param props The component's props.
 * @returns The option.
 */
function TierChoice({ tier, open, checked, onChoose }: TierChoiceProps) {
  return (
    <label className="choice items-start gap-3 p-4">
      <input
        type="radio"
        name="tier"
        value={tier.id}
        className="sr-only"
        checked={checked}
        disabled={!open}
        onChange={onChoose}
      />
      <span className="choice-mark mt-0.5" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-3">
          <span className="font-semibold">{tier.name}</span>
          <span className="text-sm whitespace-nowrap">
            <span className="font-semibold">{price(hourlyUsd(tier))}</span>
            <span className="text-muted"> / hr</span>
          </span>
        </span>
        <span className="mt-1 block text-sm text-muted">{gpuLabel(tier)}</span>
        <span className="mt-0.5 block text-xs text-faint">
          {tier.cpu} vCPU · {tier.memory_gb} GB memory · {creditCount(tier.credits_per_minute)}{' '}
          {tier.credits_per_minute === 1 ? 'credit' : 'credits'} / min
        </span>
        {open ? null : <span className="mt-2 block text-xs font-semibold text-warn">Not switched on yet</span>}
      </span>
    </label>
  );
}
