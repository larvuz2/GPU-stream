/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's composite: pictures stacked as layers, with an inspector where the composite has an id.
 *
 * The layers are drawn over one another in the card's order, the first at the bottom, each with
 * its opacity and blend mode, by the browser's own compositing: nothing is read back from a
 * canvas, so the layers may come from anywhere. The frame takes the shape of the bottom layer.
 *
 * With an id, the composite is an input. A dropdown picks a layer, and a switch and a slider set
 * that layer's visibility and opacity; the picture answers as they move. Its answer is every
 * layer's setting by name and the layer last in the inspector, which is how a card asks "which
 * of these stays, and how strong". Each layer's own visibility and opacity in the card are what
 * the agent recommends for it, so the switch and the slider of the layer in the inspector are
 * each marked while they hold it and offer the way back once they do not (`Recommend.tsx`);
 * which layer is in the inspector is where the person looks, and no part of the recommendation.
 * @module
 */
import { useState } from 'react';
import { useCard } from '../context';
import { Recommended, WayBack } from '../Recommend';
import { isLayersValue, layerSpecs, type LayerSetting } from '../values';
import { useInput, type ViewProps } from '../view';
import { Missing } from './Adjusted';

/** The shape the frame takes until the bottom layer has loaded and said its own. */
const DEFAULT_ASPECT = '4 / 5';

/**
 * Renders a composite and, where it answers, its inspector.
 *
 * @param props The component's props.
 * @returns The composite.
 */
export function Layers({ node }: ViewProps) {
  const card = useCard();
  const input = useInput(node);
  const [aspect, setAspect] = useState(DEFAULT_ASPECT);
  const layers = layerSpecs(node);
  const answers = isLayersValue(input.value);
  const value = isLayersValue(input.value) ? input.value : null;
  const settingOf = (name: string): LayerSetting => {
    const spec = layers.find((layer) => layer.name === name);
    return value?.layers[name] ?? { visible: spec?.visible ?? true, opacity: spec?.opacity ?? 100 };
  };
  const selected = layers.find((layer) => layer.name === value?.selected) ?? layers.at(-1);

  /**
   * Changes one layer's setting.
   *
   * @param name The layer.
   * @param change What to change of it.
   */
  function change(name: string, change: Partial<LayerSetting>): void {
    if (value !== null) {
      input.set({ ...value, layers: { ...value.layers, [name]: { ...settingOf(name), ...change } } });
    }
  }

  if (layers.length === 0) {
    return <Missing name="The composite" />;
  }
  const current = selected === undefined ? null : settingOf(selected.name);
  // What the agent recommends for the layer in the inspector, which each of its two controls is held against.
  const advised =
    input.advice !== null && isLayersValue(input.advice.value) && selected !== undefined
      ? (input.advice.value.layers[selected.name] ?? null)
      : null;
  return (
    <div className="ui-stack">
      <div
        className="ui-frame ui-composite"
        style={{ aspectRatio: aspect }}
        role="img"
        aria-label={`Composite of ${layers.length} layers: ${layers
          .map((layer) => `${layer.name} ${settingOf(layer.name).visible ? `${Math.round(settingOf(layer.name).opacity)}%` : 'hidden'}`)
          .join(', ')}`}
      >
        {layers.map((layer, index) => {
          const media = card.media(layer.src);
          const setting = settingOf(layer.name);
          return media === null ? null : (
            <img
              key={layer.name}
              src={media.url}
              alt=""
              decoding="async"
              draggable={false}
              className="ui-layer"
              data-selected={answers && layer.name === selected?.name ? 'true' : undefined}
              style={{
                opacity: setting.visible ? setting.opacity / 100 : 0,
                '--ui-blend': layer.blend,
              }}
              onLoad={
                index === 0
                  ? (event) => {
                      const { naturalWidth, naturalHeight } = event.currentTarget;
                      if (naturalWidth > 0 && naturalHeight > 0) {
                        setAspect(`${naturalWidth} / ${naturalHeight}`);
                      }
                    }
                  : undefined
              }
            />
          );
        })}
      </div>
      {value === null || selected === undefined || current === null ? null : (
        <div className="ui-inspector">
          <div className="ui-input">
            <label htmlFor={`${input.domId}-layer`} className="ui-label">
              Layer
            </label>
            <select
              id={`${input.domId}-layer`}
              className="ui-field ui-select"
              value={selected.name}
              disabled={input.frozen}
              onChange={(event) => {
                input.set({ ...value, selected: event.target.value });
              }}
            >
              {/* The top layer first, as a layers panel lists them. */}
              {[...layers].reverse().map((layer) => (
                <option key={layer.name} value={layer.name}>
                  {layer.name}
                  {settingOf(layer.name).visible ? '' : ' (hidden)'}
                </option>
              ))}
            </select>
          </div>
          <div className="ui-toggle-line">
            <label className="ui-toggle">
              <input
                type="checkbox"
                role="switch"
                className="sr-only"
                checked={current.visible}
                disabled={input.frozen}
                onChange={(event) => {
                  change(selected.name, { visible: event.target.checked });
                }}
              />
              <span className="ui-switch" aria-hidden="true" />
              <span className="ui-label">Visible</span>
            </label>
            {advised === null ? null : advised.visible === current.visible || input.frozen ? (
              <Recommended words={advised.visible ? 'on' : 'off'} />
            ) : (
              <WayBack
                input={{ ...input, label: `${selected.name}, visible` }}
                words={advised.visible ? 'on' : 'off'}
                onBack={() => {
                  change(selected.name, { visible: advised.visible });
                }}
              />
            )}
          </div>
          <div className="ui-input">
            <div className="ui-input-head">
              <span className="ui-label-line">
                <label htmlFor={`${input.domId}-opacity`} className="ui-label">
                  Opacity
                </label>
                {advised === null ? null : advised.opacity === current.opacity ? (
                  <Recommended />
                ) : input.frozen ? (
                  <Recommended words={`${Math.round(advised.opacity)}%`} />
                ) : (
                  <WayBack
                    input={{ ...input, label: `${selected.name}, opacity` }}
                    words={`${Math.round(advised.opacity)}%`}
                    onBack={() => {
                      change(selected.name, { opacity: advised.opacity });
                    }}
                  />
                )}
              </span>
              <output htmlFor={`${input.domId}-opacity`} className="ui-readout">
                {Math.round(current.opacity)}%
              </output>
            </div>
            <div
              className="ui-range-wrap"
              data-advised={advised === null ? undefined : 'true'}
              style={advised === null ? undefined : { '--ui-advised': `${advised.opacity}` }}
            >
              <input
                id={`${input.domId}-opacity`}
                type="range"
                className="ui-range"
                min={0}
                max={100}
                value={current.opacity}
                disabled={input.frozen || !current.visible}
                aria-valuetext={
                  advised?.opacity === current.opacity
                    ? `${Math.round(current.opacity)}% (recommended)`
                    : `${Math.round(current.opacity)}%`
                }
                style={{ '--ui-from': '0%', '--ui-to': `${current.opacity}%` }}
                onChange={(event) => {
                  change(selected.name, { opacity: event.target.valueAsNumber });
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
