/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's questions and answers, each a native disclosure.
 *
 * The answers say what the studio does today and stop there: what is live, what a number is, and
 * which engine needs a license of the user's own all come from the catalog, and nothing is priced
 * that the catalog does not price.
 * @module
 */
import { ChevronDown } from 'lucide-react';
import { brand, catalog, IDLE_SHUTDOWN_MINUTES, liveApps, ownLicenseLabel } from '../lib/catalog';
import { usd } from '../lib/format';
import { SectionHeading } from './SectionHeading';
import { appsWithStatus, listFormat, liveDisciplines } from './studio';

/** A question and its answer. */
interface Question {
  /** The question, as a visitor would ask it. */
  question: string;
  /** The answer. */
  answer: string;
}

/**
 * The questions, answered from the catalog.
 *
 * @returns The questions in the order they are shown.
 */
function questions(): Question[] {
  const engines = listFormat.format(liveApps.map((app) => app.name));
  const disciplines = listFormat.format(liveDisciplines.map((discipline) => discipline.name.toLowerCase()));
  const next = listFormat.format(appsWithStatus('next').map((app) => app.name));
  const team = appsWithStatus('team');
  const answers: Question[] = [
    {
      question: 'What can I make today?',
      answer:
        liveApps.length === 0
          ? 'The first engines are being set up, and this page will say so when they are ready.'
          : `Projects in ${disciplines}, worked in ${engines}.${
              next === '' ? '' : ` ${next} ${appsWithStatus('next').length === 1 ? 'is' : 'are'} coming next.`
            } You can start a project in any of the ${catalog.disciplines.length} disciplines, and the agent plans it with you while its engines are on the way.`,
    },
    {
      question: 'What is an engine?',
      answer: `A real piece of creative software, such as ${engines === '' ? 'a video editor or a 3D suite' : engines}, running on a cloud GPU and streamed to your browser tab. The agent works in it through the same commands its menus run, and you can take the controls whenever you like.`,
    },
    {
      question: 'Do I need a powerful computer or anything installed?',
      answer:
        'No. The engines run and render on cloud GPUs. Your computer plays the stream and sends your keyboard and mouse, which any machine that plays video comfortably can do, in a current version of Chrome, Edge, Firefox, or Safari.',
    },
    {
      question: 'Who makes the decisions?',
      answer:
        'You do. The agent asks at every decision that is yours, such as the story, the cast, the ending, or the cut, and offers choices you can pick or answer in your own words. You can watch it work and steer at any moment.',
    },
    {
      question: 'Where do my files live?',
      answer:
        'In the project. Every engine of a project opens the same project folder, so they work on the same files. Connect GitHub and the project also gets a repository, where the agent commits the script, the library, and the shot list as it works.',
    },
    {
      question: 'What happens when I walk away?',
      answer: `An engine that sees no activity for ${IDLE_SHUTDOWN_MINUTES} minutes shuts itself down and stops spending credits, so a forgotten tab does not run all night. The project and its files are kept.`,
    },
    {
      question: 'How is it billed?',
      answer: `With credits, and no subscription. One credit is ${usd(catalog.credit_usd)}, each engine spends a set number of credits per minute on the tier it runs on, and a new account starts with ${catalog.signup_credits} free credits. Pricing for the agent's own model and for generation will be listed here before either is billed.`,
    },
  ];
  for (const app of appsWithStatus('byol')) {
    const steps = app.license?.steps ?? [];
    answers.push({
      question: `What do I need for ${app.name}?`,
      answer: `${ownLicenseLabel(app)}. ${app.name} runs under its maker's license to you, not to ${brand}, so it opens once your account is linked${
        steps.length === 0 ? '.' : `: ${steps.map((step, index) => `(${index + 1}) ${step}`).join(' ')}`
      }`,
    });
  }
  for (const app of team) {
    answers.push({
      question: `Why is ${app.name} for teams only?`,
      answer: `${app.name} is licensed per person by its maker, so each person signs in with their own license inside the session. Offering it beyond the team needs the maker's agreement, so for now ${brand} opens it to the team's accounts only.`,
    });
  }
  return answers;
}

/**
 * Renders the FAQ section.
 *
 * @returns The section.
 */
export function Faq() {
  return (
    <section id="faq" className="section" aria-labelledby="faq-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:gap-16">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <SectionHeading
            id="faq-title"
            eyebrow="FAQ"
            title="Fair questions, straight answers"
            lede="The things people ask before they start their first project."
            start
          />
        </div>
        <div className="grid gap-3">
          {questions().map(({ question, answer }) => (
            <details key={question} className="faq glass group">
              <summary className="flex items-center justify-between gap-4 rounded-[inherit] p-5 text-[1.0625rem] font-semibold tracking-tight sm:px-6">
                {question}
                <ChevronDown
                  className="faq-chevron size-5 flex-none text-faint transition-transform duration-200"
                  aria-hidden="true"
                />
              </summary>
              <p className="lede px-5 pb-6 text-[0.9375rem] sm:px-6">{answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
