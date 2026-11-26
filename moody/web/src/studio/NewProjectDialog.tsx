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
 * format is the project's own text. A shortcut of the sidebar's Create list opens it the same way,
 * at the details of its discipline, on its format where it names one.
 *
 * A discipline that asks its kind (`asksKind`) needs no format here: "Choose later" is its first
 * choice, and a project made that way opens on the card that asks. Its first message then waits in
 * the message box, since the kind is answered first.
 *
 * A Games project can also be imported from GitHub: "Import from GitHub" lists the repositories of
 * the control plane's GitHub App the person reaches, and the project is made already linked to
 * the one picked, so an Unreal engine started in it clones it. "Create new" is the project made
 * from nothing, as for every other discipline. Connecting GitHub from the dialog comes back to it
 * on the import (`source=github`).
 * @module
 */
import { useEffect, useId, useRef, useState, type SubmitEvent } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Dialog } from '../components/Dialog';
import type { NewProject } from '../lib/api';
import { asksKind, catalog, findApp, findDiscipline, type Discipline } from '../lib/catalog';
import { cx } from '../lib/cx';
import { midSentence } from '../lib/format';
import { ErrorNotice } from './Notice';
import { DisciplineIcon } from '../components/DisciplineIcon';
import { FormatLine } from '../components/FormatLine';
import { GitHubMark } from './Menu';
import { appStatusLabel } from './present';
import { RepoList } from './RepoList';
import type { GitHub } from './useAccount';

/** The disciplines whose projects can be imported from a GitHub repository. */
const IMPORTABLE = new Set(['games']);

/** Where a new project comes from. */
type Source = 'new' | 'github';

/** What the dialog opens filled with, from a link into the studio. */
export interface ProjectDraft {
  /** The discipline's identifier. */
  discipline?: string;
  /** The format. */
  format?: string;
  /** The first message for the agent. */
  prompt?: string;
  /** Where the project comes from: `github` opens the dialog on importing a repository. */
  source?: string;
}

