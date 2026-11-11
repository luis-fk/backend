"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Locale } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";
import { type PlantsDictionary, plantsDictionary } from "@/plants/dictionary";
import {
  type Hours,
  MEASURES,
  type Measure,
  type Reading,
  formatValue,
  formatWhen,
  valueOf,
} from "@/plants/sensors";

// The chart measures its own width, so one unit is one pixel and its text keeps
// its size on a phone; 640 until the first measure.
const FIRST_WIDTH = 640;
const MIN_WIDTH = 300;
const LEFT = 36;
const RIGHT = 60;
const TOP = 10;
const AXIS = 22;
const LABEL_GAP = 14;
const HOUR = 3_600_000;

type SensorsTexts = PlantsDictionary["sensors"];

interface Point {
  time: number;
  value: number;
}

interface Panel {
  kind: "humidity" | "temperature";
  title: string;
  measures: Measure[];
  min: number;
  max: number;
  step: number;
  height: number;
  // None of its measures has a value in the period.
  empty: boolean;
}

interface Hover {
  index: number;
  x: number;
  y: number;
}

interface ChartProps {
  readings: Reading[];
  hours: Hours;
  visible: Record<Measure, boolean>;
  // When the period ends: the time axis covers the whole period, so a new device's
  // few hours sit at its right end.
  end: number;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : 0;
}

// Two readings further apart than this, as when the device was offline, aren't
// joined by a line.
function gapLimit(times: number[]): number {
  const steps = times.slice(1).map((time, i) => time - times[i]);
  return Math.max(3 * median(steps), 2 * HOUR);
}

// The stretches a measure's line joins: one ends at a gap or at an empty value.
function runsOf(
  readings: Reading[],
  times: number[],
  measure: Measure,
  limit: number,
): Point[][] {
  const runs: Point[][] = [];
  let run: Point[] = [];
  readings.forEach((reading, i) => {
    const value = valueOf(reading, measure);
    if (value === null || (i > 0 && times[i] - times[i - 1] > limit)) {
      if (run.length > 0) runs.push(run);
      run = [];
    }
    if (value !== null) run.push({ time: times[i], value });
  });
  if (run.length > 0) runs.push(run);
  return runs;
}

// The temperature axis: the period's range plus 2 °C on each side, in fives.
function temperatureRange(readings: Reading[]): [number, number] | null {
  const temperatures = readings
    .map((reading) => reading.temperature)
    .filter((value): value is number => value !== null);
  if (temperatures.length === 0) return null;
  return [
    Math.floor((Math.min(...temperatures) - 2) / 5) * 5,
    Math.ceil((Math.max(...temperatures) + 2) / 5) * 5,
  ];
}

function panelsOf(
  readings: Reading[],
  visible: Record<Measure, boolean>,
  t: SensorsTexts,
): Panel[] {
  const panels: Panel[] = [];
  const humidity = (["soil", "air"] as const).filter(
    (measure) => visible[measure],
  );
  if (humidity.length > 0) {
    panels.push({
      kind: "humidity",
      title: t.humidityPanel,
      measures: [...humidity],
      min: 0,
      max: 100,
      step: 25,
      height: 170,
      empty: readings.every((reading) =>
        humidity.every((measure) => valueOf(reading, measure) === null),
      ),
    });
  }
  if (visible.temp) {
    const range = temperatureRange(readings);
    panels.push({
      kind: "temperature",
      title: t.temperaturePanel,
      measures: ["temp"],
      min: range?.[0] ?? 0,
      max: range?.[1] ?? 40,
      step: 5,
      height: 130,
      empty: range === null,
    });
  }
  return panels;
}

// The time ticks: every 4 hours over a day, each midnight over a week, and every
// fifth day's midnight over 30 days, in the browser's time zone.
function ticksOf(start: number, end: number, hours: Hours): number[] {
  const ticks: number[] = [];
  const first = new Date(start);
  first.setMinutes(0, 0, 0);
  for (let time = first.getTime(); time <= end; time += HOUR) {
    if (time < start) continue;
    const date = new Date(time);
    const hour = date.getHours();
    const tick =
      hours === 24
        ? hour % 4 === 0
        : hour === 0 && (hours === 168 || date.getDate() % 5 === 0);
    if (tick) ticks.push(time);
  }
  return ticks;
}

