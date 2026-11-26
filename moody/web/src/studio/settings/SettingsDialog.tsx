/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Settings: the one place that holds what is the person's to set, opened from the account menu.
 *
 * It is a dialog that is a page of its own (`Dialog`'s `page`): the tabs down the side, the open
 * tab's content beside them, scrolling by itself. Below 768 pixels the tabs run across the top,
 * and on a phone the dialog fills the screen. The tabs and their order are `settingsTabs`
 * (`tabs.ts`): Profile, Billing, Agent, the catalog's own (Video editing), Connections, and API
 * keys, each left out where it would hold nothing real.
 *
 * The tabs are a tab list as assistive technology knows one: one stop for the Tab key, the arrow
 * keys, Home, and End move between them and open the one they land on, and the panel names the
 * tab it belongs to. The platform's modal dialog keeps the focus inside, closes on Escape, and
 * gives the focus back to what opened it. It opens with the focus on the open tab, which is marked
 * `autofocus` for it: left to itself the dialog takes the first thing that can hold the focus,
 * and on a narrow screen that is the row of tabs, which scrolls. The open tab is written to the
 * address as it changes.
 * @module
 */
import { useCallback, useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { Coins, Gauge, KeyRound, Plug, SlidersHorizontal, UserRound, type LucideIcon } from 'lucide-react';
import { Dialog } from '../../components/Dialog';
import type { ControlPlane, SettingValue } from '../../lib/api';
import type { EpicReturn, GitHubReturn } from '../EnvironmentPanel';
import { useMediaQuery } from '../hooks';
import { connected, type Account, type Epic, type GitHub } from '../useAccount';
import { LimitsForm } from './Agent';
import { ApiKeysTab } from './ApiKeys';
import { BillingTab } from './Billing';
import { CatalogSettings } from './CatalogSettings';
import { ConnectionsTab } from './Connections';
import { Block, TabHeading } from './parts';
import { ProfileTab } from './Profile';
import {
  AGENT,
  BILLING,
  CONNECTIONS,
  KEYS,
  PROFILE,
  settingsOn,
  settingsTabs,
  writeTabToAddress,
  type SettingsTab,
  type SettingsTarget,
} from './tabs';

/** The icon of each tab built here; a tab that comes from the catalog takes {@link CATALOG_ICON}. */
const ICONS: Readonly<Record<string, LucideIcon>> = {
  [PROFILE.id]: UserRound,
  [BILLING.id]: Coins,
  [AGENT.id]: Gauge,
  [CONNECTIONS.id]: Plug,
  [KEYS.id]: KeyRound,
};

/** The icon of a tab that holds the catalog's settings alone. */
const CATALOG_ICON: LucideIcon = SlidersHorizontal;

/** The media query under which the tabs run across the top, as `studio.css` lays them out. */
const TABS_ACROSS = '(max-width: 767.98px)';

/** What Settings shows and acts on. */
interface SettingsContent {
  /** What answers its requests, or `null` when no control plane is connected. */
  client: ControlPlane | null;
  /** The account and what the control plane can do. */
  account: Account;
  /** The email address the person signed in with. */
  email: string;
  /** The GitHub connection. */
  github: GitHub;
  /** The Epic connection. */
  epic: Epic;
  /** The outcome of a return from GitHub, shown once. */
  githubReturned: GitHubReturn;
  /** The outcome of a return from connecting Epic, shown once. */
  epicReturned: EpicReturn;
  /** Signs the person out. */
  onSignOut: () => void;
}

/** Props of {@link SettingsDialog}. */
interface SettingsDialogProps extends SettingsContent {
  /** What Settings is open on, or `null` while it is closed. */
  target: SettingsTarget | null;
  /** Opens another tab. */
  onTarget: (target: SettingsTarget) => void;
  /** Closes Settings. */
  onClose: () => void;
}

/**
 * Renders Settings.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function SettingsDialog({ target, onTarget, onClose, ...content }: SettingsDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={target !== null} onClose={onClose} labelledBy={titleId} page>
      {target === null ? null : <SettingsView titleId={titleId} target={target} onTarget={onTarget} {...content} />}
    </Dialog>
  );
}

/** Props of {@link SettingsView}. */
interface SettingsViewProps extends SettingsContent {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** What Settings is open on. */
  target: SettingsTarget;
  /** Opens another tab. */
  onTarget: (target: SettingsTarget) => void;
}

/**
 * Renders the tabs and the open tab's content.
 *
 * @param props The component's props.
 * @returns The dialog's content.
 */
function SettingsView({ titleId, target, onTarget, client, account, ...rest }: SettingsViewProps) {
  const { me } = account;
  const panelId = useId();
  const across = useMediaQuery(TABS_ACROSS);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  // Until the account has loaded, the tabs that depend on it are assumed, so a link to one opens on it.
  const tabs = settingsTabs({
    connected: client !== null,
    limits: me === null || me.limits !== undefined,
    settings: me === null || me.settings !== undefined,
  });
  const open = tabs.find((tab) => tab.id === target.tab) ?? PROFILE;

  useEffect(() => {
    writeTabToAddress(open.id);
    buttons.current.get(open.id)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [open.id]);

  /**
   * Moves between the tabs from the keyboard, opening the one landed on.
   *
   * @param event The key press.
   */
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const index = tabs.findIndex((tab) => tab.id === open.id);
    const moves: Readonly<Record<string, number>> = {
      ArrowDown: index + 1,
      ArrowRight: index + 1,
      ArrowUp: index - 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: tabs.length - 1,
    };
    const to = Object.hasOwn(moves, event.key) ? moves[event.key] : undefined;
    const next = to === undefined ? undefined : tabs[(to + tabs.length) % tabs.length];
    if (next === undefined) {
      return;
    }
    event.preventDefault();
    onTarget({ tab: next.id });
    buttons.current.get(next.id)?.focus();
  }

  return (
    <div className="settings">
      <div className="settings-side">
        <h2 id={titleId} className="settings-title">
          Settings
        </h2>
        <div
          className="settings-tabs"
          role="tablist"
          aria-labelledby={titleId}
          aria-orientation={across ? 'horizontal' : 'vertical'}
          onKeyDown={onKeyDown}
        >
          {tabs.map((tab) => {
            const Icon = ICONS[tab.id] ?? CATALOG_ICON;
            const selected = tab.id === open.id;
            return (
              <button
                key={tab.id}
                ref={(node) => {
                  if (node === null) {
                    buttons.current.delete(tab.id);
                  } else {
                    buttons.current.set(tab.id, node);
                    // The attribute itself, which the dialog reads as it opens; React's `autoFocus` writes none.
                    node.toggleAttribute('autofocus', selected);
                  }
                }}
                type="button"
                role="tab"
                id={`${panelId}-${tab.id}`}
                className="settings-tab"
                aria-selected={selected}
                aria-controls={panelId}
                tabIndex={selected ? 0 : -1}
                onClick={() => {
                  onTarget({ tab: tab.id });
                }}
              >
                <Icon aria-hidden="true" />
                {tab.name}
              </button>
            );
          })}
        </div>
      </div>
      <div
        key={open.id}
        id={panelId}
        role="tabpanel"
        aria-labelledby={`${panelId}-${open.id}`}
        className="settings-panel thin-scroll"
        data-tab={open.id}
      >
        <TabContent tab={open} target={target} onTarget={onTarget} client={client} account={account} {...rest} />
      </div>
    </div>
  );
}

/** Props of {@link TabContent}. */
interface TabContentProps extends SettingsContent {
  /** The open tab. */
  tab: SettingsTab;
  /** What Settings is open on. */
  target: SettingsTarget;
  /** Opens another tab. */
  onTarget: (target: SettingsTarget) => void;
}

/**
 * Renders the content of the open tab.
 *
 * @param props The component's props.
 * @returns The content.
 */
function TabContent({
  tab,
  target,
  onTarget,
  client,
  account,
  email,
  github,
  epic,
  githubReturned,
  epicReturned,
  onSignOut,
}: TabContentProps): ReactNode {
  const { me, health, change } = account;
  const listKeys = useCallback(() => connected(client).listApiKeys(), [client]);
  const createKey = useCallback((name: string) => connected(client).createApiKey(name), [client]);
  const revokeKey = useCallback((id: string) => connected(client).revokeApiKey(id), [client]);
  const checkout = useCallback((pack: string) => connected(client).checkout(pack), [client]);
  const settings = settingsOn(tab);
  const catalogSettings =
    settings.length === 0 ? null : (
      <CatalogSettings
        settings={settings}
        values={me?.settings}
        onChange={(id: string, value: SettingValue) => change({ settings: { [id]: value } })}
      />
    );

  switch (tab.id) {
    case PROFILE.id:
      return <ProfileTab me={me} email={email} connected={client !== null} onSave={change} onSignOut={onSignOut} />;
    case BILLING.id:
      return <BillingTab me={me} health={health} onCheckout={checkout} />;
    case AGENT.id:
      return (
        <>
          <TabHeading title={tab.name}>
            A turn is one message of yours and everything the agent does until it hands back to you. Each limit starts
            fresh with your next message.
          </TabHeading>
          <Block label="Limits for a turn">
            {me === null ? (
              <div className="h-40 animate-pulse rounded-xl bg-white/[0.04] sm:max-w-md" aria-label="Loading your limits" />
            ) : me.limits === undefined ? null : (
              <LimitsForm limits={me.limits} reached={target.limit ?? null} onSave={change} />
            )}
          </Block>
          {catalogSettings === null ? null : <Block>{catalogSettings}</Block>}
        </>
      );
    case CONNECTIONS.id:
      return (
        <ConnectionsTab
          github={github}
          epic={epic}
          health={health}
          githubReturned={githubReturned}
          epicReturned={epicReturned}
          onKeys={() => {
            onTarget({ tab: KEYS.id });
          }}
        />
      );
    case KEYS.id:
      return <ApiKeysTab onList={listKeys} onCreate={createKey} onRevoke={revokeKey} />;
    default:
      return (
        <>
          <TabHeading title={tab.name}>Each change is saved as you make it.</TabHeading>
          <Block>{catalogSettings}</Block>
        </>
      );
  }
}
