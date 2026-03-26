import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";

const FILTERS = ["All", "Speech", "Movement", "Action"] as const;
type Filter = (typeof FILTERS)[number];

const TYPE_COLORS: Record<string, string> = {
  agent_speak: "text-blue-400",
  agent_move: "text-gray-500",
  agent_action: "text-yellow-400",
  agent_thought: "text-purple-400",
};

const TYPE_ICONS: Record<string, string> = {
  agent_speak: "\uD83D\uDDE3\uFE0F",
  agent_move: "\uD83C\uDFC3",
  agent_action: "\u2699\uFE0F",
  agent_thought: "\uD83D\uDCAD",
};

interface Props {
  onAgentClick: (agentId: string) => void;
}

export default function LiveFeed({ onAgentClick }: Props) {
  const [filter, setFilter] = useState<Filter>("All");
  const feed = useSimulationStore((s) => s.feed);

  const filtered =
    filter === "All"
      ? feed
      : feed.filter((e) => {
          if (filter === "Speech") return e.type === "agent_speak";
          if (filter === "Movement") return e.type === "agent_move";
          if (filter === "Action") return e.type === "agent_action";
          return true;
        });

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-1.5 border-b border-gray-800 flex items-center gap-2">
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Live Feed
        </span>
        <div className="flex gap-1 ml-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-1.5 py-0.5 text-[9px] rounded ${
                filter === f
                  ? "bg-gray-700 text-gray-200"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="text-[9px] text-gray-600 ml-auto">
          {feed.length} events
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-1 space-y-0.5">
        {filtered.length === 0 ? (
          <p className="text-xs text-gray-600 italic py-2">
            {feed.length === 0
              ? "Waiting for simulation events..."
              : "No events match this filter"}
          </p>
        ) : (
          filtered.slice(0, 100).map((entry) => (
            <div
              key={entry.id}
              className={`text-[11px] cursor-pointer hover:bg-gray-800/50 px-1 py-0.5 rounded ${
                TYPE_COLORS[entry.type] || "text-gray-400"
              }`}
              onClick={() => entry.agentId && onAgentClick(entry.agentId)}
            >
              <span className="text-gray-600 mr-1">
                [{entry.time}]
              </span>
              <span className="mr-1">
                {TYPE_ICONS[entry.type] || ""}
              </span>
              {entry.text}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
