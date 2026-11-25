/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * Renders the agent's text from the Markdown subset `markdown.ts` parses.
 *
 * Every piece becomes a React element whose text React escapes, so nothing the agent writes is
 * ever markup. A library tag the project has (`@mara`) is a button that opens its asset; one it
 * does not have yet reads as the tag, styled the same but inert. Text that is still being written
 * ends in a caret (`.prose-studio[data-streaming]`), which goes once the text is whole.
 * @module
 */
import { Fragment, useMemo, type ReactNode } from 'react';
import { parseMarkdown, type Inline } from './markdown';

/** Props of {@link Prose}. */
interface ProseProps {
  /** The text, in the Markdown subset. */
  text: string;
  /** The library's tags, lowercase and without the `@`, which become references. */
  tags?: ReadonlySet<string>;
  /** Opens the asset a tag names. */
  onTag?: (tag: string) => void;
  /** Whether the text is still being written. */
  streaming?: boolean;
}

/**
 * Renders the text.
 *
 * @param props The component's props.
 * @returns The text's blocks.
 */
export function Prose({ text, tags, onTag, streaming = false }: ProseProps) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  const inline = (runs: Inline[]): ReactNode => <InlineRuns runs={runs} tags={tags} onTag={onTag} />;
  return (
    <div className="prose-studio" data-streaming={streaming ? true : undefined}>
      {blocks.map((block, index) => {
        // A block's position is its identity: the text only grows at its end as pieces arrive.
        const key = index;
        switch (block.kind) {
          case 'paragraph':
            return (
              <p key={key}>
                {block.lines.map((line, number) => (
                  <Fragment key={number}>
                    {number > 0 ? <br /> : null}
                    {inline(line)}
                  </Fragment>
                ))}
              </p>
            );
          case 'heading': {
            const Heading = block.level === 1 ? 'h3' : block.level === 2 ? 'h4' : 'h5';
            return <Heading key={key}>{inline(block.content)}</Heading>;
          }
          case 'list': {
            const List = block.ordered ? 'ol' : 'ul';
            return (
              <List key={key} start={block.ordered && block.start !== 1 ? block.start : undefined}>
                {block.items.map((item, number) => (
                  <li key={number}>{inline(item)}</li>
                ))}
              </List>
            );
          }
          case 'code':
            return (
              <pre key={key}>
                <code>{block.text}</code>
              </pre>
            );
          case 'quote':
            return (
              <blockquote key={key}>
                {block.lines.map((line, number) => (
                  <Fragment key={number}>
                    {number > 0 ? <br /> : null}
                    {inline(line)}
                  </Fragment>
                ))}
              </blockquote>
            );
          case 'rule':
            return <hr key={key} />;
        }
      })}
    </div>
  );
}

/** Props of {@link InlineRuns}. */
interface InlineRunsProps {
  /** The runs to render. */
  runs: Inline[];
  /** The library's tags. */
  tags: ReadonlySet<string> | undefined;
  /** Opens the asset a tag names. */
  onTag: ((tag: string) => void) | undefined;
}

/**
 * Renders inline runs.
 *
 * @param props The component's props.
 * @returns The runs.
 */
function InlineRuns({ runs, tags, onTag }: InlineRunsProps) {
  return runs.map((run, index) => {
    switch (run.kind) {
      case 'text':
        return <Fragment key={index}>{run.text}</Fragment>;
      case 'code':
        return <code key={index}>{run.text}</code>;
      case 'strong':
        return (
          <strong key={index}>
            <InlineRuns runs={run.children} tags={tags} onTag={onTag} />
          </strong>
        );
      case 'em':
        return (
          <em key={index}>
            <InlineRuns runs={run.children} tags={tags} onTag={onTag} />
          </em>
        );
      case 'link':
        return (
          <a key={index} href={run.href} target="_blank" rel="noopener noreferrer" className="link">
            <InlineRuns runs={run.children} tags={tags} onTag={onTag} />
          </a>
        );
      case 'tag': {
        const known = tags?.has(run.tag.toLowerCase()) === true && onTag !== undefined;
        return known ? (
          <button
            key={index}
            type="button"
            className="tag-chip tag-chip-live"
            title={`Open @${run.tag} in the library`}
            onClick={() => {
              onTag(run.tag);
            }}
          >
            @{run.tag}
          </button>
        ) : (
          <span key={index} className="tag-chip">
            @{run.tag}
          </span>
        );
      }
    }
  });
}
