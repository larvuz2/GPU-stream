/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's questions and answers, each a native disclosure.
 *
 * The answers say what the product does today and stop there; what a number is comes from the
 * catalog. The questions written here are the first take's; the second take of the landing page
 * renders the same section with its own (`creative/CreativeLanding.tsx`).
 * @module
 */
import { ChevronDown } from 'lucide-react';
import { brand, catalog, IDLE_SHUTDOWN_MINUTES, liveApps } from '../lib/catalog';
import { usd } from '../lib/format';
import { SectionHeading } from './SectionHeading';

/** A question and its answer. */
export interface Question {
  /** The question, as a visitor would ask it. */
  question: string;
  /** The answer. */
  answer: string;
}

/**
 * The first take's questions, written from the catalog.
 *
 * @returns The questions in the order they are shown.
 */
function technicalQuestions(): Question[] {
  const app = liveApps[0]?.name ?? 'the app';
  return [
    {
      question: 'What happens to my files?',
      answer:
        'Files in your workspace persist between sessions: save there, and they are back the next time you start one. Anything left elsewhere on the machine belongs to that session and goes away with it, so treat the workspace as your project folder.',
    },
    {
      question: 'What does idle shutdown mean?',
      answer: `If a session sees no activity for ${IDLE_SHUTDOWN_MINUTES} minutes, it shuts itself down and stops spending credits. It is there so a tab you forgot does not run all night. Your workspace files are kept.`,
    },
    {
      question: 'Which browsers work?',
      answer:
        'A current version of Chrome, Edge, Firefox, or Safari. Creative apps are built for a keyboard and a mouse, so a desktop or laptop is the comfortable way to use them.',
    },
    {
      question: 'Do I need a GPU on my own computer?',
      answer: `No. ${app} runs and renders on the cloud workstation. Your computer plays the stream and sends your input, which any machine that plays video comfortably can do.`,
    },
    {
      question: 'Can an AI agent use it?',
      answer: `Yes. ${brand} has an MCP endpoint. Create an API key, add the endpoint to Claude with one command, and Claude can start a session, run Python inside the ${app} you are watching, take screenshots to check its work, and stop the session.`,
    },
    {
      question: 'How is it billed?',
      answer: `With credits. One credit is ${usd(catalog.credit_usd)}, and each tier spends a set number of credits per minute. A new account starts with ${catalog.signup_credits} credits; after that you buy credit packs when you want more. There is no subscription.`,
    },
  ];
}

/** Props of {@link Faq}. */
interface FaqProps {
  /** The section's title. */
  title?: string;
  /** The sentence under the title. */
  lede?: string;
  /** The questions to answer, in order; the first take's when left out. */
  questions?: Question[];
}

/**
 * Renders the FAQ section.
 *
 * @param props The component's props.
 * @returns The section.
 */
export function Faq({
  title = 'Fair questions, straight answers',
  lede = 'The things people ask before they launch their first session.',
  questions = technicalQuestions(),
}: FaqProps) {
  return (
    <section id="faq" className="section" aria-labelledby="faq-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:gap-16">
        <div className="lg:sticky lg:top-[calc(7rem+var(--compare-bar))] lg:self-start">
          <SectionHeading id="faq-title" eyebrow="FAQ" title={title} lede={lede} start />
        </div>
        <div className="grid gap-3">
          {questions.map(({ question, answer }) => (
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
