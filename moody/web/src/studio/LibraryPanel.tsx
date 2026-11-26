/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Library panel's body: the project's assets under a tab per section, everything the session
 * showed under Process, an asset's detail, and adding one.
 *
 * The tabs are "All", then the project's own sections (`useProject`, `sections`), then "Process".
 * A film has characters, environments, and props, a commercial products and shots, and the agent
 * adds sections as the work needs them, so nothing here names one: a tab appears when its section
 * does. Each asset is a card of its thumbnail, its `@tag`, and its name; its detail shows its
 * media, description, and metadata, and takes more media. A person adds an asset with a name, a
 * tag, a description, and optionally a first file, in an existing section or a new one.
 *
 * Process is no section and holds no assets: it is every picture, video, and sound the session
 * showed (what the agent's and its subagents' tools returned, previews, an engine's screenshots),
 * newest first, derived from the conversation (`processMedia`), so it is there without anyone
 * filing anything. A file there leads back to the entry of the conversation it appeared in. Its
 * address is the signed one the log returned, which expires: a file that fails to load asks for
 * the log to be read again (`refreshLinks`), is shown again once that reading brought another
 * address for it, and otherwise says it is no longer available.
 * @module
 */
import { useId, useMemo, useState, type SubmitEvent } from 'react';
import { ArrowLeft, CornerUpLeft, ImageOff, ImagePlus, Music, Play, Plus, Trash2, Upload } from 'lucide-react';
import type { Asset, NewAsset } from '../lib/api';
import { cx } from '../lib/cx';
import { shortDateTime } from '../lib/format';
import { MediaView } from './MediaView';
import { ErrorNotice, Notice } from './Notice';
import { normalizeTag } from './present';
import { Prose } from './Prose';
import type { ProcessEntry } from './transcript';
import type { ProjectData } from './useProject';

/** The file types an asset's media upload offers first; any file is still accepted. */
const MEDIA_ACCEPT = 'image/*,video/*,audio/*,.pdf,.txt,.md,.fountain';

/** Props of {@link LibraryBody}. */
interface LibraryBodyProps {
  /** The project's live data. */
  data: ProjectData;
  /** The asset whose detail is open, or `null` for the grid. */
  openAssetId: string | null;
  /** Opens an asset's detail, or goes back to the grid. */
  onOpenAsset: (id: string | null) => void;
  /** Whether the form that adds an asset is open. */
  adding: boolean;
  /** Opens or closes that form. */
  onAdding: (adding: boolean) => void;
  /** Whether this server can generate media; `false` adds a note, `null` says nothing. */
  generation: boolean | null;
  /** Every picture, video, and sound the session showed, newest first. */
  process: ProcessEntry[];
  /** Leads to where one of them appeared in the conversation. */
  onShowInConversation: (entry: ProcessEntry) => void;
}

/** The tab that shows every section, and the tab that shows what the session showed. */
const ALL_TAB = '\u0000all';
const PROCESS_TAB = '\u0000process';

/**
 * The image that stands for an asset in a grid.
 *
 * @param asset The asset.
 * @returns Its thumbnail, else its first image, else `null`.
 */
function thumbnailOf(asset: Asset): string | null {
  return asset.thumbnail_url ?? asset.media.find((media) => media.kind === 'image')?.url ?? null;
}

/**
 * Renders the library.
 *
 * @param props The component's props.
 * @returns The library's body.
 */
export function LibraryBody({
  data,
  openAssetId,
  onOpenAsset,
  adding,
  onAdding,
  generation,
  process,
  onShowInConversation,
}: LibraryBodyProps) {
  const [picked, setPicked] = useState(ALL_TAB);
  const panelId = useId();
  const assets = useMemo(() => data.library?.assets ?? [], [data.library]);
  const open = openAssetId === null ? undefined : assets.find((asset) => asset.id === openAssetId);

  if (data.libraryStatus === 'loading') {
    return (
      <div className="grid grid-cols-2 gap-2.5" aria-label="Loading the library">
        {[0, 1, 2, 3].map((tile) => (
          <div key={tile} className="aspect-[4/3] animate-pulse rounded-xl bg-white/[0.04]" />
        ))}
      </div>
    );
  }
  if (data.libraryStatus === 'missing' || data.libraryStatus === 'offline') {
    return <p className="text-sm text-faint">The library arrives with the studio&rsquo;s backend.</p>;
  }
  if (data.libraryStatus === 'failed') {
    return <p className="text-sm text-bad">Could not read the library.</p>;
  }
  if (open !== undefined) {
    return (
      <AssetDetail
        asset={open}
        onBack={() => {
          onOpenAsset(null);
        }}
        onUpload={(file) => data.uploadMedia(open.id, file)}
        onDelete={async () => {
          await data.deleteAsset(open.id);
          onOpenAsset(null);
        }}
      />
    );
  }

  // A section that is gone leaves its tab's viewer on All.
  const tab = picked === PROCESS_TAB || data.sections.includes(picked) ? picked : ALL_TAB;
  const shown = tab === ALL_TAB || tab === PROCESS_TAB ? null : tab;
  const groups = (shown === null ? data.sections : [shown]).map((section) => ({
    section,
    assets: assets.filter((asset) => asset.section === section),
  }));
  return (
    <div className="@container">
      {generation === false ? (
        <div className="mb-3">
          <Notice tone="info">
            Image and video generation is not configured here yet. Add references yourself meanwhile.
          </Notice>
        </div>
      ) : null}
      {adding ? (
        <AddAsset
          sections={data.sections}
          initialSection={shown ?? data.sections[0] ?? ''}
          onCancel={() => {
            onAdding(false);
          }}
          onCreate={async (asset, file) => {
            const made = await data.createAsset(asset, file);
            onAdding(false);
            onOpenAsset(made.id);
          }}
        />
      ) : null}
      <SectionTabs
        sections={data.sections}
        assets={assets}
        processCount={process.length}
        selected={tab}
        panelId={panelId}
        onSelect={setPicked}
        onAddSection={data.addSection}
      />
      {tab === PROCESS_TAB ? (
        <ProcessGrid
          id={panelId}
          entries={process}
          onShow={onShowInConversation}
          onStale={data.refreshLinks}
        />
      ) : data.sections.length === 0 ? (
        <p id={panelId} role="tabpanel" className="mt-3 text-sm text-faint">
          Nothing here yet. The agent fills the library as the work takes shape: characters, places, products, whatever
          the project needs.
        </p>
      ) : (
        <div id={panelId} role="tabpanel" className="mt-3 grid grid-cols-1 gap-4">
          {groups.map((group) => (
            <section key={group.section} aria-label={group.section}>
              {shown === null ? (
                <h4 className="mb-2 flex items-baseline gap-2 text-xs font-semibold text-muted">
                  {group.section}
                  <span className="font-normal text-faint tabular-nums">{group.assets.length}</span>
                </h4>
              ) : null}
              {group.assets.length === 0 ? (
                <p className="rounded-xl border border-dashed border-line px-3 py-3 text-xs text-faint">
                  Nothing in {group.section} yet.
                </p>
              ) : (
                <ul className="grid grid-cols-2 gap-2.5 @[30rem]:grid-cols-3">
                  {group.assets.map((asset) => (
                    <li key={asset.id}>
                      <AssetCard
                        asset={asset}
                        onOpen={() => {
                          onOpenAsset(asset.id);
                        }}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

/** Props of {@link SectionTabs}. */
interface SectionTabsProps {
  /** The sections. */
  sections: string[];
  /** Every asset, to count each section's. */
  assets: Asset[];
  /** How many files the session showed. */
  processCount: number;
  /** The tab shown: a section, {@link ALL_TAB}, or {@link PROCESS_TAB}. */
  selected: string;
  /** The element the tabs control. */
  panelId: string;
  /** Shows a tab. */
  onSelect: (tab: string) => void;
  /** Adds a section. */
  onAddSection: (name: string) => Promise<void>;
}

/**
 * Renders the library's tabs (All, the project's sections, Process) and the control that adds a
 * section.
 *
 * @param props The component's props.
 * @returns The tabs.
 */
function SectionTabs({
  sections,
  assets,
  processCount,
  selected,
  panelId,
  onSelect,
  onAddSection,
}: SectionTabsProps) {
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState<unknown>(null);

  /**
   * Adds the section named.
   *
   * @param event The form's submission.
   */
  async function add(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    try {
      await onAddSection(name);
      setName('');
      setNaming(false);
    } catch (failure) {
      setError(failure);
    }
  }

  const tabs = [
    { id: ALL_TAB, label: 'All', count: assets.length },
    ...sections.map((section) => ({
      id: section,
      label: section,
      count: assets.filter((asset) => asset.section === section).length,
    })),
    { id: PROCESS_TAB, label: 'Process', count: processCount },
  ];
  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        <div className="contents" role="tablist" aria-label="Library">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className="chip h-7 px-2.5 text-xs"
              aria-selected={selected === tab.id}
              aria-controls={panelId}
              onClick={() => {
                onSelect(tab.id);
              }}
            >
              {tab.label} <span className="chip-count">{tab.count}</span>
            </button>
          ))}
        </div>
        {naming ? (
          <form
            className="flex items-center gap-1"
            onSubmit={(event) => {
              void add(event);
            }}
          >
            <input
              className="field field-sm h-7 w-32 rounded-full px-2.5 text-xs"
              aria-label="New section"
              placeholder="Section name"
              maxLength={60}
              value={name}
              autoFocus
              onChange={(event) => {
                setName(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setNaming(false);
                }
              }}
            />
          </form>
        ) : (
          <button
            type="button"
            className="chip h-7 border-dashed px-2.5 text-xs"
            onClick={() => {
              setNaming(true);
            }}
          >
            <Plus className="size-3" aria-hidden="true" />
            Section
          </button>
        )}
      </div>
      {error === null ? null : (
        <div className="mt-2">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
  );
}

/** Props of {@link ProcessGrid}. */
interface ProcessGridProps {
  /** The identifier the tabs control. */
  id: string;
  /** The files, newest first. */
  entries: ProcessEntry[];
  /** Leads to where a file appeared in the conversation. */
  onShow: (entry: ProcessEntry) => void;
  /** Reports that a file failed to load, as an expired address does. */
  onStale: () => void;
}

/**
 * Renders what the session showed, newest first.
 *
 * @param props The component's props.
 * @returns The grid, or a line saying what will gather here.
 */
function ProcessGrid({ id, entries, onShow, onStale }: ProcessGridProps) {
  if (entries.length === 0) {
    return (
      <p id={id} role="tabpanel" className="mt-3 text-sm text-faint">
        Nothing yet. Every picture, video, and sound the agent shows while it works gathers here by itself, newest
        first.
      </p>
    );
  }
  return (
    <ul id={id} role="tabpanel" aria-label="Process" className="mt-3 grid grid-cols-2 gap-2.5 @[30rem]:grid-cols-3">
      {entries.map((entry) => (
        <li key={entry.key}>
          <ProcessTile
            entry={entry}
            onShow={() => {
              onShow(entry);
            }}
            onStale={onStale}
          />
        </li>
      ))}
    </ul>
  );
}

/** Props of {@link ProcessTile}. */
interface ProcessTileProps {
  /** The file, and where it appeared. */
  entry: ProcessEntry;
  /** Leads to where it appeared in the conversation. */
  onShow: () => void;
  /** Reports that it failed to load. */
  onStale: () => void;
}

/**
 * Renders one file the session showed, as a tile that leads back to the conversation.
 *
 * @param props The component's props.
 * @returns The tile.
 */
function ProcessTile({ entry, onShow, onStale }: ProcessTileProps) {
  const { media, caption } = entry;
  // The address that failed: the file is tried again once the log returns another for it.
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const fail = (): void => {
    setFailedUrl(media.url);
    onStale();
  };
  const gone = failedUrl === media.url;
  const name = media.name ?? caption;
  return (
    <button
      type="button"
      className="asset-card group w-full"
      aria-label={`Show ${name} in the conversation`}
      title="Show in the conversation"
      onClick={onShow}
    >
      <span className="asset-thumb block">
        {gone ? (
          <span className="absolute inset-0 grid place-items-center text-faint">
            <ImageOff className="size-5" aria-label="No longer available here" />
          </span>
        ) : media.kind === 'image' ? (
          <img src={media.url} alt="" loading="lazy" decoding="async" onError={fail} />
        ) : media.kind === 'video' ? (
          <video src={media.url} muted playsInline preload="metadata" onError={fail} />
        ) : (
          <>
            <span className="absolute inset-0 grid place-items-center text-lavender">
              <Music className="size-6" aria-hidden="true" />
            </span>
            <audio src={media.url} preload="metadata" className="hidden" onError={fail} />
          </>
        )}
        {media.kind === 'video' && !gone ? (
          <span className="preview-badge bottom-1.5 left-1.5">
            <Play className="size-3 fill-current" aria-hidden="true" />
          </span>
        ) : null}
        <span className="preview-badge top-1.5 right-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <CornerUpLeft className="size-3" aria-hidden="true" />
        </span>
      </span>
      <span className="block min-w-0 px-2.5 pt-2 pb-2.5">
        <span className="block truncate text-[0.8125rem] font-medium">{caption}</span>
        <span className="block truncate text-[0.6875rem] text-faint">
          {gone ? 'No longer available here' : (media.name ?? media.kind)}
        </span>
      </span>
    </button>
  );
}

/** Props of {@link AssetCard}. */
interface AssetCardProps {
  /** The asset. */
  asset: Asset;
  /** Opens its detail. */
  onOpen: () => void;
}

/**
 * Renders one asset of the grid.
 *
 * @param props The component's props.
 * @returns The card.
 */
function AssetCard({ asset, onOpen }: AssetCardProps) {
  const [failed, setFailed] = useState(false);
  const thumbnail = thumbnailOf(asset);
  return (
    <button type="button" className="asset-card w-full" onClick={onOpen}>
      <span className="asset-thumb block">
        {thumbnail === null || failed ? (
          <span className="absolute inset-0 grid place-items-center text-2xl font-semibold text-white/25 uppercase">
            {asset.name.charAt(0)}
          </span>
        ) : (
          <img
            src={thumbnail}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => {
              setFailed(true);
            }}
          />
        )}
      </span>
      <span className="block min-w-0 px-2.5 pt-2 pb-2.5">
        <span className="block truncate text-[0.8125rem] font-medium">{asset.name}</span>
        {asset.tag === null || asset.tag === '' ? (
          <span className="block text-[0.6875rem] text-faint">No tag</span>
        ) : (
          <span className="mono block truncate text-[0.6875rem] text-fg">@{asset.tag}</span>
        )}
      </span>
    </button>
  );
}

/** Props of {@link AssetDetail}. */
interface AssetDetailProps {
  /** The asset. */
  asset: Asset;
  /** Goes back to the grid. */
  onBack: () => void;
  /** Uploads a file to it. */
  onUpload: (file: File) => Promise<Asset>;
  /** Deletes it. */
  onDelete: () => Promise<void>;
}

/**
 * Writes a metadata value for the detail's table.
 *
 * @param value The value as recorded.
 * @returns Text for it.
 */
function metadataText(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value.join(', ');
  }
  return JSON.stringify(value);
}

/**
 * Renders an asset's detail: its media, description, and metadata.
 *
 * @param props The component's props.
 * @returns The detail.
 */
function AssetDetail({ asset, onBack, onUpload, onDelete }: AssetDetailProps) {
  const [shown, setShown] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fileId = useId();
  const media = asset.media[Math.min(shown, asset.media.length - 1)];
  const metadata = Object.entries(asset.metadata ?? {});

  /**
   * Uploads the files chosen, one after another.
   *
   * @param files The files.
   */
  async function upload(files: FileList | null): Promise<void> {
    if (files === null || files.length === 0) {
      return;
    }
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        await onUpload(file);
      }
      setShown(asset.media.length);
    } catch (failure) {
      setError(failure);
    } finally {
      setUploading(false);
    }
  }

  /** Deletes the asset. */
  async function remove(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onDelete();
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <div>
      <button type="button" className="btn btn-quiet btn-sm -ml-2 h-7 px-2 text-xs" onClick={onBack}>
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        {asset.section}
      </button>
      <div className="mt-2 flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg leading-tight font-semibold tracking-tight">{asset.name}</h3>
          {asset.tag === null || asset.tag === '' ? null : (
            <span className="tag-chip mt-1 inline-block">@{asset.tag}</span>
          )}
        </div>
      </div>

      <div className="mt-3">
        {media === undefined ? (
          <label
            htmlFor={fileId}
            className="grid aspect-video place-items-center rounded-xl border border-dashed border-line-strong text-center text-xs text-faint transition-colors hover:border-white/30 hover:text-muted"
          >
            <span>
              <ImagePlus className="mx-auto mb-1.5 size-5" aria-hidden="true" />
              No reference yet. Upload one.
            </span>
          </label>
        ) : (
          <div className="overflow-hidden rounded-xl border border-line bg-black/40">
            <MediaView key={media.url} media={media} label={asset.name} className="max-h-80 w-full" />
          </div>
        )}
        {asset.media.length > 1 ? (
          <ul className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
            {asset.media.map((file, index) => (
              // Media are only added at the end, and two files may share an address.
              <li key={`${index}:${file.url}`}>
                <button
                  type="button"
                  className={cx(
                    'asset-thumb block size-12 rounded-lg border',
                    index === shown ? 'border-fg' : 'border-line',
                  )}
                  aria-label={`Show ${file.name ?? `${file.kind} ${index + 1}`}`}
                  onClick={() => {
                    setShown(index);
                  }}
                >
                  {file.kind === 'image' ? <img src={file.url} alt="" loading="lazy" /> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {asset.description === null || asset.description === '' ? null : (
        <div className="mt-4">
          <Prose text={asset.description} />
        </div>
      )}

      {metadata.length === 0 ? null : (
        <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 rounded-xl border border-line p-3 text-xs">
          {metadata.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-faint">{key.replaceAll('_', ' ')}</dt>
              <dd className="break-words text-muted">{metadataText(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      <p className="mt-3 text-[0.6875rem] text-faint">Updated {shortDateTime(asset.updated_at)}</p>

      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <label
          htmlFor={fileId}
          className={cx('btn btn-ghost btn-sm h-8 px-3 text-xs', uploading && 'pointer-events-none opacity-60')}
        >
          {uploading ? (
            <span className="spinner size-3.5" aria-hidden="true" />
          ) : (
            <Upload className="size-3.5" aria-hidden="true" />
          )}
          {uploading ? 'Uploading…' : 'Upload media'}
        </label>
        <input
          id={fileId}
          type="file"
          className="sr-only"
          accept={MEDIA_ACCEPT}
          multiple
          disabled={uploading}
          onChange={(event) => {
            void upload(event.target.files);
            event.target.value = '';
          }}
        />
        <span className="ml-auto">
          {confirming ? (
            <span className="flex items-center gap-1">
              <button
                type="button"
                className="btn btn-danger btn-sm h-8 px-3 text-xs"
                disabled={busy}
                onClick={() => {
                  void remove();
                }}
              >
                {busy ? <span className="spinner size-3" aria-hidden="true" /> : null}
                Delete
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm h-8 px-2.5 text-xs"
                onClick={() => {
                  setConfirming(false);
                }}
              >
                Keep
              </button>
            </span>
          ) : (
            <button
              type="button"
              className="icon-btn"
              aria-label={`Delete ${asset.name}`}
              title="Delete"
              onClick={() => {
                setConfirming(true);
              }}
            >
              <Trash2 aria-hidden="true" />
            </button>
          )}
        </span>
      </div>
    </div>
  );
}

/** The section choice that asks for a new section's name. */
const NEW_SECTION = '\u0000new';

/** Props of {@link AddAsset}. */
interface AddAssetProps {
  /** The existing sections. */
  sections: string[];
  /** The section chosen at first. */
  initialSection: string;
  /** Closes the form. */
  onCancel: () => void;
  /** Adds the asset, with its first file when one is chosen. */
  onCreate: (asset: NewAsset, file: File | null) => Promise<void>;
}

/**
 * Renders the form that adds an asset.
 *
 * @param props The component's props.
 * @returns The form.
 */
function AddAsset({ sections, initialSection, onCancel, onCreate }: AddAssetProps) {
  const ids = {
    section: useId(),
    newSection: useId(),
    name: useId(),
    tag: useId(),
    description: useId(),
    file: useId(),
  };
  const [section, setSection] = useState(initialSection === '' ? NEW_SECTION : initialSection);
  const [newSection, setNewSection] = useState('');
  const [name, setName] = useState('');
  const [tag, setTag] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const suggestedTag = normalizeTag(name);

  /**
   * Adds the asset.
   *
   * @param event The form's submission.
   */
  async function submit(event: SubmitEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const chosen = section === NEW_SECTION ? newSection.trim() : section;
    const finalTag = normalizeTag(tag) || suggestedTag;
    setBusy(true);
    setError(null);
    try {
      await onCreate(
        {
          section: chosen,
          name: name.trim(),
          ...(finalTag === '' ? {} : { tag: finalTag }),
          ...(description.trim() === '' ? {} : { description: description.trim() }),
        },
        file,
      );
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <form
      className="mb-4 grid grid-cols-1 gap-2.5 rounded-xl border border-line-strong bg-white/[0.025] p-3"
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      <p className="text-sm font-semibold">Add to the library</p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label htmlFor={ids.section} className="text-xs text-muted">
            Section
          </label>
          <select
            id={ids.section}
            className="field field-sm mt-1"
            value={section}
            onChange={(event) => {
              setSection(event.target.value);
            }}
          >
            {sections.map((candidate) => (
              <option key={candidate} value={candidate}>
                {candidate}
              </option>
            ))}
            <option value={NEW_SECTION}>New section…</option>
          </select>
        </div>
        {section === NEW_SECTION ? (
          <div>
            <label htmlFor={ids.newSection} className="text-xs text-muted">
              Section name
            </label>
            <input
              id={ids.newSection}
              className="field field-sm mt-1"
              required
              maxLength={60}
              placeholder="Products"
              value={newSection}
              onChange={(event) => {
                setNewSection(event.target.value);
              }}
            />
          </div>
        ) : (
          <div>
            <label htmlFor={ids.tag} className="text-xs text-muted">
              Tag
            </label>
            <input
              id={ids.tag}
              className="field field-sm mono mt-1"
              maxLength={64}
              placeholder={suggestedTag === '' ? '@tag' : `@${suggestedTag}`}
              value={tag}
              onChange={(event) => {
                setTag(event.target.value);
              }}
            />
          </div>
        )}
      </div>
      <div>
        <label htmlFor={ids.name} className="text-xs text-muted">
          Name
        </label>
        <input
          id={ids.name}
          className="field field-sm mt-1"
          required
          maxLength={120}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
      </div>
      {section === NEW_SECTION ? (
        <div>
          <label htmlFor={ids.tag} className="text-xs text-muted">
            Tag
          </label>
          <input
            id={ids.tag}
            className="field field-sm mono mt-1"
            maxLength={64}
            placeholder={suggestedTag === '' ? '@tag' : `@${suggestedTag}`}
            value={tag}
            onChange={(event) => {
              setTag(event.target.value);
            }}
          />
        </div>
      ) : null}
      <div>
        <label htmlFor={ids.description} className="text-xs text-muted">
          Description
        </label>
        <textarea
          id={ids.description}
          className="field mt-1 h-auto min-h-16 resize-y py-2 text-sm leading-relaxed"
          rows={2}
          maxLength={4000}
          value={description}
          onChange={(event) => {
            setDescription(event.target.value);
          }}
        />
      </div>
      <div>
        <label htmlFor={ids.file} className="text-xs text-muted">
          Reference <span className="text-faint">(optional)</span>
        </label>
        <input
          id={ids.file}
          type="file"
          accept={MEDIA_ACCEPT}
          className="mt-1 block w-full text-xs text-muted file:mr-3 file:rounded-full file:border file:border-line-strong file:bg-white/5 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-fg"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
          }}
        />
      </div>
      {error === null ? null : <ErrorNotice error={error} />}
      <div className="flex justify-end gap-2">
        <button type="button" className="btn btn-quiet btn-sm h-8 px-3 text-xs" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="submit"
          className="btn btn-primary btn-sm h-8 px-3.5 text-xs"
          disabled={busy || name.trim() === ''}
        >
          {busy ? (
            <span className="spinner size-3.5" aria-hidden="true" />
          ) : (
            <Plus className="size-3.5" aria-hidden="true" />
          )}
          Add
        </button>
      </div>
    </form>
  );
}
