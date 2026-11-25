/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's table: rows under column headings, which the person can pick from where the table has an id.
 *
 * A table that answers is a radio group (`pick: one`) or a set of checkboxes (`pick: many`) laid
 * out as rows: each row leads with its control, named by the row's first cell, so it is chosen by
 * keyboard as any radio or checkbox is, and a click anywhere on the row chooses it too. The
 * answer is the first cell of each picked row, in the table's order, which is what the agent
 * named the row by.
 *
 * Numbers align right in tabular figures so a column of them compares by eye. A table wider
 * than its card scrolls inside its own frame, which takes the focus so the keyboard can scroll
 * it; the page never scrolls sideways.
 * @module
 */
import { isNumber, isString } from '../../../lib/narrow';
import { isScalar, show, text, type Scalar } from '../tree';
import { rowKeys } from '../values';
import { useInput, type ViewProps } from '../view';

/**
 * Renders a table.
 *
 * @param props The component's props.
 * @returns The table in its scrolling frame.
 */
export function Table({ node }: ViewProps) {
  const input = useInput(node);
  const picks = isString(node.props.id);
  const many = text(node, 'pick') === 'many';
  const given: unknown = node.props.columns;
  const columns = Array.isArray(given) ? given.filter(isString) : [];
  const rows: unknown = node.props.rows;
  const body = Array.isArray(rows) ? rows.filter((row): row is unknown[] => Array.isArray(row)) : [];
  const keys = rowKeys(node);
  // A column whose every cell is a number is set, and headed, from the right.
  const numeric = columns.map((_column, index) => body.length > 0 && body.every((row) => isNumber(row[index])));
  const chosen: unknown[] = Array.isArray(input.value) ? input.value : [input.value];

  /**
   * Picks a row, or with `pick: many` adds or removes it.
   *
   * @param key The row's first cell.
   * @param on Whether the row is now picked.
   */
  function pick(key: Scalar, on: boolean): void {
    if (!many) {
      input.set(key);
      return;
    }
    input.set(keys.filter((one) => (one === key ? on : chosen.includes(one))));
  }

  return (
    <div className="ui-table-frame" role="region" aria-label={input.label} tabIndex={0}>
      <table className="ui-table" data-picks={picks}>
        <thead>
          <tr>
            {picks ? (
              <th scope="col" className="ui-table-pick">
                <span className="sr-only">{many ? 'Picked' : 'Pick'}</span>
              </th>
            ) : null}
            {columns.map((column, index) => (
              <th key={column} scope="col" data-number={numeric[index] === true ? 'true' : undefined}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, index) => {
            const key: unknown = row[0];
            const picked = isScalar(key) && chosen.includes(key);
            return (
              // A table's rows never reorder; a row that answers is told apart by its first cell.
              <tr
                key={`${index}:${show(key)}`}
                data-picked={picks ? picked : undefined}
                onClick={
                  picks && !input.frozen && isScalar(key)
                    ? () => {
                        pick(key, many ? !picked : true);
                      }
                    : undefined
                }
              >
                {picks ? (
                  <td className="ui-table-pick">
                    <input
                      type={many ? 'checkbox' : 'radio'}
                      className="sr-only"
                      name={input.domId}
                      aria-label={show(key)}
                      checked={picked}
                      disabled={input.frozen}
                      onClick={(event) => {
                        // The row's own click would pick it a second time, which unpicks a checkbox.
                        event.stopPropagation();
                      }}
                      onChange={(event) => {
                        if (isScalar(key)) {
                          pick(key, event.target.checked);
                        }
                      }}
                    />
                    <span className="ui-check-mark" data-round={many ? undefined : 'true'} aria-hidden="true" />
                  </td>
                ) : null}
                {row.map((cell, column) => (
                  <td key={columns[column] ?? column} data-number={numeric[column] === true ? 'true' : undefined}>
                    {show(cell)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
