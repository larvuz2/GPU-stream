/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * ESLint configuration of the site: typescript-eslint's type-checked rules over every TypeScript
 * file, with the React hooks and fast-refresh rules over the pages.
 *
 * typescript-eslint parses through the TypeScript 6 API (the `typescript` package here), while
 * `tsc` is the native TypeScript 7 compiler (`@typescript/native`); see `package.json`.
 * @module
 */
import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import { reactRefresh } from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig([
  // A rule holds everywhere it applies: no comment turns one off or reconfigures it, so a finding
  // is fixed in the code.
  { linterOptions: { noInlineConfig: true } },
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.strictTypeChecked, tseslint.configs.stylisticTypeChecked],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      // No type assertion that narrows: a guard narrows, never `as`.
      '@typescript-eslint/no-unsafe-type-assertion': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      // A number or a boolean reads as itself in a template; anything else is converted on purpose.
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true, allowBoolean: true }],
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat.recommended, reactRefresh.configs.vite()],
    languageOptions: { globals: globals.browser },
  },
  {
    files: ['*.ts'],
    languageOptions: { globals: globals.node },
  },
]);
