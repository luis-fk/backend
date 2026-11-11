import type { Locale } from "@/app/i18n";

// The types of the plants sensors API (backend/plants/api/sensors) and the tab's
// choices.
export type Measure = "soil" | "air" | "temp";
export type Hours = 24 | 168 | 720;

export const MEASURES: readonly Measure[] = ["soil", "air", "temp"];
export const HOURS: readonly Hours[] = [24, 168, 720];

export interface Device {
  id: number;
  nickname: string;
  last_reading_at: string | null;
}

export interface Reading {
  time: string;
  soil_percent: number | null;
  soil_raw: number;
  air_humidity: number | null;
  temperature: number | null;
}

// A reading's value for a measure, or null when it came without it.
export function valueOf(reading: Reading, measure: Measure): number | null {
  if (measure === "soil") return reading.soil_percent;
  if (measure === "air") return reading.air_humidity;
  return reading.temperature;
}

// A measure's value as people read it: "54%", "21 °C", or "–" when empty.
export function formatValue(
  value: number | null,
  measure: Measure,
  lang: Locale,
): string {
  if (value === null) return "–";
  const number = value.toLocaleString(lang);
  // A no-break space keeps the unit with its number.
  return measure === "temp" ? `${number}\u00a0°C` : `${number}%`;
}

// A reading's time, in the browser's time zone.
export function formatWhen(time: string, lang: Locale): string {
  return new Date(time).toLocaleString(lang, {
    weekday: "short",
    day: "numeric",
    month: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
