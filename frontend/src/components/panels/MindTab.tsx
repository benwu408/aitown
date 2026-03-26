import { AgentData, AgentDetail } from "../../types/agent";

const MEMORY_COLORS: Record<string, string> = {
  observation: "border-blue-500",
  conversation: "border-green-500",
  reflection: "border-purple-500",
  action: "border-yellow-500",
  emotion: "border-red-500",
};

const MEMORY_ICONS: Record<string, string> = {
  observation: "\uD83D\uDD35",
  conversation: "\uD83D\uDFE2",
  reflection: "\uD83D\uDFE3",
  action: "\uD83D\uDFE1",
  emotion: "\uD83D\uDD34",
};

interface Props {
  agent: AgentData;
  detail: AgentDetail | null;
}

export default function MindTab({ agent, detail }: Props) {
  return (
    <div className="space-y-3 text-xs">
      {/* Current thought */}
      {agent.innerThought && (
        <div className="p-2 bg-purple-900/20 border border-purple-800/30 rounded">
          <div className="text-[10px] text-purple-400 uppercase mb-1">
            Current Thought
          </div>
          <p className="text-gray-300 italic">"{agent.innerThought}"</p>
        </div>
      )}

      {/* Current state */}
      <div className="p-2 bg-gray-800/50 rounded">
        <div className="flex justify-between mb-1">
          <span className="text-gray-500">Action</span>
          <span className="text-gray-300">{agent.currentAction}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Emotion</span>
          <span className="text-gray-300">{agent.emotion}</span>
        </div>
      </div>

      {/* Daily plan */}
      {detail?.dailyPlan && (
        <div className="p-2 bg-gray-800/50 rounded">
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Today's Plan
          </div>
          <p className="text-gray-400">{detail.dailyPlan}</p>
        </div>
      )}

      {/* Goals */}
      {detail?.goals && detail.goals.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Active Goals
          </div>
          {detail.goals.map((g, i) => (
            <div key={i} className="flex items-start gap-1 text-gray-400 mb-0.5">
              <span className="text-gray-600">{i + 1}.</span>
              <span>{g}</span>
            </div>
          ))}
        </div>
      )}

      {/* Memories */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Recent Memories
        </div>
        {detail?.memories && detail.memories.length > 0 ? (
          <div className="space-y-1">
            {[...detail.memories].reverse().map((m, i) => (
              <div
                key={i}
                className={`p-1.5 border-l-2 ${
                  MEMORY_COLORS[m.type] || "border-gray-600"
                } bg-gray-800/30 rounded-r`}
              >
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-[9px]">
                    {MEMORY_ICONS[m.type] || "\u26AA"}
                  </span>
                  <span className="text-[9px] text-gray-600 uppercase">
                    {m.type}
                  </span>
                  {m.importance >= 7 && (
                    <span className="text-[9px] text-amber-500">
                      \u2605
                    </span>
                  )}
                </div>
                <p className="text-gray-400">{m.content}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 italic">No memories yet</p>
        )}
      </div>
    </div>
  );
}
