import { AgentData, AgentDetail } from "../../types/agent";
import { useSimulationStore } from "../../stores/simulationStore";
import { AGENT_COLORS } from "../../utils/formatting";

interface Props {
  agent: AgentData;
  detail: AgentDetail | null;
  onInspect: (agentId: string) => void;
}

export default function RelationshipsTab({ agent, detail, onInspect }: Props) {
  const allAgents = useSimulationStore((s) => s.agents);
  const relationships = detail?.relationships || {};

  const otherAgents = Object.values(allAgents).filter((a) => a.id !== agent.id);

  return (
    <div className="space-y-1 text-xs">
      {otherAgents.map((other) => {
        const rel = relationships[other.name] || {};
        const sentiment = rel.sentiment ?? 0.5;
        const trust = rel.trust ?? 0.5;
        const notes = rel.notes || "No interactions yet";
        const color = AGENT_COLORS[other.colorIndex % AGENT_COLORS.length];

        return (
          <button
            key={other.id}
            onClick={() => onInspect(other.id)}
            className="w-full p-2 bg-gray-800/30 rounded hover:bg-gray-800/60 text-left"
          >
            <div className="flex items-center gap-2 mb-1">
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[8px] font-bold"
                style={{
                  backgroundColor: `#${color.toString(16).padStart(6, "0")}`,
                }}
              >
                {other.name[0]}
              </div>
              <span className="text-gray-300 font-medium">{other.name}</span>
              <span className="text-[10px] text-gray-600 ml-auto">
                {other.job}
              </span>
            </div>

            {/* Sentiment bar */}
            <div className="flex items-center gap-1 mb-0.5">
              <span className="text-[9px] text-gray-600 w-12">Sentiment</span>
              <div className="flex-1 bg-gray-800 rounded-full h-1">
                <div
                  className={`h-1 rounded-full ${
                    sentiment >= 0.5 ? "bg-green-500" : "bg-red-500"
                  }`}
                  style={{
                    width: `${Math.abs(sentiment) * 100}%`,
                    marginLeft: sentiment < 0 ? `${(1 + sentiment) * 50}%` : "50%",
                  }}
                />
              </div>
              <span className="text-[9px] text-gray-600 w-6 text-right">
                {sentiment.toFixed(1)}
              </span>
            </div>

            {/* Trust bar */}
            <div className="flex items-center gap-1 mb-0.5">
              <span className="text-[9px] text-gray-600 w-12">Trust</span>
              <div className="flex-1 bg-gray-800 rounded-full h-1">
                <div
                  className="bg-blue-500 h-1 rounded-full"
                  style={{ width: `${trust * 100}%` }}
                />
              </div>
              <span className="text-[9px] text-gray-600 w-6 text-right">
                {trust.toFixed(1)}
              </span>
            </div>

            <p className="text-[10px] text-gray-500 mt-0.5">{notes}</p>
          </button>
        );
      })}
    </div>
  );
}
