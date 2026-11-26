/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The studio's left sidebar: the brand, "New project", the **Create** shortcuts, the **Pinned** and
 * **Recent** projects, and the account with its credits and the limits of its turns at the foot.
 *
 * Create lists the catalog's shortcuts (`catalog.shortcuts`): a kind of work by its everyday name.
 * Each opens the new-project dialog on its discipline, and on its format where it names one, so a
 * project of that kind is two clicks away and the first of them makes nothing. A shortcut the
 * catalog does not offer yet is drawn dimmed with "Soon": it starts nothing, and where the catalog
 * says what to expect of it, choosing it shows that (`ComingDialog.tsx`).
 *
 * Each project row has a menu to pin, rename, or delete it; a rename is edited in the row itself,
 * and a delete asks first. The search is a quiet icon at the end of the Recent heading's row (the
 * Pinned one's, for an account whose projects are all pinned). Pressing it opens the field in that
 * row, where it narrows both lists by name, discipline, or format; Escape, its close button, or
 * leaving it empty puts the heading back.
 *
 * Folded, the sidebar is a rail: unfolding, a new project, the search (which unfolds it), the
 * shortcuts as icons, and the account. On a narrow screen it is the Projects tab, where the
 * shortcuts sit in columns.
 * @module
 */
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import {
  Coins,
  Ellipsis,
  Gauge,
  KeyRound,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { BrandMark } from '../components/Brand';
import { MoodyLogo } from '../components/Moody';
import { Dialog } from '../components/Dialog';
import type { Me, Project } from '../lib/api';
import { brand, catalog, shortcutDiscipline, type Shortcut } from '../lib/catalog';
import { cx } from '../lib/cx';
import { creditCount } from '../lib/format';
import { useNow } from './hooks';
import { Menu } from './Menu';
import { ErrorNotice } from './Notice';
import { DisciplineIcon, ShortcutIcon } from '../components/DisciplineIcon';
import { ComingDialog } from './ComingDialog';
import type { ProjectDraft } from './NewProjectDialog';
import { ago, disciplineName, limitText } from './present';
import type { Projects } from './useAccount';

/** Props of {@link Sidebar}. */
interface SidebarProps {
  /** The account's projects and the actions over them. */
  projects: Projects;
  /** The open project, or `null`. */
  selectedId: string | null;
  /** Opens a project. */
  onSelect: (id: string) => void;
  /** Opens the new-project dialog, on what a shortcut starts where one was chosen. */
  onNewProject: (preset?: ProjectDraft) => void;
  /** Whether the sidebar is folded to a rail. */
  collapsed: boolean;
  /** Folds or unfolds it. */
  onCollapse: (collapsed: boolean) => void;
  /** The signed-in account, or `null` while it is not known. */
  me: Me | null;
  /** The account's email address. */
  email: string;
  /** Whether the studio is showing the demo's sample data, which the header says. */
  demo: boolean;
  /** Opens the credits dialog. */
  onAddCredits: () => void;
  /** Opens the Connect Claude dialog. */
  onConnectClaude: () => void;
  /** Opens the dialog of a turn's limits. */
  onLimits: () => void;
  /** Signs the person out. */
  onSignOut: () => void;
  /** Whether the region is hidden behind another tab on a narrow screen. */
  mobileHidden: boolean;
}

/**
 * Renders the sidebar.
 *
 * @param props The component's props.
 * @returns The sidebar.
 */
export function Sidebar(props: SidebarProps) {
  const { projects, collapsed, onCollapse, onNewProject, mobileHidden, demo } = props;
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [deleting, setDeleting] = useState<Project | null>(null);
  const [coming, setComing] = useState<Shortcut | null>(null);
  const ready = projects.status === 'ready';
  const search: ProjectSearch = {
    open: searching,
    query,
    onOpen: () => {
      setSearching(true);
    },
    onQuery: setQuery,
    onClose: () => {
      setSearching(false);
      setQuery('');
    },
  };

  /**
   * Opens the new-project dialog on what a shortcut starts, or, for one that starts nothing yet,
   * what to expect of it.
   *
   * @param shortcut The shortcut chosen.
   */
  const choose = (shortcut: Shortcut): void => {
    const discipline = shortcutDiscipline(shortcut);
    if (discipline === undefined) {
      setComing(shortcut);
    } else {
      onNewProject({ discipline: discipline.id, format: shortcut.format });
    }
  };
  const comingDialog = (
    <ComingDialog
      shortcut={coming}
      onClose={() => {
        setComing(null);
      }}
    />
  );

  const filtered = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length === 0) {
      return projects.list;
    }
    return projects.list.filter((project) => {
      const haystack = `${project.name} ${disciplineName(project.discipline)} ${project.format}`.toLowerCase();
      return words.every((word) => haystack.includes(word));
    });
  }, [projects.list, query]);
  const pinned = filtered.filter((project) => project.pinned);
  const recent = filtered.filter((project) => !project.pinned);

  if (collapsed) {
    return (
      <nav className="studio-side items-center gap-2 py-3" aria-label="Projects" data-mobile-hidden={mobileHidden}>
        <a href="/" aria-label={`${brand} home`} className="mb-1 grid size-9 place-items-center rounded-lg">
          <BrandMark className="w-7" />
        </a>
        <button
          type="button"
          className="icon-btn"
          aria-label="Show the sidebar"
          title="Show the sidebar"
          onClick={() => {
            onCollapse(false);
          }}
        >
          <PanelLeftOpen aria-hidden="true" />
        </button>
        <button
          type="button"
          className="icon-btn"
          aria-label="New project"
          title="New project"
          disabled={!ready}
          onClick={() => {
            onNewProject();
          }}
        >
          <Plus aria-hidden="true" />
        </button>
        {projects.list.length === 0 ? null : (
          <button
            type="button"
            className="icon-btn"
            aria-label="Search projects"
            title="Search projects"
            onClick={() => {
              setSearching(true);
              onCollapse(false);
            }}
          >
            <Search aria-hidden="true" />
          </button>
        )}
        <span className="h-px w-5 flex-none bg-line" aria-hidden="true" />
        <CreateList ready={ready} compact onChoose={choose} />
        <div className="mt-auto">
          <AccountMenu {...props} compact />
        </div>
        {comingDialog}
      </nav>
    );
  }

  return (
    <nav className="studio-side" aria-label="Projects" data-mobile-hidden={mobileHidden}>
      <div className="flex items-center gap-2 px-4 pt-4 pb-3">
        <a
          href="/"
          aria-label={`${brand} home`}
          className="flex items-center gap-2.5 rounded-lg font-semibold tracking-tight"
        >
          <MoodyLogo className="h-9" />
          <span
            className={cx(
              'mono rounded-sm border px-1.5 py-0.5 text-[0.625rem] font-semibold tracking-wider uppercase',
              demo ? 'border-line-strong bg-ink-700 text-fg' : 'border-line text-faint',
            )}
            title={demo ? 'Sample data: nothing here is a real account, and no request is sent' : undefined}
          >
            {demo ? 'Demo' : 'Studio'}
          </span>
        </a>
        <button
          type="button"
          className="icon-btn ml-auto max-lg:hidden"
          aria-label="Hide the sidebar"
          title="Hide the sidebar"
          onClick={() => {
            onCollapse(true);
          }}
        >
          <PanelLeftClose aria-hidden="true" />
        </button>
      </div>

      <div className="px-3">
        <button
          type="button"
          className="btn btn-ghost btn-sm w-full justify-start rounded-xl"
          disabled={!ready}
          title={ready ? undefined : 'Projects are not available on this server yet'}
          onClick={() => {
            onNewProject();
          }}
        >
          <Plus className="size-4 text-fg" aria-hidden="true" />
          New project
        </button>
      </div>

      <div className="thin-scroll mt-3 grid min-h-0 flex-1 grid-cols-1 content-start gap-4 overflow-y-auto px-3 pb-3">
        <CreateList ready={ready} compact={false} onChoose={choose} />
        <ProjectLists {...props} pinned={pinned} recent={recent} search={search} onDelete={setDeleting} />
      </div>

      <div className="border-t border-line p-2">
        <AccountMenu {...props} compact={false} />
      </div>

      <DeleteDialog
        project={deleting}
        onClose={() => {
          setDeleting(null);
        }}
        onDelete={projects.remove}
      />
      {comingDialog}
    </nav>
  );
}

