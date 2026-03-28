import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { AGENT_COLORS } from "../../utils/formatting";
import MindTab from "./MindTab";
import RelationshipsTab from "./RelationshipsTab";

const TABS = ["Status", "Mind", "Relations", "Skills"] as const;
type Tab = (typeof TABS)[number];

interface Props {
  onInspect: (agentId: string) => void;
}

export default function InspectorPanel({ onInspect }: Props) {
  const [tab, setTab] = useState<Tab>("Status");
  const selectedId = useSimulationStore((s) => s.selectedAgentId);
  const agents = useSimulationStore((s) => s.agents);
  const detail = useSimulationStore((s) => s.selectedAgentDetail);

  const agent = selectedId ? agents[selectedId] : null;

  if (!agent) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-3 border-b border-gray-800">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Inspector
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <p className="text-sm text-gray-500">
            Click an agent to inspect their mind, memories, and relationships.
          </p>
          {/* Agent list */}
          <div className="mt-3 space-y-1.5">
            {Object.values(agents).map((a) => {
              const color = AGENT_COLORS[a.colorIndex % AGENT_COLORS.length];
              const moodPct = Math.round(a.state.mood * 100);
              const moodColor = moodPct > 60 ? "bg-green-500" : moodPct > 30 ? "bg-yellow-500" : "bg-red-500";
              const summary = (a as any).summary || `${a.age}yo ${a.job}`;
              return (
                <button
                  key={a.id}
                  onClick={() => onInspect(a.id)}
                  className="w-full p-2 rounded hover:bg-gray-800/80 text-left border border-transparent hover:border-gray-700"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[8px] font-bold shrink-0"
                      style={{ backgroundColor: `#${color.toString(16).padStart(6, "0")}` }}
                    >
                      {a.name[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-200 font-medium">{a.name}</span>
                        <span className="text-[9px] text-gray-600">{a.emotion}</span>
                      </div>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500 leading-tight line-clamp-2 mb-1">
                    {summary}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-gray-600">{a.currentAction}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-1">
                      <div className={`${moodColor} h-1 rounded-full`} style={{ width: `${moodPct}%` }} />
                    </div>
                    <span className="text-[9px] text-amber-400">{a.state.wealth}c</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  const color = AGENT_COLORS[agent.colorIndex % AGENT_COLORS.length];

  return (
    <div className="flex flex-col h-full">
      {/* Agent header */}
      <div className="p-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold"
            style={{ backgroundColor: `#${color.toString(16).padStart(6, "0")}` }}
          >
            {agent.name[0]}
          </div>
          <div>
            <div className="text-sm font-medium text-gray-200">{agent.name}</div>
            <div className="text-[10px] text-gray-500">
              {agent.age}yo {agent.job}
            </div>
          </div>
          <button
            onClick={() => { useSimulationStore.getState().selectAgent(null); useSimulationStore.getState().setFollowAgent(null); }}
            className="ml-auto text-gray-500 hover:text-gray-200 text-xs flex items-center gap-1 px-2 py-0.5 rounded hover:bg-gray-800"
          >
            {"<"} Back
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-[10px] uppercase tracking-wider ${
              tab === t
                ? "text-amber-400 border-b-2 border-amber-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "Status" && <StatusContent agent={agent} detail={detail} />}
        {tab === "Mind" && <MindTab agent={agent} detail={detail} />}
        {tab === "Relations" && (
          <RelationshipsTab agent={agent} detail={detail} onInspect={onInspect} />
        )}
        {tab === "Skills" && <EconContent agent={agent} detail={detail} />}
      </div>
    </div>
  );
}

function StatusContent({ agent, detail }: { agent: any; detail: any }) {
  return (
    <div className="space-y-3 text-xs">
      {agent.innerThought && (
        <div className="p-2 bg-gray-800/50 rounded italic text-gray-300">
          "{agent.innerThought}"
        </div>
      )}

      <div className="space-y-1.5">
        <Row label="Activity" value={agent.currentAction} />
        <Row label="Location" value={agent.currentLocation.replace(/_/g, " ")} />
        <Row label="Emotion" value={agent.emotion} />
        <Row
          label="Wealth"
          value={`${agent.state.wealth} coins`}
          valueClass="text-amber-400"
        />
      </div>

      <div className="space-y-1.5">
        <BarRow label="Energy" value={agent.state.energy} color="bg-green-500" />
        <BarRow label="Hunger" value={agent.state.hunger} color="bg-orange-500" />
        <BarRow label="Mood" value={agent.state.mood} color="bg-blue-500" />
      </div>

      {detail?.backstory && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Backstory</div>
          <p className="text-gray-400">{detail.backstory}</p>
        </div>
      )}

      {detail?.goals && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Goals</div>
          {detail.goals.map((g: string, i: number) => (
            <div key={i} className="text-gray-400">- {g}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function EconContent({ agent, detail }: { agent: any; detail: any }) {
  const inventory = (agent as any)?.inventory || detail?.inventory || [];
  const skills = detail?.skills || {};
  const physicalTraits = detail?.physicalTraits || {};

  return (
    <div className="space-y-3 text-xs">
      <div className="text-sm text-gray-300 font-medium">
        Role: {agent.job || "newcomer"}
      </div>

      {/* Physical Traits */}
      {Object.keys(physicalTraits).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Physical Traits</div>
          <div className="space-y-1">
            {Object.entries(physicalTraits).map(([trait, val]: [string, any]) => (
              <BarRow key={trait} label={trait} value={val} color="bg-blue-500" />
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Discovered Skills ({Object.keys(skills).length})
        </div>
        {Object.keys(skills).length === 0 ? (
          <p className="text-gray-600 italic">No skills discovered yet</p>
        ) : (
          <div className="space-y-1">
            {Object.entries(skills).sort((a: any, b: any) => (b[1].skill_level || 0) - (a[1].skill_level || 0)).map(([name, data]: [string, any]) => (
              <div key={name} className="flex items-center justify-between">
                <span className="text-gray-300 capitalize">{name.replace(/_/g, " ")}</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-gray-800 rounded-full h-1.5">
                    <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${(data.skill_level || 0) * 100}%` }} />
                  </div>
                  <span className="text-[9px] text-gray-500">{data.attempts || 0}x</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Inventory */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Inventory ({inventory.length})
        </div>
        {inventory.length === 0 ? (
          <p className="text-gray-600 italic">Empty hands</p>
        ) : (
          <div className="space-y-0.5">
            {inventory.map((item: any, i: number) => (
              <div key={i} className="text-gray-400">
                {item.name || item} {item.quantity ? `(${item.quantity})` : ""}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  valueClass = "text-gray-300",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  );
}

function BarRow({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500 w-14">{label}</span>
      <div className="flex-1 mx-2 bg-gray-800 rounded-full h-1.5">
        <div
          className={`${color} h-1.5 rounded-full transition-all`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-gray-500 w-8 text-right">
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}
