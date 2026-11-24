/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The new-project dialog: pick one of the catalog's disciplines, then a format, then a name.
 *
 * The disciplines are `catalog.disciplines` in their order, Media first, each with its formats
 * written small. Picking one moves to the details: its formats as choices, a name, the first
 * message for the agent, and the engines the discipline works in. A link into the studio
 * (`/app/?discipline=…&format=…&prompt=…`) opens the dialog at the details with all three filled;
 * a format the catalog does not list for the discipline is kept as one more choice, since the
 * format is the project's own text.
 * @module
 */
import { useEffect, useId, useRef, useState, type SubmitEvent } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Dialog } from '../components/Dialog';
import type { NewProject } from '../lib/api';
import { catalog, findApp, findDiscipline, type Discipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { ErrorNotice } from './Notice';
import { DisciplineIcon } from './DisciplineIcon';
import { appStatusLabel } from './present';

/** What the dialog opens filled with, from a link into the studio. */
export interface ProjectDraft {
  /** The discipline's identifier. */
  discipline?: string;
  /** The format. */
  format?: string;
  /** The first message for the agent. */
  prompt?: string;
}

/** Props of {@link NewProjectDialog}. */
interface NewProjectDialogProps {
  /** Whether the dialog is shown. */
  open: boolean;
  /** What it opens filled with. */
  draft: ProjectDraft | null;
  /** Closes the dialog. */
  onClose: () => void;
  /** Creates the project and sends its first message, when there is one. */
  onCreate: (project: NewProject, prompt: string) => Promise<void>;
}

/**
 * Renders the dialog.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
export function NewProjectDialog({ open, draft, onClose, onCreate }: NewProjectDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={open} onClose={onClose} labelledBy={titleId} wide>
      <NewProjectForm titleId={titleId} draft={draft} onCreate={onCreate} />
    </Dialog>
  );
}

/** Props of {@link NewProjectForm}. */
interface NewProjectFormProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** What the form starts filled with. */
  draft: ProjectDraft | null;
  /** Creates the project. */
  onCreate: (project: NewProject, prompt: string) => Promise<void>;
}

/**
 * Renders the dialog's content: the disciplines, then the details of the one picked.
 *
 * @param props The component's props.
 * @returns The content.
 */
function NewProjectForm({ titleId, draft, onCreate }: NewProjectFormProps) {
  const [discipline, setDiscipline] = useState<Discipline | undefined>(() =>
    draft?.discipline === undefined ? undefined : findDiscipline(draft.discipline),
  );

  if (discipline === undefined) {
    return <DisciplinePicker titleId={titleId} onPick={setDiscipline} />;
  }
  return (
    <Details
      key={discipline.id}
      titleId={titleId}
      discipline={discipline}
      draft={draft?.discipline === discipline.id ? draft : { prompt: draft?.prompt }}
      onBack={() => {
        setDiscipline(undefined);
      }}
      onCreate={onCreate}
    />
  );
}

/** Props of {@link DisciplinePicker}. */
interface DisciplinePickerProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** Picks a discipline. */
  onPick: (discipline: Discipline) => void;
}

/**
 * Renders the grid of disciplines.
 *
 * @param props The component's props.
 * @returns The grid.
 */