/** Props of {@link CreateList}. */
interface CreateListProps {
  /** Whether a project can be started: the account's projects have loaded. */
  ready: boolean;
  /** Whether the sidebar is a rail, where a shortcut is its icon alone. */
  compact: boolean;
  /** Takes the shortcut the person chose. */
  onChoose: (shortcut: Shortcut) => void;
}

/**
 * Renders the Create list: the catalog's shortcuts, each a way into a new project of its kind.
 *
 * A shortcut that starts a project is a control once the account's projects have loaded. One that
 * starts nothing yet is dimmed and says "Soon"; it is a control only where the catalog has a
 * preview of it to show, which needs nothing loaded.
 *
 * @param props The component's props.
 * @returns The list, as rows under their heading or, in the rail, as icons.
 */
function CreateList({ ready, compact, onChoose }: CreateListProps) {
  const items = catalog.shortcuts.map((shortcut) => {
    const soon = shortcutDiscipline(shortcut) === undefined;
    const icon = <ShortcutIcon shortcut={shortcut} className="size-3" />;
    const choose = (): void => {
      onChoose(shortcut);
    };
    if (soon && (shortcut.preview ?? []).length === 0) {
      return (
        <li key={shortcut.id}>
          {compact ? (
            <span
              className="icon-btn"
              data-soon="true"
              role="img"
              aria-label={`${shortcut.label}: soon`}
              title={`${shortcut.label}: soon`}
            >
              {icon}
            </span>
          ) : (
            <span className="create-row" data-soon="true">
              {icon}
              <span className="min-w-0 flex-1 truncate">{shortcut.label}</span>
              <span className="text-[0.6875rem]">Soon</span>
            </span>
          )}
        </li>
      );
    }
    const name = soon ? `${shortcut.label}: soon` : `New project: ${shortcut.label}`;
    return (
      <li key={shortcut.id}>
        {compact ? (
          <button
            type="button"
            className="icon-btn"
            data-soon={soon ? true : undefined}
            aria-label={name}
            title={name}
            disabled={!soon && !ready}
            onClick={choose}
          >
            {icon}
          </button>
        ) : (
          <button
            type="button"
            className="create-row"
            data-soon={soon ? true : undefined}
            disabled={!soon && !ready}
            onClick={choose}
          >
            {icon}
            <span className="min-w-0 flex-1 truncate">{shortcut.label}</span>
            {soon ? <span className="text-[0.6875rem]">Soon</span> : null}
          </button>
        )}
      </li>
    );
  });
  if (compact) {
    return (
      <ul
        className="flex min-h-0 flex-col items-center gap-1 overflow-y-auto [scrollbar-width:none]"
        aria-label="Create"
      >
        {items}
      </ul>
    );
  }
  return (
    <section aria-label="Create">
      <h2 className="section-label section-head">Create</h2>
      <ul className="grid grid-cols-2 gap-x-2 gap-y-0.5 sm:grid-cols-4 lg:grid-cols-1">{items}</ul>
    </section>
  );
}

