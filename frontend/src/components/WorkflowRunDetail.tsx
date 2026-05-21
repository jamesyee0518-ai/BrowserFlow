import type { WorkflowRun } from "../lib/api";
import { CheckCircle, XCircle, Clock, Bot, FileCode, AlertTriangle } from "lucide-react";

interface Props {
  run: WorkflowRun;
  onClose: () => void;
}

const statusIcon = (status: string) => {
  switch (status) {
    case "completed": return <CheckCircle className="h-4 w-4 text-green-400" />;
    case "failed": return <XCircle className="h-4 w-4 text-red-400" />;
    case "running": return <Clock className="h-4 w-4 text-yellow-400 animate-pulse" />;
    default: return <Clock className="h-4 w-4 text-gray-400" />;
  }
};

const pathLabel = (path: string) => {
  switch (path) {
    case "agent": return { icon: <Bot className="h-3.5 w-3.5" />, text: "Agent (LLM)", color: "text-blue-400" };
    case "script": return { icon: <FileCode className="h-3.5 w-3.5" />, text: "Script (Cached)", color: "text-green-400" };
    case "agent_fallback": return { icon: <AlertTriangle className="h-3.5 w-3.5" />, text: "Agent Fallback", color: "text-yellow-400" };
    default: return { icon: <Clock className="h-3.5 w-3.5" />, text: path, color: "text-gray-400" };
  }
};

export function WorkflowRunDetail({ run, onClose }: Props) {
  const path = pathLabel(run.execution_path);
  const progress = run.blocks_total > 0 ? (run.blocks_completed / run.blocks_total) * 100 : 0;

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {statusIcon(run.status)}
          <span className="text-sm font-medium capitalize">{run.status}</span>
        </div>
        <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-300">Close</button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface-1 rounded-lg p-3 border border-border">
          <div className="text-xs text-gray-500 mb-1">Execution Path</div>
          <div className={`flex items-center gap-1.5 ${path.color}`}>
            {path.icon}
            <span className="text-sm font-medium">{path.text}</span>
          </div>
        </div>

        <div className="bg-surface-1 rounded-lg p-3 border border-border">
          <div className="text-xs text-gray-500 mb-1">Duration</div>
          <div className="text-sm font-medium">{run.duration_seconds.toFixed(1)}s</div>
        </div>

        <div className="bg-surface-1 rounded-lg p-3 border border-border">
          <div className="text-xs text-gray-500 mb-1">LLM Tokens</div>
          <div className="text-sm font-medium">{run.llm_tokens_used.toLocaleString()}</div>
        </div>

        <div className="bg-surface-1 rounded-lg p-3 border border-border">
          <div className="text-xs text-gray-500 mb-1">Blocks</div>
          <div className="text-sm font-medium">{run.blocks_completed} / {run.blocks_total}</div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">Progress</span>
          <span className="text-xs text-gray-400">{progress.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-surface-0 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${
              run.status === "completed" ? "bg-green-500" : run.status === "failed" ? "bg-red-500" : "bg-blue-500"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {run.error && (
        <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-3">
          <div className="text-xs text-red-400 font-medium mb-1">Error</div>
          <div className="text-sm text-red-300">{run.error}</div>
        </div>
      )}

      {run.output && (
        <div>
          <div className="text-xs text-gray-500 mb-1">Output</div>
          <pre className="text-xs font-mono bg-surface-0 border border-border rounded-lg p-3 max-h-64 overflow-auto">
            {JSON.stringify(run.output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
