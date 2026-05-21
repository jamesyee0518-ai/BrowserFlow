import { Play, Trash2, Clock, Zap, Bot, FileCode } from "lucide-react";
import type { Workflow } from "../lib/api";

interface Props {
  workflows: Workflow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRun: (id: string) => void;
  onDelete: (id: string) => void;
}

const statusColors: Record<string, string> = {
  idle: "bg-gray-500",
  running: "bg-yellow-500 animate-pulse",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

const pathIcons: Record<string, React.ReactNode> = {
  agent: <Bot className="h-3 w-3" />,
  script: <FileCode className="h-3 w-3" />,
};

export function WorkflowList({ workflows, selectedId, onSelect, onNew, onRun, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Workflows</span>
        <button
          onClick={onNew}
          className="text-xs text-blue-400 hover:text-blue-300 font-medium"
        >
          + New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {workflows.length === 0 && (
          <div className="px-3 py-6 text-center text-gray-500 text-xs">
            No workflows yet
          </div>
        )}

        {workflows.map((wf) => (
          <div
            key={wf.id}
            className={`px-3 py-2 cursor-pointer border-b border-border/50 hover:bg-surface-2 transition-colors ${
              selectedId === wf.id ? "bg-surface-2" : ""
            }`}
            onClick={() => onSelect(wf.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusColors[wf.status] || "bg-gray-500"}`} />
                <span className="text-sm truncate">{wf.title}</span>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <span className="text-gray-500" title={wf.run_with}>
                  {pathIcons[wf.run_with]}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-500 capitalize">{wf.status}</span>
              {wf.adaptive_caching && (
                <span className="text-xs text-gray-600 flex items-center gap-0.5" title="Adaptive caching">
                  <Zap className="h-2.5 w-2.5" />
                </span>
              )}
              {wf.schedule && (
                <span className="text-xs text-gray-600 flex items-center gap-0.5" title={wf.schedule}>
                  <Clock className="h-2.5 w-2.5" />
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 mt-1.5">
              <button
                onClick={(e) => { e.stopPropagation(); onRun(wf.id); }}
                className="text-xs text-green-400 hover:text-green-300 flex items-center gap-0.5 px-1.5 py-0.5 rounded hover:bg-green-400/10"
                disabled={wf.status === "running"}
                title="Run workflow"
              >
                <Play className="h-3 w-3" /> Run
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(wf.id); }}
                className="text-xs text-red-400 hover:text-red-300 flex items-center gap-0.5 px-1.5 py-0.5 rounded hover:bg-red-400/10"
                title="Delete workflow"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
