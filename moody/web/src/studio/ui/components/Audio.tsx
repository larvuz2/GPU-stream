/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's sound: its waveform, with a player. {@link Audio} is the `audio` component, and
 * {@link Sound} the player itself, which a tile that plays and an uploaded sound also use.
 *
 * The file is fetched once and decoded off the audio device (an offline context, which needs no
 * gesture and makes no sound) to find the loudest sample of each of {@link BARS} slices, which is
 * the waveform drawn. Playing is an ordinary `audio` element, so the browser streams and
 * buffers as it would anywhere, and nothing plays until the person presses play. The waveform is
 * also the seek bar: a native range input lies over it, so it is sought by pointer, touch, and
 * the arrow keys, and the part already played is lit.
 *
 * Where the file cannot be decoded (a format this browser's decoder lacks, an address that
 * does not allow the read), the player still works over a flat line: the picture of the sound
 * is an aid, and the sound itself never waits on it.
 *
 * A card plays one sound at a time: every player joins the card's set of sounds
 * (`context.ts`), and starting one pauses the others, so two takes are compared by ear without
 * reaching for a second button.
 * @module
 */
import { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { useCard } from '../context';
import { text } from '../tree';
import type { ViewProps } from '../view';
import { Missing } from './Adjusted';

/** How many bars the waveform is drawn with. */
const BARS = 96;

/** The height a bar has where the waveform is not known, as a share of the frame. */
const FLAT = 0.08;

/**
 * Writes a time as minutes and seconds.
 *
 * @param seconds The time.
 * @returns The time, such as `0:07`.
 */
function clock(seconds: number): string {
  const whole = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/**
 * Finds the loudest sample of each slice of a sound.
 *
 * @param audio The decoded sound.
 * @returns One peak per bar, 0 to 1, scaled so the loudest bar is full.
 */
function peaksOf(audio: AudioBuffer): number[] {
  const samples = audio.getChannelData(0);
  const size = Math.max(1, Math.floor(samples.length / BARS));
  const peaks = Array.from({ length: BARS }, (_unused, bar) => {
    let peak = 0;
    for (let index = bar * size; index < Math.min(samples.length, (bar + 1) * size); index += 1) {
      peak = Math.max(peak, Math.abs(samples[index] ?? 0));
    }
    return peak;
  });
  const loudest = Math.max(...peaks, 0.0001);
  return peaks.map((peak) => peak / loudest);
}

/**
 * Renders the `audio` component: a sound with its waveform and a player.
 *
 * @param props The component's props.
 * @returns The player, or its placeholder where the card does not carry the file.
 */
export function Audio({ node }: ViewProps) {
  const card = useCard();
  const media = card.media(node.props.src);
  if (media === null) {
    return <Missing name={text(node, 'src') ?? 'A sound'} />;
  }
  return <Sound url={media.url} name={text(node, 'label') ?? media.name} />;
}

/** Props of {@link Sound}. */
interface SoundProps {
  /** Where the sound is read from. */
  url: string;
  /** What the sound is called, which names its controls. */
  name: string;
  /** Whether the name is written over the waveform; a tile that says it elsewhere leaves it out. */
  titled?: boolean;
}

/**
 * Renders a sound's player: a play button, the waveform to seek on, and the time.
 *
 * @param props The component's props.
 * @returns The player, or a placeholder where the browser cannot play the file.
 */
export function Sound({ url, name, titled = true }: SoundProps) {
  const card = useCard();
  const element = useRef<HTMLAudioElement>(null);
  const [peaks, setPeaks] = useState<number[] | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [length, setLength] = useState(0);
  const [failed, setFailed] = useState(false);

  // The card knows its sounds, so that it plays one at a time.
  const sounds = card.sounds;
  useEffect(() => {
    const audio = element.current;
    if (audio === null) {
      return;
    }
    sounds.add(audio);
    return () => {
      sounds.delete(audio);
    };
  }, [sounds, failed]);

  useEffect(() => {
    const leaving = new AbortController();
    void (async () => {
      try {
        const bytes = await (await fetch(url, { signal: leaving.signal })).arrayBuffer();
        const decoded = await new OfflineAudioContext(1, 1, 44_100).decodeAudioData(bytes);
        if (!leaving.signal.aborted) {
          setPeaks(peaksOf(decoded));
          setLength((known) => (known > 0 ? known : decoded.duration));
        }
      } catch {
        // The sound plays without its picture.
      }
    })();
    return () => {
      leaving.abort();
    };
  }, [url]);

  if (failed) {
    return <Missing name={name} />;
  }
  const played = length > 0 ? time / length : 0;
  return (
    <div className="ui-audio">
      <audio
        ref={element}
        src={url}
        preload="metadata"
        onLoadedMetadata={(event) => {
          if (Number.isFinite(event.currentTarget.duration)) {
            setLength(event.currentTarget.duration);
          }
        }}
        onTimeUpdate={(event) => {
          setTime(event.currentTarget.currentTime);
        }}
        onPlay={(event) => {
          setPlaying(true);
          for (const other of sounds) {
            if (other !== event.currentTarget) {
              other.pause();
            }
          }
        }}
        onPause={() => {
          setPlaying(false);
        }}
        onError={() => {
          setFailed(true);
        }}
      />
      <button
        type="button"
        className="ui-play"
        aria-label={playing ? `Pause ${name}` : `Play ${name}`}
        onClick={() => {
          const audio = element.current;
          if (audio === null) {
            return;
          }
          if (audio.paused) {
            void audio.play();
          } else {
            audio.pause();
          }
        }}
      >
        {playing ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
      </button>
      <div className="ui-audio-body">
        <div className="ui-input-head">
          {titled ? <span className="ui-label truncate">{name}</span> : <span />}
          <span className="ui-readout">
            {clock(time)} / {clock(length)}
          </span>
        </div>
        <div className="ui-wave">
          <svg viewBox={`0 0 ${BARS} 1`} preserveAspectRatio="none" aria-hidden="true">
            {(peaks ?? Array.from({ length: BARS }, () => FLAT)).map((peak, bar) => {
              const height = Math.max(FLAT, peak);
              return (
                <rect
                  // The bars are the slices of one sound, in order.
                  key={bar}
                  className="ui-wave-bar"
                  data-played={(bar + 0.5) / BARS <= played ? 'true' : undefined}
                  x={bar + 0.2}
                  y={(1 - height) / 2}
                  width={0.6}
                  height={height}
                />
              );
            })}
          </svg>
          <input
            type="range"
            className="ui-seek"
            min={0}
            max={length > 0 ? length : 1}
            step={0.05}
            value={time}
            aria-label={`Position in ${name}`}
            aria-valuetext={`${clock(time)} of ${clock(length)}`}
            onChange={(event) => {
              const audio = element.current;
              if (audio !== null) {
                audio.currentTime = event.target.valueAsNumber;
                setTime(event.target.valueAsNumber);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
