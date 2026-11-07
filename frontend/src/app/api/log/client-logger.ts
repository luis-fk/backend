"use client";

type LogLevel = "log" | "info" | "warn" | "error";

const sendLogToServer = (
  level: LogLevel,
  message: unknown,
  optionalParams: unknown[],
) => {
  if (typeof window === "undefined" || typeof fetch === "undefined") {
    return;
  }

  try {
    const blob = new Blob(
      [
        JSON.stringify({
          level,
          message,
          optionalParams,
          timestamp: new Date().toISOString(),
          url: window.location.href,
        }),
      ],
      { type: "application/json" },
    );

    navigator.sendBeacon("/api/log", blob);
  } catch (error) {
    console.error("Failed to send log to server:", error);
  }
};

const createLogger =
  (level: LogLevel) =>
  (message: unknown, ...optionalParams: unknown[]) => {
    if (process.env.NODE_ENV === "development") {
      console[level](message, ...optionalParams);
    }
    sendLogToServer(level, message, optionalParams);
  };

export const logger = {
  log: createLogger("log"),
  info: createLogger("info"),
  warn: createLogger("warn"),
  error: createLogger("error"),
};
