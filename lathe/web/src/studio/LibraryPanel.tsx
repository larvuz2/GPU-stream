/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The Library panel's body: the project's assets by section, an asset's detail, and adding one.
 *
 * The sections are the project's own (`useProject`, `sections`): a film has characters,
 * environments, and props, a commercial products and shots, and the agent adds sections as the
 * work needs them, so nothing here names one. Each asset is a card of its thumbnail, its `@tag`,
 * and its name; its detail shows its media, description, and metadata, and takes more media. A
 * person adds an asset with a name, a tag, a description, and optionally a first file, in an
 * existing section or a new one.
 * @module
 */
import { useId, useMemo, useState, type SubmitEvent } from 'react';
import { ArrowLeft, ImagePlus, Plus, Trash2, Upload } from 'lucide-react';
import type { Asset, NewAsset } from '../lib/api';
import { cx } from '../lib/cx';
import { shortDateTime } from '../lib/format';
import { MediaView } from './MediaView';
import { ErrorNotice, Notice } from './Notice';
import { Prose } from './Prose';
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
}

/**
 * Normalizes a tag as prompts name it: lowercase, without the `@`, words joined by hyphens.
 *
 * @param text The tag as typed.
 * @returns The tag.
 */
function normalizeTag(text: string): string {
  return text
    .trim()
    .replace(/^@+/, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}_-]+/gu, '-')
    .replace(/^-+|-+$/g, '');
}

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
export function LibraryBody({ data, openAssetId, onOpenAsset, adding, onAdding, generation }: LibraryBodyProps) {
  const [filter, setFilter] = useState<string | null>(null);
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

  const shown = filter === null || !data.sections.includes(filter) ? null : filter;
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
      <SectionChips
        sections={data.sections}
        assets={assets}
        selected={shown}
        onSelect={setFilter}
        onAddSection={data.addSection}
      />
      {data.sections.length === 0 ? (
        <p className="mt-3 text-sm text-faint">
          Nothing here yet. The agent fills the library as the work takes shape: characters, places, products, whatever
          the project needs.
        </p>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-4">
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

/** Props of {@link SectionChips}. */
interface SectionChipsProps {
  /** The sections. */
  sections: string[];
  /** Every asset, to count each section's. */
  assets: Asset[];
  /** The section shown alone, or `null` for all. */
  selected: string | null;
  /** Shows one section alone, or all. */
  onSelect: (section: string | null) => void;
  /** Adds a section. */
  onAddSection: (name: string) => Promise<void>;
}

/**
 * Renders the section filter and the control that adds a section.
 *
 * @param props The component's props.
 * @returns The chips.
 */
function SectionChips({ sections, assets, selected, onSelect, onAddSection }: SectionChipsProps) {
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

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          className="chip h-7 px-2.5 text-xs"
          aria-pressed={selected === null}
          onClick={() => {
            onSelect(null);
          }}
        >
          All <span className="chip-count">{assets.length}</span>
        </button>
        {sections.map((section) => (
          <button
            key={section}
            type="button"
            className="chip h-7 px-2.5 text-xs"
            aria-pressed={selected === section}
            onClick={() => {
              onSelect(section);
            }}
          >
            {section} <span className="chip-count">{assets.filter((asset) => asset.section === section).length}</span>
          </button>
        ))}
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
          <span className="mono block truncate text-[0.6875rem] text-ember-200">@{asset.tag}</span>
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
                    index === shown ? 'border-ember-300' : 'border-line',
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