/** The search over the projects: whether its field is open, what it holds, and how both change. */
interface ProjectSearch {
  /** Whether the field is shown, in place of the heading whose row holds the search. */
  open: boolean;
  /** What the field holds. */
  query: string;
  /** Opens the field. */
  onOpen: () => void;
  /** Replaces what the field holds. */
  onQuery: (query: string) => void;
  /** Closes the field and empties it, which puts the heading back. */
  onClose: () => void;
}

/** Props of {@link ListHead}. */
interface ListHeadProps {
  /** The list's name. */
  label: string;
  /** The search, for the list whose heading's row holds it. */
  search?: ProjectSearch | undefined;
}

/**
 * Renders the heading of a list of projects, and the search in its row for the list that holds it:
 * a quiet icon at the row's end, or, once pressed, the field in the heading's place.
 *
 * Closing the field from inside it (Escape, or its close button) hands the focus back to the icon,
 * so the keyboard stays where it was; leaving the field empty closes it without moving the focus.
 *
 * @param props The component's props.
 * @returns The heading's row.
 */
function ListHead({ label, search }: ListHeadProps) {
  const opener = useRef<HTMLButtonElement>(null);
  const handBack = useRef(false);
  const open = search?.open === true;
  useEffect(() => {
    if (!open && handBack.current) {
      handBack.current = false;
      opener.current?.focus();
    }
  }, [open]);

  if (search === undefined) {
    return <h2 className="section-label section-head">{label}</h2>;
  }
  if (!search.open) {
    return (
      <div className="section-head">
        <h2 className="section-label min-w-0 flex-1">{label}</h2>
        <button
          ref={opener}
          type="button"
          className="icon-btn icon-btn-sm -mr-1.5 text-faint"
          aria-label="Search projects"
          title="Search projects"
          onClick={search.onOpen}
        >
          <Search aria-hidden="true" />
        </button>
      </div>
    );
  }
  /** Closes the search and hands the focus back to the icon that opened it. */
  const close = (): void => {
    handBack.current = true;
    search.onClose();
  };
  return (
    <div className="relative mb-0.5 h-7" role="search">
      <Search
        className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint"
        aria-hidden="true"
      />
      <input
        type="search"
        className="field field-sm h-7 px-8 max-lg:text-base"
        aria-label="Search projects"
        placeholder="Search projects"
        autoFocus
        value={search.query}
        onChange={(event) => {
          search.onQuery(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault();
            close();
          }
        }}
        onBlur={() => {
          if (search.query.trim() === '') {
            search.onClose();
          }
        }}
      />
      <button
        type="button"
        className="icon-btn icon-btn-sm absolute top-1/2 right-0.5 size-6 -translate-y-1/2"
        aria-label="Close the search"
        onClick={close}
      >
        <X aria-hidden="true" />
      </button>
    </div>
  );
}

