/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The second take on the landing page: the same product, led by what people make with it.
 *
 * It keeps the first take's page around it (the navigation, the footer, the sign-up dialog), its
 * design, and its facts: every price, name, and number still comes from the catalog, and the
 * sections that state facts as they are (pricing, the steps, the questions, the closing call to
 * action) are the first take's own components given other words. What is new is the order and the
 * voice: a gallery of use cases first, benefits instead of features, and no account of the
 * machinery. Its sections carry the anchors the shared navigation links to.
 *
 * The words hold to what the first take already says the product does: nothing here is measured,
 * no app is offered before the catalog offers it, and the art is never called anyone's work.
 * @module
 */
import { AppWindow, History, MousePointerClick } from 'lucide-react';
import { catalog, IDLE_SHUTDOWN_MINUTES, liveApps, upcomingApps } from '../../lib/catalog';
import { usd } from '../../lib/format';
import { Faq, type Question } from '../Faq';
import { HowItWorks, type Point } from '../Features';
import { FinalCta } from '../Footer';
import { Pricing } from '../Pricing';
import { AppRow } from './AppRow';
import { Benefits } from './Benefits';
import { CreativeHero } from './CreativeHero';
import { Gallery } from './Gallery';
import { Partner } from './Partner';

const list = new Intl.ListFormat('en-US', { type: 'conjunction' });

/**
 * The three steps, naming the live app.
 *
 * @param app The name of the app a visitor opens.
 * @returns The steps in order.
 */
function steps(app: string): Point[] {
  return [
    {
      icon: MousePointerClick,
      title: 'Pick what you want to make',
      body: `Choose ${app} and how much power you want behind it. That is the whole setup.`,
    },
    {
      icon: AppWindow,
      title: 'It opens in a tab',
      body: `Your workstation starts and ${app} appears in a new browser tab. Your keyboard, your mouse, your files.`,
    },
    {
      icon: History,
      title: 'Come back to it whenever',
      body: 'Close the tab when you are done. Next time, your scene and your files are right where you left them.',
    },
  ];
}

/**
 * The questions a maker asks before starting, answered from the catalog.
 *
 * @param app The name of the app a visitor opens.
 * @returns The questions in the order they are shown.
 */
function questions(app: string): Question[] {
  const live = list.format(liveApps.map((entry) => [entry.name, entry.version].filter(Boolean).join(' ')));
  const coming = list.format(upcomingApps.map((entry) => entry.name));
  return [
    {
      question: 'Is my work saved?',
      answer: `Yes. Files in your workspace are kept and are there the next time you open ${app}. The scene you had open comes back too, even if you had not saved it. Saving into your workspace is still the good habit.`,
    },
    {
      question: 'Do I need a powerful computer?',
      answer: `No. ${app} runs on the cloud workstation. Your computer shows the picture and sends your keyboard and mouse, which any machine that plays video comfortably can do.`,
    },
    {
      question: 'Can I use my own files, add-ons, and settings?',
      answer: `Yes. Upload files into your workstation and they stay in your workspace. Your ${app} add-ons and preferences are kept as well, so it is your setup every time you open it.`,
    },
    {
      question: 'What happens if I walk away?',
      answer: `After ${IDLE_SHUTDOWN_MINUTES} minutes with no activity, your workstation shuts itself down and stops spending credits. It is there so a tab you forgot does not run all night. Your workspace files are kept.`,
    },
    {
      question: 'What can I make today?',
      answer:
        liveApps.length === 0
          ? 'The first apps are being set up, and this page will say so when they are ready.'
          : `${live} ${liveApps.length === 1 ? 'is' : 'are'} live today.${
              upcomingApps.length === 0 ? '' : ` ${coming} are on the way, and are not available yet.`
            }`,
    },
    {
      question: 'How does paying work?',
      answer: `You buy credits and spend them by the minute while your workstation is open. One credit is ${usd(catalog.credit_usd)}. A new account starts with ${catalog.signup_credits} credits, and there is no subscription.`,
    },
  ];
}

/**
 * Renders the sections of the second take, for the landing page to place between its navigation
 * and its footer.
 *
 * @returns The sections.
 */
export function CreativeLanding() {
  const app = liveApps[0]?.name ?? 'your app';
  return (
    <>
      <CreativeHero />
      <Gallery />
      <Benefits />
      <HowItWorks title="Three steps, then you are making" lede="No installer. No setup day." steps={steps(app)} />
      <AppRow />
      <Partner />
      <Pricing
        title="Pay for the hours you create"
        lede={`No subscription. You buy credits and spend them by the minute while your workstation is open. 1 credit is ${usd(catalog.credit_usd)}.`}
      />
      <Faq
        title="Good questions before you start"
        lede="The things people ask before they open their first scene."
        questions={questions(app)}
      />
      <FinalCta lead="The idea is ready." accent="So is the machine." body={`Open ${app} in a tab and start making.`} />
    </>
  );
}
