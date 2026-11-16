import { useEffect, useState } from "react";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");

export class ApiRequestError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiRequestError(payload?.detail || `API request failed (${response.status})`, response.status);
  }
  return response.json() as Promise<T>;
}

export type ApiState<T> = {
  data: T | null;
  loading: boolean;
  error: Error | null;
  reload: () => void;
};

export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    if (path === null) {
      setLoading(false);
      return () => controller.abort();
    }
    setLoading(true);
    requestJson<T>(path, controller.signal)
      .then((value) => setData(value))
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setData(null);
        setError(reason instanceof Error ? reason : new Error("Unexpected API error"));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, revision]);

  return { data, loading, error, reload: () => setRevision((value) => value + 1) };
}
