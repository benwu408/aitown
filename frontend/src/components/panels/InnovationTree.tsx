import { useMemo } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { InnovationEvent } from "../../types/agent";

interface Props {
  onClose: () => void;
}

function adoptionColor(rate: number): string {
  if (rate >= 0.7) return "border-green-500 bg-green-950/30 text-green-200";
  if (rate >= 0.3) return "border-yellow-500 bg-yellow-950/30 text-yellow-200";
  return "border-gray-600 bg-gray-800/30 text-gray-400";
}

function adoptionBarColor(rate: number): string {
  if (rate >= 0.7) return "bg-green-500";
  if (rate >= 0.3) return "bg-yellow-500";
  return "bg-gray-600";
}

interface TreeNode {
  innovation: InnovationEvent;
  children: TreeNode[];
}

function buildTree(innovations: InnovationEvent[]): TreeNode[] {
  const byId = new Map<string, InnovationEvent>();
  for (const inn of innovations) {
    byId.set(inn.id, inn);
  }

  const childMap = new Map<string, InnovationEvent[]>();
  const roots: InnovationEvent[] = [];

  for (const inn of innovations) {
    if (inn.parent_id && byId.has(inn.parent_id)) {
      if (!childMap.has(inn.parent_id)) childMap.set(inn.parent_id, []);
      childMap.get(inn.parent_id)!.push(inn);
    } else {
      roots.push(inn);
    }
  }

  function toNode(inn: InnovationEvent): TreeNode {
    const children = (childMap.get(inn.id) || []).map(toNode);
    return { innovation: inn, children };
  }

  return roots.map(toNode);
}

function TreeNodeView({ node, depth }: { node: TreeNode; depth: number }) {
  const inn = node.innovation;
  const colorClass = adoptionColor(inn.adoption_rate);
  const barColor = adoptionBarColor(inn.adoption_rate);

  return (
    <div style={{ marginLeft: depth * 16 }}>
      <div className={`rounded border p-2.5 mb-1.5 ${colorClass}`}>
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium truncate">{inn.name}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">
              by {inn.inventor}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-12 bg-gray-800 rounded-full h-1.5">
              <div className={`${barColor} h-1.5 rounded-full`} style={{ width: `${inn.adoption_rate * 100}%` }} />
            </div>
            <span className="text-[9px] w-8 text-right">{Math.round(inn.adoption_rate * 100)}%</span>
          </div>
        </div>
        {inn.description && (
          <div className="text-[10px] text-gray-500 mt-1">{inn.description}</div>
        )}
        {inn.adopters.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {inn.adopters.slice(0, 5).map((name, i) => (
              <span key={i} className="text-[8px] px-1 py-0.5 bg-gray-800/50 rounded text-gray-500">
                {name}
              </span>
            ))}
            {inn.adopters.length > 5 && (
              <span className="text-[8px] text-gray-600">+{inn.adopters.length - 5}</span>
            )}
          </div>
        )}
      </div>
      {node.children.map((child) => (
        <TreeNodeView key={child.innovation.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function InnovationTree({ onClose }: Props) {
  const innovations = useSimulationStore((s) => s.innovations);

  const tree = useMemo(() => buildTree(innovations), [innovations]);

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-gray-900 border border-gray-700/50 rounded-lg w-[520px] max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-800 shrink-0">
          <div>
            <h2 className="text-pink-400 font-bold text-sm uppercase tracking-wider">
              Innovation Tree
            </h2>
            <span className="text-[10px] text-gray-500">
              {innovations.length} innovation{innovations.length !== 1 ? "s" : ""} discovered
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-lg leading-none"
          >
            x
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {innovations.length === 0 ? (
            <p className="text-sm text-gray-500 italic text-center py-8">
              No innovations discovered yet. Agents will invent things as they interact with the world.
            </p>
          ) : (
            <div className="space-y-1">
              {tree.map((node) => (
                <TreeNodeView key={node.innovation.id} node={node} depth={0} />
              ))}
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="p-3 border-t border-gray-800 flex items-center gap-4 text-[9px] text-gray-500">
          <span>Adoption:</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-gray-600" /> Low
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-500" /> Medium
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" /> High
          </span>
        </div>
      </div>
    </div>
  );
}
