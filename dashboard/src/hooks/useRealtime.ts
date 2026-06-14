import { useState, useEffect, useCallback } from "react";

/**
 * Hook for adaptive polling
 * @param fetchFn The async function to fetch data
 * @param intervalMs The polling interval in milliseconds
 * @param enabled Whether polling is active
 */
export function useRealtime<T>(fetchFn: () => Promise<T>, intervalMs: number = 5000, enabled: boolean = true) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchData = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Polling error:", err);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    let timerId: ReturnType<typeof setTimeout> | undefined;
    let intervalId: number | undefined;

    if (enabled) {
      timerId = setTimeout(() => {
        fetchData().catch(err => console.error("Initial fetch failed", err));
      }, 0);

      intervalId = window.setInterval(() => {
        fetchData().catch(err => console.error("Interval fetch failed", err));
      }, intervalMs);
    }

    // Cleanup
    return () => {
      if (timerId) {
        clearTimeout(timerId);
      }
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [fetchData, intervalMs, enabled]);

  return { data, loading, error, lastUpdated, refetch: fetchData };
}

