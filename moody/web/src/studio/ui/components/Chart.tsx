/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * A card's chart: one series as ranked bars, a line or an area, or the shares of a whole.
 *
 * The form follows what the reader has to do with the values. Bars lie on one baseline with the
 * value at each tip, so magnitudes compare exactly. A line, or an area, runs over an ordered
 * axis, read through a crosshair that snaps to the nearest point by pointer or by the arrow
 * keys. Shares of one whole are a segmented bar with its legend, never a pie: at most six
 * parts, the tail folded into "Other" (`chart.ts`).
 *
 * The data is the agent's, so the marks are the intelligence's lavender, one hue for a series;
 * the parts of a share bar step down one ramp of it, a step per rank, light to dark. What the
 * person points at is lime: a `highlight` that follows one of the card's inputs emphasizes that
 * value and lets the others recede. Text never wears a mark's color, so every label reads the
 * same in any palette. A hidden table carries the same values for assistive technology.
 *
 * The plot of a line is laid out for the width it is shown at (`useWidth`), not scaled to it,
 * so its text keeps its size on a phone.
 * @module
 */
import { useState, type KeyboardEvent, type PointerEvent } from 'react';
import { amount, linePath, parts, points, share, ticks, type Point } from '../chart';
import { useCard } from '../context';
import { useWidth } from '../hooks';
import { bound, isScalar, text } from '../tree';
import type { ViewProps } from '../view';

/** The height of a line's plot, in CSS pixels. */
const PLOT_HEIGHT = 168;

/** The room a line's plot leaves above, right, and below for its labels. */
const MARGIN = { top: 14, right: 14, bottom: 24 };

/** About how wide one character of an axis label is, to leave room for the widest tick. */
const TICK_CHARACTER = 6.4;

/** The least room one label of the horizontal axis takes before the next. */
const X_LABEL_ROOM = 64;

/** How wide a part of a share bar has to be for its share to be printed in it. */
const SHARE_LABEL_ROOM = 40;

/** Props of the chart's forms. */
interface FormProps {
  /** The series. */
  data: Point[];
  /** The unit its values are written with. */
  unit: string | null;
  /** Whether a point is the one the card emphasizes; `null` where it emphasizes none. */
  emphasis: ((point: Point) => boolean) | null;
}

/**
 * Says how a mark stands to the card's emphasis.
 *
 * @param emphasis The card's emphasis.
 * @param point The mark's point.
 * @returns `on` for the emphasized mark, `off` for the others, nothing where none is emphasized.
 */
function standing(emphasis: FormProps['emphasis'], point: Point): 'on' | 'off' | undefined {
  return emphasis === null ? undefined : emphasis(point) ? 'on' : 'off';
}

/**
 * Renders a chart.
 *
 * @param props The component's props.
 * @returns The figure.
 */
