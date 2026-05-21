import { useCallback, useEffect, useState } from "react";
import { api, type WorkflowRun } from "../lib/api";

export function useWorkflowRuns(limit = 50) {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listWorkflowRuns(limit);
      setRuns(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch workflow runs");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const getRun = useCallback(
    async (runId: string): Promise<WorkflowRun | undefined> => {
      try {
        return await api.getWorkflowRun(runId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch workflow run");
      }
    },
    [],
  );

  return { runs, loading, error, refresh, getRun };
}