/** Props of {@link ProjectLists}. */
interface ProjectListsProps extends SidebarProps {
  /** The pinned projects that match the search. */
  pinned: Project[];
  /** The other projects that match the search. */
  recent: Project[];
  /** The search over both lists. */
  search: ProjectSearch;
  /** Asks to delete a project. */
  onDelete: (project: Project) => void;
}

/**
 * Renders the project lists, or what stands in for them before they can be shown.
 *
 * @param props The component's props.
 * @returns The lists.
 */
function ProjectLists({ projects, pinned, recent, search, selectedId, onSelect, onDelete }: ProjectListsProps) {
  const now = useNow(true, 60_000);
  switch (projects.status) {
    case 'loading':
      return (
        <div className="grid grid-cols-1 gap-1.5 pt-1" aria-label="Loading projects">
          {[0, 1, 2, 3].map((row) => (
            <div key={row} className="h-8 animate-pulse rounded-lg bg-white/[0.04]" />
          ))}
        </div>
      );
    case 'missing':
      return (
        <p className="px-2 pt-2 text-sm leading-relaxed text-faint">
          Projects arrive with the studio&rsquo;s backend, which this server does not run yet.{' '}
          <a className="link" href="/app/?demo">
            See the demo
          </a>
          .
        </p>
      );
    case 'offline':
      return (
        <p className="px-2 pt-2 text-sm leading-relaxed text-faint">
          Your projects appear here once the control plane is connected.
        </p>
      );
    case 'failed':
      return (
        <div className="pt-1">
          <ErrorNotice error={projects.error} />
        </div>
      );
    case 'ready':
      break;
  }

  if (projects.list.length === 0) {
    return (
      <p className="px-2 pt-2 text-sm leading-relaxed text-faint">
        No projects yet. Start one and the agent opens the conversation.
      </p>
    );
  }
  const row = (project: Project) => (
    <ProjectRow
      key={project.id}
      project={project}
      active={project.id === selectedId}
      now={now}
      onSelect={onSelect}
      onDelete={onDelete}
      onRename={async (name) => {
        await projects.update(project.id, { name });
      }}
      onPin={async (pin) => {
        await projects.update(project.id, { pinned: pin });
      }}
    />
  );
  // The search's row is the Recent heading's, which is there whenever a project is not pinned.
  const recents = projects.list.some((project) => !project.pinned);
  const none =
    search.query.trim() !== '' && pinned.length === 0 && recent.length === 0 ? (
      <p className="px-2 pt-1.5 text-sm text-faint">No project matches.</p>
    ) : null;
  return (
    <div className="grid grid-cols-1 gap-4">
      {pinned.length === 0 && recents ? null : (
        <section aria-label="Pinned">
          <ListHead label="Pinned" search={recents ? undefined : search} />
          {recents ? null : none}
          <ul className="grid grid-cols-1 gap-0.5">{pinned.map(row)}</ul>
        </section>
      )}
      {recents ? (
        <section aria-label="Recent">
          <ListHead label="Recent" search={search} />
          {none}
          <ul className="grid grid-cols-1 gap-0.5">{recent.map(row)}</ul>
        </section>
      ) : null}
    </div>
  );
}

