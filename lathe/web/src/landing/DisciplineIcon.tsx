/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The icon each discipline is drawn with on the landing page, wherever it is named.
 *
 * The icons are chosen here by discipline identifier, since the catalog says what a discipline
 * is and not how it looks; a discipline added to the catalog after this list is drawn with a
 * generic mark until it is given one.
 * @module
 */
import { createElement } from 'react';
import {
  Building2,
  Camera,
  Clapperboard,
  Feather,
  Gamepad2,
  MonitorSmartphone,
  Music,
  Orbit,
  Palette,
  PenTool,
  Shapes,
  Shirt,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

/** The icon of each discipline, by identifier. */
const ICONS: Readonly<Record<string, LucideIcon>> = {
  media: Clapperboard,
  music: Music,
  art: Palette,
  design: PenTool,
  photography: Camera,
  animation: Shapes,
  games: Gamepad2,
  architecture: Building2,
  fashion: Shirt,
  writing: Feather,
  technology: MonitorSmartphone,
  experiences: Orbit,
};

/** Props of {@link DisciplineIcon}. */
interface DisciplineIconProps {
  /** The identifier of the discipline. */
  discipline: string;
  /** Classes that size and color the icon. */
  className?: string;
}

/**
 * Renders a discipline's icon, hidden from assistive technology since the name is always beside it.
 *
 * @param props The component's props.
 * @returns The icon.
 */
export function DisciplineIcon({ discipline, className }: DisciplineIconProps) {
  return createElement(ICONS[discipline] ?? Sparkles, { className, 'aria-hidden': true });
}
