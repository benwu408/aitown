import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";

const FILTERS = ["All", "Speech", "Actions", "Innovations", "Patterns", "Social", "World"] as const;
type Filter = (typeof FILTERS)[number];

const TYPE_COLORS: Record<string, string> = {
  agent_speak: "text-blue-400",
  agent_move: "text-gray-500",
  agent_action: "text-yellow-400",
  agent_thought: "text-purple-400",
  action_result: "text-emerald-400",
  innovation: "text-pink-400",
  pattern: "text-amber-400",
  gossip: "text-orange-400",
  transaction: "text-green-400",
  system_event: "text-cyan-400",
  world_object: "text-teal-400",
};

const TYPE_ICONS: Record<string, string> = {
  agent_speak: "\uD83D\uDDE3\uFE0F",
  agent_move: "\uD83C\uDFC3",
  agent_action: "\u2699\uFE0F",
  agent_thought: "\uD83D\uDCAD",
  action_result: "\u2728",
  innovation: "\uD83D\uDCA1",
  pattern: "\uD83D\uDD2E",
  gossip: "\uD83D\uDCAC",
  transaction: "\uD83D\uDCB0",
  system_event: "\u26A1",
  world_object: "\uD83C\uDF0D",
};

function matchesFilter(type: string, filter: Filter): boolean {
  if (filter === "All") return true;
  if (filter === "Speech") return type === "agent_speak";
  if (filter === "Actions") return type === "agent_action" || type === "action_result";
  if (filter === "Innovations") return type === "innovation";
  if (filter === "Patterns") return type === "pattern";
  if (filter === "Social") return type === "agent_speak" || type === "gossip" || type === "agent_thought";
  if (filter === "World") return type === "system_event" || type === "world_object" || type === "transaction";
  return true;
}

interface Props {
  onAgentClick: (agentId: string) => void;
}

export default function LiveFeed({ onAgentClick }: Props) {
  const [filter, setFilter] = useState<Filter>("All");
  const feed = useSimulationStore((s) => s.feed);
  const actionResults = useSimulationStore((s) => s.actionResults);
  const innovations = useSimulationStore((s) => s.innovations);
  const patterns = useSimulationStore((s) => s.patterns);

  // Merge action results and innovations into feed-like entries
  const extraEntries = [
    ...actionResults.slice(0, 20).map((r, i) => ({
      id: `ar-${i}`,
      tick: r.tick,
      time: "",
      type: "action_result" as string,
      agentId: undefined as string | undefined,
      agentName: r.agent_name,
      text: `${r.agent_name} ${r.success ? "succeeded" : "failed"}: ${r.outcome_description}`,
    })),
    ...innovations.slice(-10).map((inn, i) => ({
      id: `inn-${i}`,
      tick: inn.invented_on,
      time: "",
      type: "innovation" as string,
      agentId: undefined as string | undefined,
      agentName: inn.inventor,
      text: `${inn.inventor} discovered "${inn.name}" (${Math.round(inn.adoption_rate * 100)}% adoption)`,
    })),
    ...patterns.slice(-10).map((p, i) => ({
      id: `pat-${i}`,
      tick: p.emerged_on,
      time: "",
      type: "pattern" as string,
      agentId: undefined as string | undefined,
      agentName: undefined as string | undefined,
      text: `[${p.type}] ${p.name}: ${p.description}`,
    })),
  ];

  const allEntries = [...extraEntries, ...feed];

  const filtered = allEntries.filter((e) => matchesFilter(e.type, filter));

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
                {entry.time ? `[${entry.time}]` : ""}
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
