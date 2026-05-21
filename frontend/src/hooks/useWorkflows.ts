import { useCallback, useEffect, useState } from "react";
import { api, type Workflow, type WorkflowCreateData } from "../lib/api";

export function useWorkflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch workflows");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const create = useCallback(
    async (data: WorkflowCreateData): Promise<Workflow | undefined> => {
      try {
        const workflow = await api.createWorkflow(data);
        setWorkflows((prev) => [workflow, ...prev]);
        return workflow;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create workflow");
      }
    },
    [],
  );

  const update = useCallback(
    async (id: string, data: WorkflowCreateData): Promise<Workflow | undefined> => {
      try {
        const workflow = await api.updateWorkflow(id, data);
        setWorkflows((prev) => prev.map((w) => (w.id === id ? workflow : w)));
        return workflow;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update workflow");
      }
    },
    [],
  );

  const remove = useCallback(
    async (id: string) => {
      try {
        await api.deleteWorkflow(id);
        setWorkflows((prev) => prev.filter((w) => w.id !== id));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete workflow");
      }
    },
    [],
  );

  const run = useCallback(
    async (id: string, parameters?: Record<string, unknown>) => {
      try {
        const result = await api.runWorkflow(id, parameters);
        await refresh();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to run workflow");
      }
    },
    [refresh],
  );

  return { workflows, loading, error, refresh, create, update, remove, run };
}
