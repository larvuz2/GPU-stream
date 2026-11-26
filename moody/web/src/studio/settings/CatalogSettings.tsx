/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The catalog's settings of one tab of Settings, each drawn by its kind.
 *
 * A setting is data (`Setting` in `lib/catalog.ts`): its label, a line of help, and its kind,
 * which picks the control from {@link CONTROLS}: a switch for a `toggle`, one of its options for a
 * `choice`. So a setting added to the catalog is drawn with no code here, and a kind this page
 * does not know yet is left out, since a control that cannot hold its value would only mislead.
 *
 * A change is saved at once, with no button: the control shows the new value while the control
 * plane takes it, and goes back to the value that applies where it refuses, with its refusal
 * shown under the setting in its own words. The value shown is always the control plane's
 * (`Me.settings`), never one this page only assumed.
 * @module
 */
import { useId, useState, type ComponentType } from 'react';
import type { SettingValue } from '../../lib/api';
import type { Setting } from '../../lib/catalog';
import { ErrorNotice } from '../Notice';

/** Props of a setting's control. */
interface ControlProps {
  /** The setting. */
  setting: Setting;
  /** The value shown. */
  value: SettingValue;
  /** Whether a change is being saved. */
  busy: boolean;
  /** Saves a new value. */
  onChange: (value: SettingValue) => void;
}

/**
 * Renders a setting that is on or off: its label and help, and a switch.
 *
 * @param props The component's props.
 * @returns The setting.
 */
function Toggle({ setting, value, busy, onChange }: ControlProps) {
  const labelId = useId();
  const helpId = useId();
  const on = value === true;
  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1">
        <p id={labelId} className="text-sm font-medium">
          {setting.label}
        </p>
        <p id={helpId} className="mt-1 text-sm leading-relaxed text-muted">
          {setting.help}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        className="switch"
        aria-checked={on}
        aria-labelledby={labelId}
        aria-describedby={helpId}
        aria-busy={busy}
        onClick={() => {
          if (!busy) {
            onChange(!on);
          }
        }}
      >
        <span className="switch-knob" aria-hidden="true" />
      </button>
    </div>
  );
}

/**
 * Renders a setting that is one of a few options: its label and help, and the options to choose
 * from.
 *
 * @param props The component's props.
 * @returns The setting.
 */
function Choice({ setting, value, busy, onChange }: ControlProps) {
  const helpId = useId();
  return (
    <fieldset aria-describedby={helpId} aria-busy={busy}>
      <legend className="text-sm font-medium">{setting.label}</legend>
      <p id={helpId} className="mt-1 text-sm leading-relaxed text-muted">
        {setting.help}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {(setting.options ?? []).map((option) => (
          <label key={option.value} className="chip cursor-pointer">
            <input
              type="radio"
              className="sr-only"
              name={setting.id}
              value={option.value}
              checked={value === option.value}
              onChange={() => {
                if (!busy) {
                  onChange(option.value);
                }
              }}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** The control each kind of setting is drawn with. */
const CONTROLS: Readonly<Record<string, ComponentType<ControlProps>>> = { toggle: Toggle, choice: Choice };

/** Props of {@link CatalogSettings}. */
interface CatalogSettingsProps {
  /** The settings to draw, in order. */
  settings: readonly Setting[];
  /** The values that apply, by setting; `undefined` until the account has loaded. */
  values: Readonly<Record<string, SettingValue>> | undefined;
  /** Saves a setting's new value. Rejects with an `ApiError`, 400 for one the control plane refuses. */
  onChange: (id: string, value: SettingValue) => Promise<void>;
}

/**
 * Renders the settings of a tab.
 *
 * @param props The component's props.
 * @returns The settings, or a placeholder of their size while the account loads.
 */
export function CatalogSettings({ settings, values, onChange }: CatalogSettingsProps) {
  if (values === undefined) {
    return <div className="h-16 animate-pulse rounded-xl bg-white/[0.04]" aria-label="Loading your settings" />;
  }
  return (
    <ul className="settings-rows">
      {settings.map((setting) => {
        const Control = Object.hasOwn(CONTROLS, setting.kind) ? CONTROLS[setting.kind] : undefined;
        return Control === undefined ? null : (
          <li key={setting.id}>
            <SettingRow
              setting={setting}
              Control={Control}
              value={values[setting.id] ?? setting.default}
              onChange={onChange}
            />
          </li>
        );
      })}
    </ul>
  );
}

/** Props of {@link SettingRow}. */
interface SettingRowProps {
  /** The setting. */
  setting: Setting;
  /** The control its kind is drawn with. */
  Control: ComponentType<ControlProps>;
  /** The value that applies. */
  value: SettingValue;
  /** Saves a setting's new value. */
  onChange: (id: string, value: SettingValue) => Promise<void>;
}

/**
 * Renders one setting and saves each change of it at once.
 *
 * @param props The component's props.
 * @returns The setting, with the control plane's refusal under it where the last change was refused.
 */
function SettingRow({ setting, Control, value, onChange }: SettingRowProps) {
  // The value being saved, which the control shows until the control plane has answered.
  const [saving, setSaving] = useState<{ value: SettingValue } | null>(null);
  const [error, setError] = useState<unknown>(null);

  /**
   * Saves a new value.
   *
   * @param next The value.
   */
  async function change(next: SettingValue): Promise<void> {
    setSaving({ value: next });
    setError(null);
    try {
      await onChange(setting.id, next);
    } catch (failure) {
      setError(failure);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div data-setting={setting.id}>
      <Control
        setting={setting}
        value={saving?.value ?? value}
        busy={saving !== null}
        onChange={(next) => {
          void change(next);
        }}
      />
      {error === null ? null : (
        <div className="mt-3">
          <ErrorNotice error={error} />
        </div>
      )}
    </div>
  );
}
