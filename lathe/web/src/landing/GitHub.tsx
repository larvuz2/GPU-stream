/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The landing page's GitHub section: a person connects their own account once, links each project
 * to a repository, new or existing, and the agent saves the project's script, library manifest,
 * and shot list there as it works.
 *
 * The repository beside the words is drawn in markup and labeled as an example. It is drawn with
 * generic icons rather than GitHub's mark, which is another company's logo.
 * @module
 */
import { ArrowRight, FileJson, FileText, FolderGit2, GitCommitHorizontal, Lock } from 'lucide-react';
import { CREATE_HASH } from './studio';

/** The steps from no connection to a project under version control. */
const STEPS = [
  'Connect your GitHub account once, from any project.',
  'Link each project to a new repository or one you already have.',
  'The agent commits the script, the library, and the shot list as it works.',
] as const;

/** The example repository's files: their names, what they hold, and their last change. */
const FILES = [
  { icon: FileText, name: 'script.md', change: 'Rewrite the last scene' },
  { icon: FileJson, name: 'library.json', change: 'Add @iris to the cast' },
  { icon: FileJson, name: 'shots.json', change: 'Lock the shot list' },
] as const;

/** The example repository's latest commits, newest first. */
const COMMITS = [
  { author: 'Agent', message: 'Lock the shot list' },
  { author: 'You', message: 'Rewrite the last scene' },
  { author: 'Agent', message: 'Add reference images for @mara, @theo, @iris' },
] as const;

/**
 * Renders the GitHub section.
 *
 * @returns The section.
 */
export function GitHub() {
  return (
    <section id="github" className="section" aria-labelledby="github-title">
      <div className="shell grid grid-cols-[minmax(0,1fr)] items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
        <div>
          <p className="eyebrow">
            <FolderGit2 className="size-4" aria-hidden="true" />
            Version control
          </p>
          <h2 id="github-title" className="display mt-4 text-[2rem] sm:text-5xl">
            Your work lives in <span className="text-gradient">your GitHub</span>
          </h2>
          <p className="lede mt-5 text-[1.0625rem] sm:text-lg">
            Connect your account and every project gets a repository. Every change the agent makes is a commit you
            can read, roll back, or take anywhere.
          </p>
          <ol className="mt-8 grid gap-3">
            {STEPS.map((step, index) => (
              <li key={step} className="flex items-start gap-3.5 text-[0.9375rem]">
                <span className="grid size-7 flex-none place-items-center rounded-full border border-ember/40 bg-ember/10 text-xs font-bold text-ember-300">
                  {index + 1}
                </span>
                <span className="pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
          <a href={CREATE_HASH} className="btn btn-primary btn-lg mt-8 w-full sm:w-auto">
            Start creating
            <ArrowRight className="size-4" aria-hidden="true" />
          </a>
        </div>

        <figure>
          <div className="glass overflow-hidden rounded-3xl bg-ink-900/80" aria-hidden="true">
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <FolderGit2 className="size-5 flex-none text-ember-300" />
              <p className="min-w-0 truncate text-sm">
                <span className="text-muted">your-name / </span>
                <span className="font-semibold">night-shift</span>
              </p>
              <span className="pill ml-auto flex-none text-muted">
                <Lock className="size-3" />
                Private
              </span>
            </div>
            <ul className="divide-y divide-line text-sm">
              {FILES.map(({ icon: Icon, name, change }) => (
                <li key={name} className="flex items-center gap-3 px-5 py-3">
                  <Icon className="size-4 flex-none text-faint" />
                  <span className="mono flex-none font-medium">{name}</span>
                  <span className="min-w-0 flex-1 truncate text-right text-xs text-faint">{change}</span>
                </li>
              ))}
            </ul>
            <div className="border-t border-line bg-black/25 px-5 py-4">
              <p className="text-[0.6875rem] font-semibold tracking-[0.14em] text-faint uppercase">Latest commits</p>
              <ul className="mt-3 grid gap-2.5 text-[0.8125rem]">
                {COMMITS.map((commit) => (
                  <li key={commit.message} className="flex min-w-0 items-center gap-2.5">
                    <GitCommitHorizontal className="size-4 flex-none text-faint" />
                    <span
                      className={
                        commit.author === 'Agent'
                          ? 'flex-none rounded-full bg-ember/15 px-2 py-0.5 text-[0.6875rem] font-semibold text-ember-200'
                          : 'flex-none rounded-full bg-white/10 px-2 py-0.5 text-[0.6875rem] font-semibold text-muted'
                      }
                    >
                      {commit.author}
                    </span>
                    <span className="min-w-0 truncate">{commit.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <figcaption className="mt-4 text-center text-sm text-faint">An example repository.</figcaption>
        </figure>
      </div>
    </section>
  );
}
