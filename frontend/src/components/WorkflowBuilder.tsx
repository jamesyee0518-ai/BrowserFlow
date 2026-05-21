import { useState } from "react";
import { Plus, Trash2, ChevronDown, ChevronUp, GripVertical } from "lucide-react";
import type { WorkflowBlock } from "../lib/api";

interface Props {
  blocks: WorkflowBlock[];
  onChange: (blocks: WorkflowBlock[]) => void;
}

const BLOCK_TYPES = [
  { value: "task", label: "Task", desc: "LLM-driven browser task" },
  { value: "code", label: "Code", desc: "Python code execution" },
  { value: "for_loop", label: "For Loop", desc: "Iterate over a list" },
  { value: "conditional", label: "Conditional", desc: "If/else branching" },
] as const;

function makeBlock(type: WorkflowBlock["block_type"]): WorkflowBlock {
  const base: WorkflowBlock = { block_type: type, label: "" };
  switch (type) {
    case "task":
      return { ...base, url: "", navigation_goal: "", data_extraction_goal: "", max_steps: 25 };
    case "code":
      return { ...base, code: "result = {}" };
    case "for_loop":
      return { ...base, loop_over: [], loop_blocks: [] };
    case "conditional":
      return { ...base, condition: "", then_blocks: [], else_blocks: [] };
    default:
      return base;
  }
}

function BlockCard({
  block,
  onUpdate,
  onRemove,
  onMove,
}: {
  block: WorkflowBlock;
  onUpdate: (b: WorkflowBlock) => void;
  onRemove: () => void;
  onMove: (dir: -1 | 1) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const typeLabel = BLOCK_TYPES.find((t) => t.value === block.block_type)?.label || block.block_type;

  return (
    <div className="border border-border rounded-lg bg-surface-1">
      <div className="flex items-center gap-2 px-3 py-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <GripVertical className="h-4 w-4 text-gray-600" />
        <span className="text-xs font-medium text-blue-400 uppercase">{typeLabel}</span>
        <input
          value={block.label}
          onChange={(e) => onUpdate({ ...block, label: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          placeholder="Label"
          className="flex-1 text-sm bg-transparent border-none outline-none placeholder-gray-600"
        />
        <button onClick={(e) => { e.stopPropagation(); onMove(-1); }} className="text-gray-500 hover:text-gray-300" title="Move up">
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button onClick={(e) => { e.stopPropagation(); onMove(1); }} className="text-gray-500 hover:text-gray-300" title="Move down">
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <button onClick={(e) => { e.stopPropagation(); onRemove(); }} className="text-red-400 hover:text-red-300" title="Remove">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-border/50">
          {(block.block_type === "task" || block.block_type === "navigation" || block.block_type === "extraction") && (
            <>
              <div>
                <label className="text-xs text-gray-400">URL</label>
                <input
                  value={block.url || ""}
                  onChange={(e) => onUpdate({ ...block, url: e.target.value })}
                  placeholder="https://example.com"
                  className="w-full text-sm bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">Navigation Goal</label>
                <input
                  value={block.navigation_goal || ""}
                  onChange={(e) => onUpdate({ ...block, navigation_goal: e.target.value })}
                  placeholder="Navigate to product page and wait for price"
                  className="w-full text-sm bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">Data Extraction Goal</label>
                <input
                  value={block.data_extraction_goal || ""}
                  onChange={(e) => onUpdate({ ...block, data_extraction_goal: e.target.value })}
                  placeholder="Extract the current listed price"
                  className="w-full text-sm bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400">Max Steps</label>
                <input
                  type="number"
                  value={block.max_steps || 25}
                  onChange={(e) => onUpdate({ ...block, max_steps: parseInt(e.target.value) || 25 })}
                  className="w-24 text-sm bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
                />
              </div>
            </>
          )}

          {block.block_type === "code" && (
            <div>
              <label className="text-xs text-gray-400">Python Code</label>
              <textarea
                value={block.code || ""}
                onChange={(e) => onUpdate({ ...block, code: e.target.value })}
                rows={6}
                placeholder="result = {'price': 999}"
                className="w-full text-sm font-mono bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
              />
            </div>
          )}

          {block.block_type === "for_loop" && (
            <div>
              <label className="text-xs text-gray-400">Loop Over (JSON array)</label>
              <textarea
                value={JSON.stringify(block.loop_over || [], null, 2)}
                onChange={(e) => {
                  try { onUpdate({ ...block, loop_over: JSON.parse(e.target.value) }); } catch {}
                }}
                rows={4}
                placeholder='["item1", "item2"]'
                className="w-full text-sm font-mono bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
              />
            </div>
          )}

          {block.block_type === "conditional" && (
            <div>
              <label className="text-xs text-gray-400">Condition (Python expression)</label>
              <input
                value={block.condition || ""}
                onChange={(e) => onUpdate({ ...block, condition: e.target.value })}
                placeholder="context.get('price', 0) > 100"
                className="w-full text-sm font-mono bg-surface-0 border border-border rounded px-2 py-1 mt-0.5"
              />
            </div>
          )}

          {block.cached_script && (
            <div>
              <label className="text-xs text-green-400">Cached Script (auto-generated)</label>
              <pre className="text-xs font-mono bg-green-900/20 border border-green-800/30 rounded px-2 py-1 mt-0.5 max-h-32 overflow-auto">
                {block.cached_script}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function WorkflowBuilder({ blocks, onChange }: Props) {
  const addBlock = (type: WorkflowBlock["block_type"]) => {
    onChange([...blocks, makeBlock(type)]);
  };

  const updateBlock = (index: number, block: WorkflowBlock) => {
    const next = [...blocks];
    next[index] = block;
    onChange(next);
  };

  const removeBlock = (index: number) => {
    onChange(blocks.filter((_, i) => i !== index));
  };

  const moveBlock = (index: number, dir: -1 | 1) => {
    const target = index + dir;
    if (target < 0 || target >= blocks.length) return;
    const next = [...blocks];
    const temp = next[index] as WorkflowBlock;
    next[index] = next[target] as WorkflowBlock;
    next[target] = temp;
    onChange(next);
  };

  return (
    <div className="space-y-3">
      {blocks.map((block, i) => (
        <BlockCard
          key={i}
          block={block}
          onUpdate={(b) => updateBlock(i, b)}
          onRemove={() => removeBlock(i)}
          onMove={(dir) => moveBlock(i, dir)}
        />
      ))}

      <div className="flex items-center gap-2 pt-2">
        <span className="text-xs text-gray-500">Add block:</span>
        {BLOCK_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => addBlock(t.value)}
            className="text-xs px-2 py-1 rounded border border-border hover:bg-surface-2 text-gray-400 hover:text-gray-200 flex items-center gap-1"
            title={t.desc}
          >
            <Plus className="h-3 w-3" /> {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