/** Props of {@link ProjectRow}. */
interface ProjectRowProps {
  /** The project. */
  project: Project;
  /** Whether it is the open one. */
  active: boolean;
  /** The current time, for how long ago it changed. */
  now: number;
  /** Opens it. */
  onSelect: (id: string) => void;
  /** Asks to delete it. */
  onDelete: (project: Project) => void;
  /** Renames it. */
  onRename: (name: string) => Promise<void>;
  /** Pins or unpins it. */
  onPin: (pinned: boolean) => Promise<void>;
}

/**
 * Renders one project of the list, with its menu, or the field that renames it.
 *
 * @param props The component's props.
 * @returns The list item.
 */
function ProjectRow({ project, active, now, onSelect, onDelete, onRename, onPin }: ProjectRowProps) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(project.name);
  const [error, setError] = useState<unknown>(null);
  const settled = useRef(false);

  /** Saves the rename, once, whether Enter or leaving the field asked for it. */
  async function save(): Promise<void> {
    if (settled.current) {
      return;
    }
    settled.current = true;
    setRenaming(false);
    const name = draft.trim();
    if (name === '' || name === project.name) {
      return;
    }
    try {
      await onRename(name);
    } catch (failure) {
      setError(failure);
    }
  }

  /**
   * Saves on Enter and cancels on Escape.
   *
   * @param event The key press in the field.
   */
  function onKey(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      void save();
    } else if (event.key === 'Escape') {
      settled.current = true;
      setRenaming(false);
    }
  }

  return (
    <li>
      <div className="project-row" data-active={active}>
        <DisciplineIcon
          id={project.discipline}
          className={cx('size-3', active ? 'text-fg' : 'text-faint')}
        />
        {renaming ? (
          <input
            className="field field-sm h-7 min-w-0 flex-1 px-2"
            aria-label="Project name"
            maxLength={120}
            value={draft}
            autoFocus
            onChange={(event) => {
              setDraft(event.target.value);
            }}
            onKeyDown={onKey}
            onBlur={() => {
              void save();
            }}
          />
        ) : (
          <button
            type="button"
            className="min-w-0 flex-1 truncate text-left after:absolute after:inset-0 after:content-['']"
            aria-current={active ? 'page' : undefined}
            title={`${project.name} · ${disciplineName(project.discipline)} · ${project.format}`}
            onClick={() => {
              onSelect(project.id);
            }}
          >
            {project.name}
          </button>
        )}
        <span className="row-end">
          {renaming ? null : (
            <span className="row-time text-[0.6875rem] text-faint tabular-nums">{ago(project.updated_at, now)}</span>
          )}
          <span className="relative z-10">
            <Menu
              label={`Actions for ${project.name}`}
              trigger={<Ellipsis className="size-4" aria-hidden="true" />}
              triggerClassName="icon-btn icon-btn-sm row-menu"
              items={[
                {
                  label: project.pinned ? 'Unpin' : 'Pin',
                  icon: project.pinned ? <PinOff aria-hidden="true" /> : <Pin aria-hidden="true" />,
                  onSelect: () => {
                    onPin(!project.pinned).catch(setError);
                  },
                },
                {
                  label: 'Rename',
                  icon: <Pencil aria-hidden="true" />,
                  onSelect: () => {
                    setDraft(project.name);
                    settled.current = false;
                    setRenaming(true);
                  },
                },
                {
                  label: 'Delete',
                  icon: <Trash2 aria-hidden="true" />,
                  danger: true,
                  onSelect: () => {
                    onDelete(project);
                  },
                },
              ]}
            />
          </span>
        </span>
      </div>
      {error === null ? null : (
        <div className="mt-1 mb-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </li>
  );
}

/** Props of {@link DeleteDialog}. */
interface DeleteDialogProps {
  /** The project to delete, or `null` while none is asked about. */
  project: Project | null;
  /** Closes the dialog. */
  onClose: () => void;
  /** Deletes a project. */
  onDelete: (id: string) => Promise<void>;
}

/**
 * Renders the question that confirms deleting a project.
 *
 * @param props The component's props.
 * @returns The dialog.
 */
function DeleteDialog({ project, onClose, onDelete }: DeleteDialogProps) {
  const titleId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  /** Deletes the project and closes the dialog, or shows why it could not. */
  async function confirm(): Promise<void> {
    if (project === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onDelete(project.id);
      onClose();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={project !== null} onClose={onClose} labelledBy={titleId}>
      <h2 id={titleId} className="pr-10 text-xl font-semibold tracking-tight">
        Delete {project?.name}?
      </h2>
      <p className="lede mt-2 text-sm">Its conversation, plan, and library go with it. This cannot be undone.</p>
      {error === null ? null : (
        <div className="mt-4">
          <ErrorNotice error={error} />
        </div>
      )}
      <div className="mt-6 flex justify-end gap-2">
        <button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>
          Keep it
        </button>
        <button
          type="button"
          className="btn btn-danger btn-sm"
          disabled={busy}
          onClick={() => {
            void confirm();
          }}
        >
          {busy ? <span className="spinner" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
          Delete project
        </button>
      </div>
    </Dialog>
  );
}

/** Props of {@link AccountMenu}. */
interface AccountMenuProps extends SidebarProps {
  /** Whether the sidebar is a rail, where the account shows only its initial. */
  compact: boolean;
}

/**
 * Renders the account button at the sidebar's foot and the menu it opens: the balance, adding
 * credits, a turn's limits where the control plane has them (with the two that apply beside the
 * item), Connect Claude, and signing out.
 *
 * @param props The component's props.
 * @returns The account button and its menu.
 */
function AccountMenu({ me, email, compact, onAddCredits, onConnectClaude, onLimits, onSignOut }: AccountMenuProps) {
  const limits = me?.limits;
  const initial = email.charAt(0) || '?';
  const balance = me === null ? '—' : creditCount(me.credits);
  const avatar = (
    <span className="grid size-8 flex-none place-items-center rounded-md border border-line-strong bg-ink-700 text-[0.8125rem] font-semibold uppercase">
      {initial}
    </span>
  );
  return (
    <Menu
      label="Account"
      placement="above-start"
      menuClassName="w-64"
      triggerClassName={cx(
        'flex items-center gap-2.5 rounded-xl text-left transition-colors hover:bg-white/[0.05]',
        compact ? 'p-1' : 'w-full p-2',
      )}
      trigger={
        compact ? (
          avatar
        ) : (
          <>
            {avatar}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium" title={email}>
                {email || 'Your account'}
              </span>
              <span className="flex items-center gap-1 text-xs text-muted">
                <Coins className="size-3 text-fg" aria-hidden="true" />
                <span className="tabular-nums">{balance}</span> credits
              </span>
            </span>
          </>
        )
      }
      items={
        <>
          <div className="px-3 pt-2 pb-2.5">
            <p className="text-xs text-faint">Signed in as</p>
            <p className="truncate text-sm font-medium" title={email}>
              {email}
            </p>
          </div>
          <div className="mx-1 mb-1 flex items-center justify-between gap-2 rounded-xl border border-line bg-white/[0.03] py-2 pr-2 pl-3">
            <span className="flex items-center gap-2 text-sm">
              <Coins className="size-4 text-fg" aria-hidden="true" />
              <span className="font-semibold tabular-nums">{balance}</span>
              <span className="text-muted">credits</span>
            </span>
            <button
              type="button"
              role="menuitem"
              className="btn btn-primary btn-sm h-7 px-2.5 text-xs"
              onClick={onAddCredits}
            >
              <Plus className="size-3.5" aria-hidden="true" />
              Add
            </button>
          </div>
          {limits === undefined ? null : (
            <button type="button" role="menuitem" className="menu-item" onClick={onLimits}>
              <Gauge aria-hidden="true" />
              <span className="flex-none">Turn limits</span>
              <span className="min-w-0 flex-1 truncate text-right text-xs text-faint tabular-nums">
                {limitText('budget', limits.turn_budget_usd)} · {limitText('steps', limits.turn_limit)}
              </span>
            </button>
          )}
          <button type="button" role="menuitem" className="menu-item" onClick={onConnectClaude}>
            <KeyRound aria-hidden="true" />
            Connect Claude
          </button>
          <button type="button" role="menuitem" className="menu-item" onClick={onSignOut}>
            <LogOut aria-hidden="true" />
            Sign out
          </button>
        </>
      }
    />
  );
}
