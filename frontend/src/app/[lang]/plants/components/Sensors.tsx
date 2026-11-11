"use client";

import axios from "axios";
import { useEffect, useState } from "react";
import { logger } from "@/app/api/log/client-logger";
import { useSession } from "@/app/actions/useSession";
import { commonDictionary } from "@/app/dictionary";
import { useLocale } from "@/app/useLocale";
import SensorsChart from "@/plants/components/SensorsChart";
import { plantsDictionary } from "@/plants/dictionary";
import {
  type Device,
  HOURS,
  type Hours,
  MEASURES,
  type Measure,
  type Reading,
  formatValue,
  formatWhen,
  valueOf,
} from "@/plants/sensors";
import "@/plants/css/sensors.css";

// The backend answers 401 once the session's token has expired, or when the
// person was blocked in the admin; only signing in again can help.
function expired(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}

// The readings of one (device, period) pair: a change of either shows the
// loading text until its own readings arrive.
interface Loaded {
  key: string;
  readings: Reading[];
  // When they arrived: the end of the chart's period.
  end: number;
}

export default function Sensors(): React.ReactElement {
  const lang = useLocale();
  const t = plantsDictionary[lang].sensors;
  const common = commonDictionary[lang];
  const session = useSession("plants");
  const token = session?.token;
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  const [devices, setDevices] = useState<Device[] | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [hours, setHours] = useState<Hours>(168);
  const [visible, setVisible] = useState<Record<Measure, boolean>>({
    soil: true,
    air: true,
    temp: true,
  });
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const deviceId = picked ?? devices?.[0]?.id ?? null;
  const key = `${deviceId}:${hours}`;

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    axios
      .get<Device[]>(`${serverUrl}/api/plants/devices/`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      .then((response) => setDevices(response.data))
      .catch((error: unknown) => {
        if (axios.isCancel(error)) return;
        logger.error("Failed to fetch the plants' devices", { error });
        setFailure(expired(error) ? common.session.expired : t.loadFailed);
      });
    return () => controller.abort();
  }, [token, serverUrl, common, t]);

  useEffect(() => {
    if (!token || deviceId === null) return;
    const controller = new AbortController();
    const loading = `${deviceId}:${hours}`;
    axios
      .get<{ readings: Reading[] }>(
        `${serverUrl}/api/plants/devices/${deviceId}/readings/`,
        {
          params: { hours },
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        },
      )
      .then((response) => {
        const readings = response.data.readings;
        const latest = readings.at(-1);
        setLoaded({
          key: loading,
          readings,
          end: Math.max(Date.now(), latest ? Date.parse(latest.time) : 0),
        });
        setFailure(null);
      })
      .catch((error: unknown) => {
        if (axios.isCancel(error)) return;
        logger.error("Failed to fetch a device's readings", {
          deviceId,
          error,
        });
        setFailure(expired(error) ? common.session.expired : t.loadFailed);
      });
    return () => controller.abort();
  }, [token, serverUrl, deviceId, hours, common, t]);

  const current = loaded?.key === key ? loaded : null;
  const readings = current?.readings ?? null;
  const last = readings?.at(-1);

  function toggle(measure: Measure): void {
    setVisible((current) => ({ ...current, [measure]: !current[measure] }));
  }

  function chartOrState(): React.ReactNode {
    if (failure) return <p className="muted">{failure}</p>;
    if (readings === null) return <p className="muted">{t.loading}</p>;
    if (readings.length === 0) return <p className="muted">{t.noReadings}</p>;
    if (!MEASURES.some((measure) => visible[measure])) {
      return <p className="muted">{t.pickOne}</p>;
    }
    return (
      <SensorsChart
        readings={readings}
        hours={hours}
        visible={visible}
        end={current?.end ?? Date.parse(readings[readings.length - 1].time)}
      />
    );
  }

  function content(): React.ReactNode {
    if (session === null)
      return <p className="muted">{common.session.loadFailed}</p>;
    if (devices === null) {
      return <p className="muted">{failure ?? t.loading}</p>;
    }
    if (devices.length === 0) return <p className="muted">{t.noDevices}</p>;

    return (
      <>
        <div className="plants-sensors-controls">
          <div className="plants-sensors-control">
            <span
              className="plants-sensors-control-label"
              id="plants-sensors-plant"
            >
              {t.plant}
            </span>
            <div
              className="plants-sensors-segmented"
              role="group"
              aria-labelledby="plants-sensors-plant"
            >
              {devices.map((device) => (
                <button
                  key={device.id}
                  type="button"
                  aria-pressed={device.id === deviceId}
                  onClick={() => setPicked(device.id)}
                >
                  {device.nickname}
                </button>
              ))}
            </div>
          </div>
          <div className="plants-sensors-control">
            <span
              className="plants-sensors-control-label"
              id="plants-sensors-period"
            >
              {t.period}
            </span>
            <div
              className="plants-sensors-segmented"
              role="group"
              aria-labelledby="plants-sensors-period"
            >
              {HOURS.map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={option === hours}
                  onClick={() => setHours(option)}
                >
                  {t.periods[option]}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div
          className="plants-sensors-chips"
          role="group"
          aria-label={t.measuresLabel}
        >
          {MEASURES.map((measure) => (
            <button
              key={measure}
              type="button"
              className="plants-sensors-chip"
              aria-pressed={visible[measure]}
              onClick={() => toggle(measure)}
            >
              <span
                className={`plants-sensors-swatch plants-sensors-${measure}`}
                aria-hidden="true"
              />
              {t.measures[measure]}
            </button>
          ))}
        </div>
        {last && (
          <p className="plants-sensors-last">
            {t.lastReading(formatWhen(last.time, lang))} {t.soil}{" "}
            <b>{formatValue(valueOf(last, "soil"), "soil", lang)}</b> · {t.air}{" "}
            <b>{formatValue(valueOf(last, "air"), "air", lang)}</b> ·{" "}
            <b>{formatValue(valueOf(last, "temp"), "temp", lang)}</b>
          </p>
        )}
        {chartOrState()}
      </>
    );
  }

  return (
    <main className="page plants-sensors">
      <div className="page-header">
        <h1 className="page-title">{t.title}</h1>
      </div>
      {content()}
    </main>
  );
}