/** Props of {@link NewProjectDialog}. */
interface NewProjectDialogProps {
  /** Whether the dialog is shown. */
  open: boolean;
  /** What it opens filled with. */
  draft: ProjectDraft | null;
  /** The GitHub connection, which a project imported from GitHub is made through. */
  github: GitHub;
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
export function NewProjectDialog({ open, draft, github, onClose, onCreate }: NewProjectDialogProps) {
  const titleId = useId();
  return (
    <Dialog open={open} onClose={onClose} labelledBy={titleId} wide>
      <NewProjectForm titleId={titleId} draft={draft} github={github} onCreate={onCreate} />
    </Dialog>
  );
}

/** Props of {@link NewProjectForm}. */
interface NewProjectFormProps {
  /** The `id` the dialog is titled by. */
  titleId: string;
  /** What the form starts filled with. */
  draft: ProjectDraft | null;
  /** The GitHub connection. */
  github: GitHub;
  /** Creates the project. */
  onCreate: (project: NewProject, prompt: string) => Promise<void>;
}

/**
 * Renders the dialog's content: the disciplines, then the details of the one picked.
 *
 * @param props The component's props.
 * @returns The content.
 */
function NewProjectForm({ titleId, draft, github, onCreate }: NewProjectFormProps) {
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
      github={github}
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
                    className={cx('size-6', index === 0 ? 'text-fg' : 'text-muted')}
                  />
                  {candidate.name}
                </span>
                <span className="text-xs leading-snug text-faint">
                  <FormatLine formats={candidate.formats} />
                </span>
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
  /** The GitHub connection. */
  github: GitHub;
  /** Goes back to the disciplines. */
  onBack: () => void;
  /** Creates the project. */
  onCreate: (project: NewProject, prompt: string) => Promise<void>;
}

/**
 * Renders the details of a new project: its format, where it comes from where it can be imported,
 * its name, and the first message.
 *
 * @param props The component's props.
 * @returns The form.
 */
function Details({ titleId, discipline, draft, github, onBack, onCreate }: DetailsProps) {
  const nameId = useId();
  const promptId = useId();
  const requested = draft.format?.trim() ?? '';
  const formats =
    requested === '' || discipline.formats.some((format) => format.toLowerCase() === requested.toLowerCase())
      ? discipline.formats
      : [...discipline.formats, requested];
  const asks = asksKind(discipline);
  const [format, setFormat] = useState(
    formats.find((candidate) => candidate.toLowerCase() === requested.toLowerCase()) ?? (asks ? '' : (formats[0] ?? '')),
  );
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState(draft.prompt ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const importable = IMPORTABLE.has(discipline.id);
  const [source, setSource] = useState<Source>(importable && draft.source === 'github' ? 'github' : 'new');
  const [repo, setRepo] = useState<string | null>(null);
  const importing = source === 'github';
  const fallbackName =
    importing && repo !== null
      ? (repo.split('/').pop() ?? repo)
      : `Untitled ${midSentence(format) || discipline.name.toLowerCase()}`;
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
      const made: NewProject = {
        name: name.trim() || fallbackName,
        discipline: discipline.id,
        ...(format === '' ? {} : { format }),
      };
      await onCreate(importing && repo !== null ? { ...made, github_repo: repo } : made, prompt.trim());
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
          <DisciplineIcon id={discipline.id} className="size-3" />
        </span>
        New {discipline.name.toLowerCase()} project
      </h2>
      <p className="lede mt-2 text-sm">{discipline.blurb}</p>

      <fieldset className="mt-6">
        <legend className="text-sm font-semibold text-muted">
          Format {asks ? <span className="font-normal text-faint">(optional)</span> : null}
        </legend>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {(asks ? ['', ...formats] : formats).map((candidate) => (
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
              {candidate === '' ? 'Choose later' : candidate}
            </label>
          ))}
        </div>
        {asks && format === '' ? (
          <p className="mt-2 text-xs text-faint">The conversation opens by asking, with a card to choose from.</p>
        ) : null}
      </fieldset>

      {importable ? (
        <fieldset className="mt-6">
          <legend className="text-sm font-semibold text-muted">Start from</legend>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {(['new', 'github'] as const).map((choice) => (
              <label key={choice} className="chip h-9 px-3.5 text-sm">
                <input
                  type="radio"
                  name="source"
                  className="sr-only"
                  value={choice}
                  checked={source === choice}
                  onChange={() => {
                    setSource(choice);
                  }}
                />
                {choice === 'new' ? 'Create new' : 'Import from GitHub'}
              </label>
            ))}
          </div>
          {importing ? (
            <div className="mt-3">
              <GitHubImport
                github={github}
                discipline={discipline.id}
                format={format}
                chosen={repo}
                onChoose={setRepo}
              />
            </div>
          ) : null}
        </fieldset>
      ) : null}

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
        <button
          type="submit"
          className="btn btn-primary"
          disabled={busy || (format === '' && !asks) || (importing && repo === null)}
        >
          {busy ? <span className="spinner" aria-hidden="true" /> : null}
          {prompt.trim() === '' || format === '' ? 'Create project' : 'Create and send'}
          {busy ? null : <ArrowRight className="size-4" aria-hidden="true" />}
        </button>
      </div>
    </form>
  );
}

/** Props of {@link GitHubImport}. */
interface GitHubImportProps {
  /** The GitHub connection. */
  github: GitHub;
  /** The discipline picked, which connecting comes back to. */
  discipline: string;
  /** The format picked, which connecting comes back to. */
  format: string;
  /** The repository picked, as `owner/name`, or `null`. */
  chosen: string | null;
  /** Picks a repository. */
  onChoose: (repo: string) => void;
}

/**
 * Renders the import of a repository: connecting GitHub first where it is not, then the GitHub
 * App's repositories to pick from, with the way to add one the app is not on.
 *
 * Connecting and installing leave the page for GitHub; they come back to the dialog, on this
 * discipline and format and on the import, through the link the studio opens the dialog from.
 *
 * @param props The component's props.
 * @returns The block.
 */
function GitHubImport({ github, discipline, format, chosen, onChoose }: GitHubImportProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const status = github.status;

  /**
   * Sends the browser to GitHub, coming back to this dialog on the import.
   *
   * @param go Connecting, or installing the app.
   */
  async function leave(go: (back: URL) => Promise<void>): Promise<void> {
    const back = new URL(window.location.href);
    back.searchParams.set('discipline', discipline);
    back.searchParams.set('format', format);
    back.searchParams.set('source', 'github');
    setBusy(true);
    setError(null);
    try {
      await go(back);
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  let body;
  if (github.availability === 'loading') {
    body = <div className="h-9 animate-pulse rounded-xl bg-white/[0.04]" aria-label="Loading GitHub" />;
  } else if (!status?.configured) {
    body = (
      <p className="text-sm text-faint">
        GitHub is not configured on this server yet. Create the project new, and link a repository once it is.
      </p>
    );
  } else if (!status.connected) {
    body = (
      <div>
        <p className="text-sm text-muted">Connect GitHub to pick your team&rsquo;s repository.</p>
        <button
          type="button"
          className="btn btn-ghost btn-sm mt-2.5"
          disabled={busy}
          onClick={() => {
            void leave(github.connect);
          }}
        >
          {busy ? <span className="spinner size-3.5" aria-hidden="true" /> : <GitHubMark className="size-4" />}
          Connect GitHub
        </button>
      </div>
    );
  } else {
    body = (
      <RepoList
        loadRepos={github.repos}
        busy={busy}
        chosen={chosen}
        onPick={(repo) => {
          onChoose(repo.full_name);
        }}
        onInstall={() => {
          void leave(github.install);
        }}
      />
    );
  }
  return (
    <div className="rounded-xl border border-line p-2.5">
      {body}
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
  );
}
