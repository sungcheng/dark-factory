import { useState, useEffect, useRef, useCallback } from "react";

export interface UsePollingOptions {
  interval?: number;
  enabled?: boolean;
  onError?: (error: Error) => void;
}

export interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  options?: UsePollingOptions
): UsePollingResult<T> {
  const { interval = 3000, enabled = true, onError } = options ?? {};
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const mountedRef = useRef<boolean>(true);
  const fetchFnRef = useRef(fetchFn);
  const onErrorRef = useRef(onError);

  fetchFnRef.current = fetchFn;
  onErrorRef.current = onError;

  const refetch = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      const result = await fetchFnRef.current();
      if (mountedRef.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        const fetchError = err instanceof Error ? err : new Error(String(err));
        setError(fetchError);
        if (onErrorRef.current) {
          onErrorRef.current(fetchError);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled) {
      return () => {
        mountedRef.current = false;
      };
    }

    void refetch();

    const intervalId = setInterval(() => {
      void refetch();
    }, interval);

    return () => {
      mountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [enabled, interval, refetch]);

  return { data, loading, error, refetch };
}
