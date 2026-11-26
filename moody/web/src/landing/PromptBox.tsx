/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The hero's prompt box, the page's main way in: what a person wants to create, the discipline it
 * belongs to, and its format, sent to the app as a new project.
 *
 * The disciplines and their formats are the catalog's, the first discipline and its first format
 * chosen to begin with. Both are native radio groups drawn as chips, so the arrow keys move
 * through them and a screen reader announces each as a choice of one. Submitting opens the
 * project's address (`newProjectUrl` in `studio.ts`), where the app prefills a new project and has
 * a signed-out visitor sign up first. As in a chat composer, Enter sends and Shift+Enter breaks the
 * line.
 *
 * The box tells the page's wordmark what it feels (`lib/mood.ts`): surprised when the field takes
 * the focus, happy when the pointer reaches the button that sends.
 *
 * The navigation's call to action links to `#create`: the box answers that fragment by taking the
 * focus and clearing it, so the same link works again the next time it is followed.
 * @module
 */
import { useEffect, useId, useRef, useState, type KeyboardEvent, type SubmitEvent } from 'react';
import { ArrowRight } from 'lucide-react';
import { catalog, findDiscipline, isAvailable, type Discipline } from '../lib/catalog';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { midSentence } from '../lib/format';
import { replaceHash, useHash } from '../lib/hash';
import { express } from '../lib/mood';
import { ANIMATION } from '../lib/moody';
import { CREATE_HASH, enginesOf, listFormat, newProjectUrl } from './studio';

/**
 * The line under the chips: where the chosen discipline's work happens today.
 *
 * @param discipline The chosen discipline.
 * @returns The sentence.
 */
function readiness(discipline: Discipline): string {
  const live = enginesOf(discipline).filter(isAvailable);
  return live.length === 0
    ? `${discipline.name} engines are on the way. The agent can already plan the project with you.`
    : `The agent opens ${listFormat.format(live.map((app) => app.name))} on a cloud GPU and works in it with you.`;
}

/**
 * Renders the prompt box with its discipline and format choices.
 *
 * @returns The form.
 */
export function PromptBox() {
  const first = catalog.disciplines[0];
  const [disciplineId, setDisciplineId] = useState(first?.id ?? '');
  const discipline = findDiscipline(disciplineId) ?? first;
  const [format, setFormat] = useState(first?.formats[0] ?? '');
  const [prompt, setPrompt] = useState('');
  const field = useRef<HTMLTextAreaElement>(null);
  const hash = useHash();
  const labelId = useId();
  const hintId = useId();

  useEffect(() => {
    if (hash === CREATE_HASH) {
      // The link has already scrolled the box into view; the focus must not scroll it again.
      field.current?.focus({ preventScroll: true });
      replaceHash('');
    }
  }, [hash]);

  if (discipline === undefined) {
    return null;
  }

  const choose = (next: Discipline): void => {
    setDisciplineId(next.id);
    setFormat(next.formats[0] ?? '');
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>): void => {
    event.preventDefault();
    window.location.assign(newProjectUrl({ discipline: discipline.id, format, prompt }));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <form id="create" className="w-full" onSubmit={onSubmit} aria-labelledby={labelId}>
      <div className="prompt-box">
        <label id={labelId} htmlFor={`${labelId}-field`} className="block px-5 pt-4 text-sm font-semibold text-fg">
          What do you want to create?
        </label>
        <textarea
          ref={field}
          id={`${labelId}-field`}
          name="prompt"
          rows={3}
          value={prompt}
          placeholder={format === '' ? 'Describe it in a sentence or two…' : `Describe your ${midSentence(format)}…`}
          aria-describedby={hintId}
          className="prompt-field"
          onChange={(event) => {
            setPrompt(event.target.value);
          }}
          onKeyDown={onKeyDown}
          onFocus={() => {
            express(ANIMATION.surprised);
          }}
        />
        <div className="flex flex-col gap-3 border-t border-line px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
          <fieldset className="flex min-w-0 flex-wrap gap-1.5">
            <legend className="sr-only">Format</legend>
            {discipline.formats.map((option) => (
              <label key={option} className="chip chip-sm">
                <input
                  type="radio"
                  name="format"
                  value={option}
                  className="sr-only"
                  checked={option === format}
                  onChange={() => {
                    setFormat(option);
                  }}
                />
                {option}
              </label>
            ))}
          </fieldset>
          <button
            type="submit"
            className="btn btn-primary flex-none"
            onPointerEnter={() => {
              express(ANIMATION.happy);
            }}
          >
            Start creating
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <fieldset className="mt-4 min-w-0">
        <legend className="sr-only">Discipline</legend>
        <div className="chip-row">
          {catalog.disciplines.map((option) => (
            <label key={option.id} className="chip">
              <input
                type="radio"
                name="discipline"
                value={option.id}
                className="sr-only"
                checked={option.id === discipline.id}
                onChange={() => {
                  choose(option);
                }}
              />
              <DisciplineIcon id={option.id} className="size-3" />
              {option.name}
            </label>
          ))}
        </div>
      </fieldset>
      <p id={hintId} className="mt-3 text-sm text-muted" aria-live="polite">
        {readiness(discipline)}
      </p>
    </form>
  );
}