export function Chart({ node }: ViewProps) {
  const card = useCard();
  const data = points(node);
  const kind = text(node, 'kind') ?? 'bar';
  const unit = text(node, 'unit');
  const label = text(node, 'label');
  const highlighted = bound(node, 'highlight', card.state);
  const chosen = (Array.isArray(highlighted) ? highlighted : [highlighted]).filter(isScalar).map(String);
  const emphasis =
    chosen.length > 0 && data.some((point) => chosen.includes(point.label))
      ? (point: Point): boolean => chosen.includes(point.label)
      : null;
  const form = { data, unit, emphasis };
  return (
    <figure className="ui-chart">
      {label === null ? null : <figcaption className="ui-label">{label}</figcaption>}
      {data.length === 0 ? (
        <p className="ui-text-muted">Nothing to chart yet.</p>
      ) : kind === 'share' ? (
        <Share {...form} />
      ) : kind === 'bar' ? (
        <Bars {...form} />
      ) : (
        <Line {...form} area={kind === 'area'} name={label ?? 'Chart'} />
      )}
      <table className="sr-only">
        <caption>{label ?? 'Chart'}</caption>
        <tbody>
          {data.map((point, index) => (
            // A chart's points never reorder, and two of them may share a label.
            <tr key={`${index}:${point.label}`}>
              <th scope="row">{point.label}</th>
              <td>{amount(point.value, unit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

/**
 * Renders the series as bars on one baseline, each with its name before it and its value at its tip.
 *
 * @param props The component's props.
 * @returns The bars.
 */
function Bars({ data, unit, emphasis }: FormProps) {
  const most = Math.max(...data.map((point) => point.value), 0);
  return (
    <ul className="ui-bars" aria-hidden="true">
      {data.map((point, index) => (
        <li key={`${index}:${point.label}`} className="ui-bar-row" data-emphasis={standing(emphasis, point)}>
          <span className="ui-bar-name">{point.label}</span>
          <span className="ui-bar-track">
            <span className="ui-bar" style={{ width: `${most > 0 ? (Math.max(point.value, 0) / most) * 100 : 0}%` }} />
          </span>
          <span className="ui-bar-value">{amount(point.value, unit)}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Renders one whole as a segmented bar, each part's share printed in it where it fits, over a
 * legend that names every part with its amount.
 *
 * @param props The component's props.
 * @returns The bar and its legend.
 */
function Share({ data, unit, emphasis }: FormProps) {
  const [bar, width] = useWidth<HTMLDivElement>();
  const shown = parts(data);
  const whole = shown.reduce((sum, part) => sum + part.value, 0);
  return (
    <div className="ui-share-chart" aria-hidden="true">
      <div ref={bar} className="ui-share">
        {shown.map((part, index) => (
          <span
            key={part.label}
            className="ui-share-part"
            data-step={index}
            data-emphasis={standing(emphasis, part)}
            style={{ flexGrow: part.value }}
          >
            {(part.value / whole) * width >= SHARE_LABEL_ROOM ? share(part.value, whole) : null}
          </span>
        ))}
      </div>
      <ul className="ui-legend">
        {shown.map((part, index) => (
          <li key={part.label} className="ui-legend-row" data-emphasis={standing(emphasis, part)}>
            <span className="ui-legend-key" data-step={index} data-emphasis={standing(emphasis, part)} />
            <span className="ui-legend-name">{part.label}</span>
            <span className="ui-legend-value">
              {amount(part.value, unit)}
              {(part.value / whole) * width >= SHARE_LABEL_ROOM ? null : ` · ${share(part.value, whole)}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Props of {@link Line}. */
interface LineProps extends FormProps {
  /** Whether the line is drawn over a wash down to the baseline. */
  area: boolean;
  /** What the chart is called, for assistive technology. */
  name: string;
}

/**
 * Renders the series as a line over its points in order, read through a crosshair.
 *
 * @param props The component's props.
 * @returns The plot.
 */
function Line({ data, unit, emphasis, area, name }: LineProps) {
  const [frame, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const values = data.map((point) => point.value);
  const marks = ticks(Math.min(0, ...values), Math.max(...values));
  const low = marks[0] ?? 0;
  const high = marks.at(-1) ?? 1;
  const left = Math.max(...marks.map((mark) => amount(mark, unit, true).length)) * TICK_CHARACTER + 10;
  const plotWidth = Math.max(width - left - MARGIN.right, 1);
  const plotHeight = PLOT_HEIGHT - MARGIN.top - MARGIN.bottom;
  const x = (index: number): number => left + (data.length > 1 ? (index / (data.length - 1)) * plotWidth : plotWidth / 2);
  const y = (value: number): number => MARGIN.top + (1 - (value - low) / (high - low)) * plotHeight;
  const coordinates = data.map((point, index): [number, number] => [x(index), y(point.value)]);
  const every = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(plotWidth / X_LABEL_ROOM))));
  const last = data.length - 1;
  const read = active === null ? null : (data[active] ?? null);

  /**
   * Snaps the crosshair to the point nearest the pointer.
   *
   * @param event The pointer's move over the plot.
   */
  function onPointerMove(event: PointerEvent<SVGSVGElement>): void {
    const offset = event.clientX - event.currentTarget.getBoundingClientRect().left - left;
    const nearest = data.length > 1 ? Math.round((offset / plotWidth) * (data.length - 1)) : 0;
    setActive(Math.min(last, Math.max(0, nearest)));
  }

  /**
   * Moves the crosshair by the arrow keys.
   *
   * @param event The key press on the plot.
   */
  function onKeyDown(event: KeyboardEvent): void {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (step !== 0) {
      event.preventDefault();
      setActive((current) => Math.min(last, Math.max(0, (current ?? (step > 0 ? -1 : data.length)) + step)));
    } else if (event.key === 'Escape') {
      setActive(null);
    }
  }

  return (
    <div
      ref={frame}
      className="ui-plot"
      role="group"
      tabIndex={0}
      aria-label={`${name}: ${data.length} values. Use the left and right arrow keys to read each one.`}
      onKeyDown={onKeyDown}
      onBlur={() => {
        setActive(null);
      }}
    >
      {width === 0 ? null : (
        <svg
          width={width}
          height={PLOT_HEIGHT}
          aria-hidden="true"
          onPointerMove={onPointerMove}
          onPointerLeave={() => {
            setActive(null);
          }}
        >
          {marks.map((mark) => (
            <g key={mark}>
              <line className="ui-plot-grid" x1={left} x2={left + plotWidth} y1={y(mark)} y2={y(mark)} />
              <text className="ui-plot-tick" x={left - 8} y={y(mark)} textAnchor="end" dominantBaseline="middle">
                {amount(mark, unit, true)}
              </text>
            </g>
          ))}
          {data.map((point, index) =>
            index % every === 0 || index === last ? (
              // A label too near the last one gives way to it.
              index !== last && last - index < every / 2 ? null : (
                <text
                  key={`${index}:${point.label}`}
                  className="ui-plot-tick"
                  x={x(index)}
                  y={PLOT_HEIGHT - 6}
                  textAnchor={index === 0 ? 'start' : index === last ? 'end' : 'middle'}
                >
                  {point.label}
                </text>
              )
            ) : null,
          )}
          {area && coordinates.length > 1 ? (
            <path
              className="ui-plot-area"
              d={`${linePath(coordinates)} L${x(last).toFixed(1)} ${y(low).toFixed(1)} L${x(0).toFixed(1)} ${y(low).toFixed(1)} Z`}
            />
          ) : null}
          <path className="ui-plot-line" d={linePath(coordinates)} />
          {data.map((point, index) => {
            const emphasized = standing(emphasis, point) === 'on';
            const [cx, cy] = coordinates[index] ?? [0, 0];
            // The end of the line and what the card emphasizes are the only points drawn and labeled.
            return emphasized || (index === last && emphasis === null) ? (
              <g key={`${index}:${point.label}`}>
                <circle className="ui-plot-dot" data-emphasis={emphasized ? 'on' : undefined} cx={cx} cy={cy} r={4} />
                <text
                  className="ui-plot-value"
                  x={cx}
                  y={cy - 10}
                  textAnchor={index === 0 ? 'start' : index === last ? 'end' : 'middle'}
                >
                  {amount(point.value, unit)}
                </text>
              </g>
            ) : null;
          })}
          {active === null || read === null ? null : (
            <g>
              <line className="ui-plot-cross" x1={x(active)} x2={x(active)} y1={MARGIN.top} y2={MARGIN.top + plotHeight} />
              <circle className="ui-plot-dot" cx={x(active)} cy={y(read.value)} r={4} />
            </g>
          )}
        </svg>
      )}
      {active === null || read === null ? null : (
        <div
          className="ui-tooltip"
          style={{
            top: Math.max(0, y(read.value) - 44),
            ...(x(active) > width / 2 ? { right: width - x(active) + 10 } : { left: x(active) + 10 }),
          }}
        >
          <strong>{amount(read.value, unit)}</strong>
          <span>{read.label}</span>
        </div>
      )}
      <p className="sr-only" aria-live="polite">
        {read === null ? '' : `${read.label}: ${amount(read.value, unit)}`}
      </p>
    </div>
  );
}