function tickLabel(
  time: number,
  hours: Hours,
  lang: Locale,
  t: SensorsTexts,
): string {
  const date = new Date(time);
  if (hours === 24) return t.hourTick(date);
  if (hours === 168) {
    return date.toLocaleDateString(lang, { weekday: "short", day: "numeric" });
  }
  return date.toLocaleDateString(lang, { day: "numeric", month: "numeric" });
}

// The index of the reading closest in time.
function nearest(times: number[], time: number): number {
  let low = 0;
  let high = times.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (times[middle] < time) low = middle + 1;
    else high = middle;
  }
  if (low > 0 && time - times[low - 1] < times[low] - time) return low - 1;
  return low;
}

export default function SensorsChart({
  readings,
  hours,
  visible,
  end,
}: ChartProps): React.ReactElement {
  const lang = useLocale();
  const t = plantsDictionary[lang].sensors;
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(FIRST_WIDTH);
  const [hover, setHover] = useState<Hover | null>(null);
  const tip = useRef<HTMLDivElement>(null);

  const times = useMemo(
    () => readings.map((reading) => Date.parse(reading.time)),
    [readings],
  );
  const start = Math.min(end - hours * HOUR, times[0]);
  const span = end - start;
  const plotWidth = width - LEFT - RIGHT;
  const x = (time: number): number =>
    LEFT + (span > 0 ? (time - start) / span : 0.5) * plotWidth;

  const panels = useMemo(() => {
    const limit = gapLimit(times);
    return panelsOf(readings, visible, t).map((panel) => ({
      panel,
      runs: panel.measures.map((measure) => ({
        measure,
        runs: runsOf(readings, times, measure, limit),
      })),
    }));
  }, [readings, times, visible, t]);
  // Labels too close for their text keep every second, or every third, tick.
  const ticks = useMemo(() => {
    const all = ticksOf(start, end, hours);
    const spacing =
      all.length > 1 ? ((all[1] - all[0]) / (span || 1)) * plotWidth : Infinity;
    const every = Math.max(1, Math.ceil((hours === 168 ? 56 : 36) / spacing));
    return all.filter((_, i) => i % every === 0);
  }, [start, end, span, hours, plotWidth]);

  useEffect(() => {
    const chart = box.current;
    if (!chart) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(MIN_WIDTH, Math.round(entry.contentRect.width))),
    );
    observer.observe(chart);
    return () => observer.disconnect();
  }, []);

  function onPointer(event: React.PointerEvent<SVGRectElement>): void {
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg || !box.current) return;
    const svgBox = svg.getBoundingClientRect();
    const svgX = ((event.clientX - svgBox.left) * width) / svgBox.width;
    const time = start + ((svgX - LEFT) / plotWidth) * span;
    const chartBox = box.current.getBoundingClientRect();
    const pointerX = event.clientX - chartBox.left;
    setHover({
      index: nearest(times, time),
      x: pointerX,
      y: event.clientY - chartBox.top,
    });
  }

  // The tooltip opens beside the pointer, on whichever side it fits, and never
  // past the chart's edges; it's placed before the browser paints it.
  useLayoutEffect(() => {
    const chart = box.current;
    const element = tip.current;
    if (!hover || !chart || !element) return;
    const room = chart.clientWidth;
    const size = element.offsetWidth;
    let left = hover.x + 14;
    if (left + size > room) left = hover.x - 14 - size;
    element.style.left = `${Math.max(0, Math.min(left, room - size))}px`;
  }, [hover]);

  const hovered = hover ? readings[hover.index] : null;
  const lastDrawn = panels.findLastIndex(({ panel }) => !panel.empty);

  return (
    <div className="plants-sensors-chart" ref={box}>
      {panels.map(({ panel, runs }, index) => {
        // The time labels go under the lowest panel that draws a chart.
        const bottom = index === lastDrawn;
        const height = panel.height + (bottom ? AXIS : 6);
        const y = (value: number): number =>
          TOP +
          (1 - (value - panel.min) / (panel.max - panel.min)) *
            (panel.height - TOP - 4);
        const grid: number[] = [];
        for (let value = panel.min; value <= panel.max; value += panel.step) {
          grid.push(value);
        }

        // Each measure's latest value at the line's end, pushed apart when close.
        const labels = panel.measures
          .flatMap((measure) => {
            const latest = readings.findLast(
              (reading) => valueOf(reading, measure) !== null,
            );
            const value = latest ? valueOf(latest, measure) : null;
            return value === null
              ? []
              : [
                  {
                    measure,
                    y: y(value),
                    text: `${value}${measure === "temp" ? "°" : "%"}`,
                  },
                ];
          })
          .sort((a, b) => a.y - b.y);
        labels.forEach((label, i) => {
          if (i > 0 && label.y - labels[i - 1].y < LABEL_GAP) {
            label.y = labels[i - 1].y + LABEL_GAP;
          }
        });

        return (
          <section key={panel.kind} className="plants-sensors-panel">
            <h2 className="plants-sensors-panel-title">{panel.title}</h2>
            {panel.empty ? (
              <p className="muted">{t.noData}</p>
            ) : (
              <svg
                className="plants-sensors-svg"
                viewBox={`0 0 ${width} ${height}`}
                role="img"
                aria-label={panel.title}
              >
                <g className="plants-sensors-grid">
                  {grid.map((value) => (
                    <g key={value}>
                      <line
                        x1={LEFT}
                        x2={width - RIGHT}
                        y1={y(value)}
                        y2={y(value)}
                      />
                      <text x={LEFT - 6} y={y(value) + 4} textAnchor="end">
                        {value}
                      </text>
                    </g>
                  ))}
                </g>
                {bottom && (
                  <g className="plants-sensors-grid">
                    {ticks.map((time) => (
                      <g key={time}>
                        <line
                          x1={x(time)}
                          x2={x(time)}
                          y1={panel.height - 4}
                          y2={panel.height}
                        />
                        <text
                          x={x(time)}
                          y={panel.height + 15}
                          textAnchor="middle"
                        >
                          {tickLabel(time, hours, lang, t)}
                        </text>
                      </g>
                    ))}
                  </g>
                )}
                {runs.map(({ measure, runs: stretches }) =>
                  stretches.map((run) =>
                    run.length === 1 ? (
                      <circle
                        key={`${measure}-${run[0].time}`}
                        className={`plants-sensors-point plants-sensors-${measure}`}
                        cx={x(run[0].time)}
                        cy={y(run[0].value)}
                        r={2.5}
                      />
                    ) : (
                      <path
                        key={`${measure}-${run[0].time}`}
                        className={`plants-sensors-line plants-sensors-${measure}`}
                        d={run
                          .map(
                            (point, i) =>
                              `${i === 0 ? "M" : "L"}${x(point.time).toFixed(1)} ${y(point.value).toFixed(1)}`,
                          )
                          .join("")}
                      />
                    ),
                  ),
                )}
                <g className="plants-sensors-end">
                  {labels.map((label) => (
                    <g key={label.measure}>
                      <line
                        className={`plants-sensors-line plants-sensors-${label.measure}`}
                        x1={width - RIGHT + 8}
                        x2={width - RIGHT + 16}
                        y1={label.y}
                        y2={label.y}
                      />
                      <text x={width - RIGHT + 20} y={label.y + 4}>
                        {label.text}
                      </text>
                    </g>
                  ))}
                </g>
                {hover && hovered && (
                  <g className="plants-sensors-cross">
                    <line
                      x1={x(times[hover.index])}
                      x2={x(times[hover.index])}
                      y1={TOP}
                      y2={panel.height - 4}
                    />
                    {panel.measures.map((measure) => {
                      const value = valueOf(hovered, measure);
                      return value === null ? null : (
                        <circle
                          key={measure}
                          className={`plants-sensors-dot plants-sensors-${measure}`}
                          cx={x(times[hover.index])}
                          cy={y(value)}
                          r={4.5}
                        />
                      );
                    })}
                  </g>
                )}
                <rect
                  className="plants-sensors-hit"
                  x={LEFT}
                  y={0}
                  width={plotWidth}
                  height={panel.height}
                  onPointerMove={onPointer}
                  onPointerDown={onPointer}
                  onPointerLeave={() => setHover(null)}
                />
              </svg>
            )}
          </section>
        );
      })}
      {hover && hovered && (
        <div
          ref={tip}
          className="plants-sensors-tip"
          style={{ left: hover.x + 14, top: hover.y }}
        >
          <p className="plants-sensors-tip-when">
            {formatWhen(hovered.time, lang)}
          </p>
          {MEASURES.filter((measure) => visible[measure]).map((measure) => (
            <p key={measure} className="plants-sensors-tip-row">
              <span
                className={`plants-sensors-swatch plants-sensors-${measure}`}
                aria-hidden="true"
              />
              <span>{t.measures[measure]}</span>
              <b>
                {formatValue(valueOf(hovered, measure), measure, lang)}
                {measure === "soil" &&
                  ` ${t.rawReading(hovered.soil_raw.toLocaleString(lang))}`}
              </b>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