function DisciplinePicker({ titleId, onPick }: DisciplinePickerProps) {
  return (
    <div>
      <h2 id={titleId} className="display pr-10 text-[1.6rem]">
        What are you making?
      </h2>
      <p className="lede mt-1.5 text-sm">Pick a discipline. The agent opens the engines it needs as the work goes.</p>
      <ul className="mt-5 grid grid-cols-1 gap-2.5 min-[30rem]:grid-cols-2 sm:grid-cols-3">
        {catalog.disciplines.map((candidate, index) => {
          return (
            <li key={candidate.id}>
              <button
                type="button"
                className="discipline-card h-full w-full"
                data-featured={index === 0}
                title={candidate.blurb}
                onClick={() => {
                  onPick(candidate);
                }}
              >
                <span className="flex items-center gap-2 font-semibold tracking-tight">
                  <DisciplineIcon
                    id={candidate.id}
                    className={cx('size-4', index === 0 ? 'text-ember-300' : 'text-muted')}
                  />
                  {candidate.name}
                </span>
                <span className="text-xs leading-snug text-faint">{candidate.formats.join(' · ')}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Props of {@link Details}. */
interface DetailsProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** The discipline picked. */
  discipline: Discipline;
  /** What the fields start filled with. */
  draft: ProjectDraft;
  /** Goes back to the disciplines. */
  onBack: () => void;
  /** Creates the project. */
  onCreate: (project: NewProject, prompt: string) => Promise<void>;
}

/**
 * Renders the details of a new project: its format, its name, and the first message.
 *
 * @param props The component's props.
 * @returns The form.
 */
function Details({ titleId, discipline, draft, onBack, onCreate }: DetailsProps) {
  const nameId = useId();
  const promptId = useId();
  const requested = draft.format?.trim() ?? '';
  const formats =
    requested === '' || discipline.formats.some((format) => format.toLowerCase() === requested.toLowerCase())
      ? discipline.formats
      : [...discipline.formats, requested];
  const [format, setFormat] = useState(
    formats.find((candidate) => candidate.toLowerCase() === requested.toLowerCase()) ?? formats[0] ?? '',
  );
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState(draft.prompt ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fallbackName = `Untitled ${format.toLowerCase() || discipline.name.toLowerCase()}`;
  const engines = discipline.engines.map(findApp).filter((app) => app !== undefined);
  const nameField = useRef<HTMLInputElement>(null);

  // The dialog focuses its first control as it opens, which is the way back; the name is where
  // typing starts, so it takes the focus once the dialog has settled.
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      nameField.current?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, []);

  /**
   * Creates the project.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onCreate({ name: name.trim() || fallbackName, discipline: discipline.id, format }, prompt.trim());
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <button type="button" className="btn btn-quiet btn-sm -ml-3 h-8 px-3 text-muted" onClick={onBack}>
        <ArrowLeft className="size-4" aria-hidden="true" />
        All disciplines
      </button>
      <h2 id={titleId} className="display mt-2 flex items-center gap-2.5 pr-10 text-[1.6rem]">
        <span className="icon-tile size-9 rounded-xl">
          <DisciplineIcon id={discipline.id} className="size-4" />
        </span>
        New {discipline.name.toLowerCase()} project
      </h2>
      <p className="lede mt-2 text-sm">{discipline.blurb}</p>

      <fieldset className="mt-6">
        <legend className="text-sm font-semibold text-muted">Format</legend>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {formats.map((candidate) => (
            <label key={candidate} className="chip h-9 px-3.5 text-sm">
              <input
                type="radio"
                name="format"
                className="sr-only"
                value={candidate}
                checked={candidate === format}
                onChange={() => {
                  setFormat(candidate);
                }}
              />
              {candidate}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="mt-6">
        <label htmlFor={nameId} className="text-sm font-semibold text-muted">
          Name
        </label>
        <input
          ref={nameField}
          id={nameId}
          className="field mt-2.5"
          placeholder={fallbackName}
          maxLength={120}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
      </div>

      <div className="mt-6">
        <label htmlFor={promptId} className="text-sm font-semibold text-muted">
          First message <span className="font-normal text-faint">(optional)</span>
        </label>
        <textarea
          id={promptId}
          className="field mt-2.5 h-auto min-h-[5.5rem] resize-y py-2.5 leading-relaxed"
          placeholder="The idea, a logline, or a script to start from. Leave it empty and the agent asks."
          rows={3}
          maxLength={20_000}
          value={prompt}
          onChange={(event) => {
            setPrompt(event.target.value);
          }}
        />
      </div>

      {engines.length === 0 ? null : (
        <p className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-faint">
          <span>Engines</span>
          {engines.map((app) => {
            const status = appStatusLabel(app);
            return (
              <span key={app.id} className="rounded-md border border-line px-1.5 py-0.5 text-muted">
                {app.name}
                {status === '' ? null : <span className="text-faint"> · {status}</span>}
              </span>
            );
          })}
        </p>
      )}

      {error === null ? null : (
        <div className="mt-5">
          <ErrorNotice error={error} />
        </div>
      )}

      <div className="mt-7 flex justify-end">
        <button type="submit" className="btn btn-primary" disabled={busy || format === ''}>
          {busy ? <span className="spinner" aria-hidden="true" /> : null}
          {prompt.trim() === '' ? 'Create project' : 'Create and send'}
          {busy ? null : <ArrowRight className="size-4" aria-hidden="true" />}
        </button>
      </div>
    </form>
  );
}
