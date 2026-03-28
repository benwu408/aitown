import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";

const TYPE_STYLES: Record<string, { color: string; icon: string; bg: string }> = {
  crisis: { color: "text-red-300", icon: "!", bg: "bg-red-950/60 border-red-800/40" },
  scandal: { color: "text-purple-300", icon: "!", bg: "bg-purple-950/60 border-purple-800/40" },
  achievement: { color: "text-green-300", icon: "+", bg: "bg-green-950/60 border-green-800/40" },
  new_goal: { color: "text-blue-300", icon: "*", bg: "bg-blue-950/60 border-blue-800/40" },
  breakup: { color: "text-orange-300", icon: "-", bg: "bg-orange-950/60 border-orange-800/40" },
};

interface Props {
  onAgentClick: (agentId: string) => void;
}

export default function StoryHighlights({ onAgentClick }: Props) {
  const highlights = useSimulationStore((s) => s.storyHighlights);
  const [collapsed, setCollapsed] = useState(false);
  const recent = highlights.slice(-15);

  if (recent.length === 0) return null;

  return (
    <div className="absolute top-2 left-2 w-56 z-10 pointer-events-auto flex flex-col" style={{ maxHeight: "calc(100% - 1rem)" }}>
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between px-2 py-1 bg-gray-900/80 backdrop-blur-sm rounded-t border border-gray-700/50 border-b-0"
      >
        <span className="text-[9px] text-gray-400 uppercase tracking-wider font-semibold">
          Stories ({highlights.length})
        </span>
        <span className="text-[9px] text-gray-500">{collapsed ? "+" : "-"}</span>
      </button>

      {/* Content */}
      {!collapsed && (
        <div className="overflow-y-auto bg-gray-900/70 backdrop-blur-sm border border-gray-700/50 border-t-0 rounded-b space-y-0.5 p-1">
          {[...recent].reverse().map((h: any, i: number) => {
            const style = TYPE_STYLES[h.type] || TYPE_STYLES.new_goal;
            return (
              <div
                key={i}
                onClick={() => h.agentId && onAgentClick(h.agentId)}
                className={`px-2 py-1 rounded border text-[9px] leading-tight cursor-pointer hover:brightness-125 transition-all ${style.bg} ${style.color}`}
              >
                <span className="font-bold mr-0.5 opacity-60">[{style.icon}]</span>
                {h.text}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
