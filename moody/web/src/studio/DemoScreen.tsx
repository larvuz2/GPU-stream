/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * What the demo's Screen shows in place of a stream: a still picture of an engine at work.
 *
 * The demo has no workstation to stream, so it draws one: an editor's media bin, viewer, and
 * timeline for an editing app, and the app's own artwork for any other. An Unreal engine's Desktop
 * is the Blender that runs there, drawn with Blender's artwork, and its Unreal view the art of
 * Unreal Engine's card. It is sized in container units, so it reads the same in the column and in
 * focus mode. It is part of the demo's chunk and never shown over a real engine.
 * @module
 */
import { DESKTOP_STREAM } from '../lib/api';
import type { CatalogApp } from '../lib/catalog';
import { engineImage } from '../lib/media';

/** The demo film's stills, which the drawn editor's bin and viewer show. */
const STILLS = [
  '/media/character-theo.webp',
  '/media/character-mara.webp',
  '/media/discipline-architecture.webp',
  '/media/discipline-media.webp',
];

/** The drawn timeline's tracks: each clip's start and length in percent of the sequence, and its tint. */
const TRACKS: readonly { name: string; clips: readonly [number, number, string][] }[] = [
  { name: 'V2', clips: [[31, 12, '#ffffff']] },
  {
    name: 'V1',
    clips: [
      [0, 14, '#bdbdbd'],
      [14.5, 16, '#bdbdbd'],
      [31, 21, '#e6e6e6'],
      [52.5, 13, '#bdbdbd'],
    ],
  },
  { name: 'A1', clips: [[0, 66, '#8c8c8c']] },
  {
    name: 'A2',
    clips: [
      [6, 22, '#6e6e6e'],
      [36, 26, '#6e6e6e'],
    ],
  },
];

/** Props of {@link DemoScreen}. */
interface DemoScreenProps {
  /** The engine's app. */
  app: CatalogApp | undefined;
  /** The picture of the engine on screen, or `null` for an engine that streams its desktop alone. */
  stream: string | null;
}

/**
 * Renders the drawn engine.
 *
 * @param props The component's props.
 * @returns The picture, filling its frame.
 */
export function DemoScreen({ app, stream }: DemoScreenProps) {
  if (app?.id !== 'filmcraft') {
    const desktop = app?.id === 'unreal' && stream === DESKTOP_STREAM;
    const picture = desktop ? engineImage('blender') : app === undefined ? undefined : engineImage(app.id);
    return (
      <div className="absolute inset-0 bg-ink-800">
        <img src={picture ?? STILLS[2]} alt="" className="absolute inset-0 size-full object-cover" />
        <span className="absolute bottom-3 left-3 rounded-md bg-ink-950/70 px-2 py-1 text-xs font-semibold">
          {desktop
            ? 'Desktop · GitHub client, Firefox, Blender'
            : stream === null
              ? app?.name
              : `${app?.name ?? ''} · ${stream}`}
        </span>
      </div>
    );
  }
  return (
    <div className="@container absolute inset-0">
      <div className="flex size-full flex-col bg-[#0d0d0d] font-sans text-[clamp(5px,1.15cqw,12px)] text-white/70 select-none">
        <div className="flex h-[6%] items-center gap-[2.2%] border-b border-white/5 bg-[#191919] px-[1.5%]">
          <span className="font-semibold text-white/90">{app.name}</span>
          {['File', 'Edit', 'Clip', 'Sequence', 'Color', 'Audio', 'Export'].map((menu) => (
            <span key={menu}>{menu}</span>
          ))}
          <span className="ml-auto text-white/40">The Beacon · Scene 1</span>
        </div>
        <div className="flex min-h-0 flex-1">
          <div className="flex w-[22%] flex-col gap-[3%] border-r border-white/5 bg-[#121212] p-[1.2%]">
            <span className="text-white/45">Media</span>
            <div className="grid grid-cols-2 gap-[6%]">
              {STILLS.map((still) => (
                <div key={still} className="aspect-video overflow-hidden rounded-[0.3em] bg-white/5">
                  <img src={still} alt="" className="size-full object-cover opacity-90" />
                </div>
              ))}
            </div>
          </div>
          <div className="flex min-w-0 flex-1 flex-col items-center justify-center bg-black/60 p-[1.5%]">
            <div className="relative aspect-video h-[88%] max-w-full overflow-hidden rounded-[0.2em]">
              <img src={STILLS[0]} alt="" className="size-full object-cover" />
              <span className="absolute bottom-[4%] left-[3%] rounded-[0.25em] bg-black/60 px-[0.6em] py-[0.15em] font-mono text-white/85">
                01:00:07:14
              </span>
            </div>
          </div>
        </div>
        <div className="relative h-[34%] border-t border-white/5 bg-[#111111] px-[1.2%] py-[1%]">
          <div className="ml-[5%] flex justify-between pb-[0.6%] font-mono text-white/30">
            {['00:00', '00:15', '00:30', '00:45', '01:00'].map((mark) => (
              <span key={mark}>{mark}</span>
            ))}
          </div>
          <div className="grid h-[82%] grid-rows-4 gap-[4%]">
            {TRACKS.map((track) => (
              <div key={track.name} className="flex items-stretch gap-[1%]">
                <span className="w-[4%] self-center font-mono text-white/40">{track.name}</span>
                <div className="relative flex-1 rounded-[0.2em] bg-white/[0.03]">
                  {track.clips.map(([start, length, tint]) => (
                    <span
                      key={start}
                      className="absolute inset-y-[8%] rounded-[0.25em] border border-white/20"
                      style={{ left: `${start}%`, width: `${length}%`, background: `${tint}55` }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <span className="absolute top-[6%] bottom-[4%] left-[30%] w-px bg-white" />
        </div>
      </div>
    </div>
  );
}
