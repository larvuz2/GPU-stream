/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The dashboard page: the header over the sessions in flight, the launch panel, the recent
 * sessions, and the card that connects Claude.
 *
 * It is written against the {@link ControlPlane} interface and renders the same whatever answers
 * it. With none connected (no API address in the build) it shows one banner saying so and makes
 * no request; with the preview's it says the data is a sample.
 * @module
 */
import { useState } from 'react';
import { isActive, type ControlPlane } from '../lib/api';
import { brand } from '../lib/catalog';
import { ConnectClaude } from './ConnectClaude';
import { CreditsDialog } from './CreditsDialog';
import { Header } from './Header';
import { LaunchPanel } from './LaunchPanel';
import { Notice } from './Notice';
import { ActiveSessions, RecentSessions } from './Sessions';
import { useStudio } from './useStudio';

/** Props of {@link Dashboard}. */
interface DashboardProps {
  /** What answers the dashboard's requests, or `null` when no control plane is connected. */
  client: ControlPlane | null;
  /** The signed-in account's email address. */
  email: string;
  /** Whether the dashboard is showing the preview's sample data. */
  preview: boolean;
  /** Signs the user out. */
  onSignOut: () => void;
}

/**
 * Renders the dashboard.
 *
 * @param props The component's props.
 * @returns The page.
 */
export function Dashboard({ client, email, preview, onSignOut }: DashboardProps) {
  const studio = useStudio(client);
  const [addingCredits, setAddingCredits] = useState(false);
  const connected = client !== null;
  const cards = studio.sessions.filter((session) => isActive(session) || studio.watched.has(session.id));
  const recent = studio.sessions.filter((session) => !isActive(session) && !studio.watched.has(session.id));
  const openCredits = (): void => {
    setAddingCredits(true);
  };

  return (
    <div className="page">
      <div className="backdrop" aria-hidden="true" />
      <Header credits={studio.me?.credits ?? null} email={email} onAddCredits={openCredits} onSignOut={onSignOut} />
      <main className="shell grid gap-6 py-8 sm:py-10">
        <div>
          <h1 className="display text-3xl sm:text-4xl">Your studio</h1>
          <p className="mt-1.5 text-sm text-muted">Launch a workstation, or hand the keys to Claude.</p>
        </div>

        {preview ? (
          <Notice tone="info" title="Preview.">
            This is sample data for looking around. Nothing here is a real account, session, or key, and no request
            is sent.
          </Notice>
        ) : null}
        {connected ? null : (
          <Notice tone="warn" title="Control plane not connected.">
            {brand} cannot reach its backend from this build, so sessions, credits, and API keys are unavailable for
            now. You are signed in, and everything appears here once it is connected.
          </Notice>
        )}
        {studio.loadError === null ? null : (
          <Notice tone="bad" title="Could not refresh." announce>
            {studio.loadError}
          </Notice>
        )}

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <div className="grid min-w-0 gap-6">
            <ActiveSessions
              sessions={cards}
              loaded={studio.loaded}
              onStop={studio.stop}
              onLink={studio.link}
              onDismiss={studio.dismiss}
            />
            <LaunchPanel
              me={studio.me}
              activeCount={studio.sessions.filter(isActive).length}
              openTiers={studio.openTiers}
              connected={connected}
              onLaunch={studio.launch}
              onAddCredits={openCredits}
            />
            <RecentSessions sessions={recent} />
          </div>
          <div className="min-w-0">
            <ConnectClaude
              keys={studio.keys}
              connected={connected}
              onCreate={studio.createKey}
              onRevoke={studio.revokeKey}
            />
          </div>
        </div>
      </main>
      <CreditsDialog
        open={addingCredits}
        onClose={() => {
          setAddingCredits(false);
        }}
        onCheckout={studio.checkout}
      />
    </div>
  );
}
