import { useState } from "react";
import { Save, Play, ArrowLeft } from "lucide-react";
import { type Workflow, type WorkflowCreateData, type WorkflowBlock, type WorkflowRun, type Profile } from "../lib/api";
import { WorkflowBuilder } from "./WorkflowBuilder";

interface Props {
  workflow: Workflow | null;
  profiles: Profile[];
  onSave: (data: WorkflowCreateData) => Promise<Workflow | undefined>;
  onRun: (id: string, parameters?: Record<string, unknown>) => Promise<WorkflowRun | undefined>;
  onCancel: () => void;
}

export function WorkflowEditor({ workflow, profiles, onSave, onRun, onCancel }: Props) {
  const [title, setTitle] = useState(workflow?.title || "");
  const [description, setDescription] = useState(workflow?.description || "");
  const [profileId, setProfileId] = useState(workflow?.profile_id || "");
  const [runWith, setRunWith] = useState<"agent" | "script">(workflow?.run_with || "agent");
  const [aiFallback, setAiFallback] = useState(workflow?.ai_fallback ?? true);
  const [adaptiveCaching, setAdaptiveCaching] = useState(workflow?.adaptive_caching ?? true);
  const [blocks, setBlocks] = useState<WorkflowBlock[]>(workflow?.definition?.blocks || []);
  const [saving, setSaving] = useState(false);
  const [lastRun, setLastRun] = useState<WorkflowRun | null>(null);
  const [running, setRunning] = useState(false);

  const handleSave = async () => {
    if (!title || !profileId) return;
    setSaving(true);
    try {
      await onSave({
        title,
        description: description || null,
        profile_id: profileId,
        definition: { blocks },
        run_with: runWith,
        ai_fallback: aiFallback,
        adaptive_caching: adaptiveCaching,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!workflow) return;
    setRunning(true);
    try {
      const result = await onRun(workflow.id);
      if (result) setLastRun(result);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="text-gray-500 hover:text-gray-300">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Workflow title"
            className="text-sm font-medium bg-transparent border-none outline-none placeholder-gray-600"
          />
        </div>
        <div className="flex items-center gap-2">
          {workflow && (
            <button
              onClick={handleRun}
              disabled={running || workflow.status === "running"}
              className="text-xs px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white flex items-center gap-1 disabled:opacity-50"
            >
              <Play className="h-3 w-3" /> {running ? "Running..." : "Run"}
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !title || !profileId}
            className="text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-1 disabled:opacity-50"
          >
            <Save className="h-3 w-3" /> {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Profile</label>
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              className="w-full text-sm bg-surface-0 border border-border rounded px-2 py-1.5"
            >
              <option value="">Select a profile...</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.platform})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Description</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="w-full text-sm bg-surface-0 border border-border rounded px-2 py-1.5"
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Execution:</label>
            <select
              value={runWith}
              onChange={(e) => setRunWith(e.target.value as "agent" | "script")}
              className="text-sm bg-surface-0 border border-border rounded px-2 py-1"
            >
              <option value="agent">Agent (LLM)</option>
              <option value="script">Script (Cached)</option>
            </select>
          </div>
          <label className="flex items-center gap-1.5 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={aiFallback}
              onChange={(e) => setAiFallback(e.target.checked)}
              className="rounded"
            />
            AI Fallback
          </label>
          <label className="flex items-center gap-1.5 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={adaptiveCaching}
              onChange={(e) => setAdaptiveCaching(e.target.checked)}
              className="rounded"
            />
            Adaptive Caching
          </label>
        </div>

        <div>
          <div className="text-xs text-gray-400 mb-2 font-medium">Blocks</div>
          <WorkflowBuilder blocks={blocks} onChange={setBlocks} />
        </div>

        {lastRun && (
          <div className="border border-border rounded-lg bg-surface-1">
            <div className="px-3 py-2 border-b border-border">
              <span className="text-xs font-medium text-gray-400">Last Run Result</span>
            </div>
            <div className="p-3 space-y-2">
              <div className="flex items-center gap-4 text-sm">
                <span className={lastRun.status === "completed" ? "text-green-400" : "text-red-400"}>
                  {lastRun.status}
                </span>
                <span className="text-gray-400">{lastRun.duration_seconds.toFixed(1)}s</span>
                <span className="text-gray-400">{lastRun.llm_tokens_used.toLocaleString()} tokens</span>
                <span className="text-gray-400 capitalize">{lastRun.execution_path.replace("_", " ")}</span>
              </div>
              {lastRun.error && (
                <div className="text-xs text-red-400">{lastRun.error}</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
