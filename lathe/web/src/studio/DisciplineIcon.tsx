/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A discipline's icon.
 *
 * The catalog holds no icons, so each discipline's comes from here by identifier, and one the
 * catalog adds later gets a plain folder until it is given its own.
 * @module
 */
import { createElement } from 'react';
import {
  BookOpen,
  Building2,
  Camera,
  Clapperboard,
  Code,
  Film,
  Folder,
  Gamepad2,
  Music,
  Palette,
  PenTool,
  Shirt,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

/** The icon of each discipline, by catalog identifier. */
const ICONS: Readonly<Record<string, LucideIcon>> = {
  media: Clapperboard,
  music: Music,
  art: Palette,
  design: PenTool,
  photography: Camera,
  animation: Film,
  games: Gamepad2,
  architecture: Building2,
  fashion: Shirt,
  writing: BookOpen,
  technology: Code,
  experiences: Sparkles,
};

/** Props of {@link DisciplineIcon}. */
interface DisciplineIconProps {
  /** The discipline's identifier. */
  id: string;
  /** Classes that size and color the icon. */
  className?: string;
}

/**
 * Renders a discipline's icon, as decoration beside its name.
 *
 * @param props The component's props.
 * @returns The icon.
 */
export function DisciplineIcon({ id, className }: DisciplineIconProps) {
  const icon = Object.hasOwn(ICONS, id) ? (ICONS[id] ?? Folder) : Folder;
  return createElement(icon, { className, 'aria-hidden': true });
}
