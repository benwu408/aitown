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

const OPINION_LABELS: Record<string, string> = {
  taxes: "Taxes",
  clinic_funding: "Clinic Funding",
  modernization: "Modernization",
  outsiders: "Outsiders",
  school_budget: "School Budget",
  tradition: "Tradition",
};

interface Props {
  agent: AgentData;
  detail: AgentDetail | null;
}

export default function MindTab({ agent, detail }: Props) {
  const activeGoals = (detail as any)?.activeGoals || [];
  const secrets = (detail as any)?.secrets || [];
  const opinions = (detail as any)?.opinions || {};

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

      {/* Secrets */}
      {secrets.length > 0 && (
        <div className="p-2 bg-red-900/10 border border-red-900/30 rounded">
          <div className="text-[10px] text-red-400 uppercase mb-1">
            Secrets ({secrets.length})
          </div>
          {secrets.map((s: any, i: number) => {
            const knownCount = s.known_by?.length || 0;
            const isPublic = knownCount >= 3;
            return (
              <div key={i} className="mb-1">
                <p className="text-gray-400 italic text-[11px]">"{s.content}"</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-[9px] px-1 rounded ${isPublic ? "bg-red-900/50 text-red-300" : knownCount > 0 ? "bg-yellow-900/50 text-yellow-300" : "bg-gray-800 text-gray-500"}`}>
                    {isPublic ? "PUBLIC" : knownCount > 0 ? `${knownCount} know` : "HIDDEN"}
                  </span>
                  {knownCount > 0 && (
                    <span className="text-[9px] text-gray-600">
                      Known by: {s.known_by.join(", ")}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Active Goals with Timeline */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Goals ({activeGoals.filter((g: any) => g.status === "active").length} active)
        </div>
        {activeGoals.length === 0 ? (
          <p className="text-gray-600 italic">No goals</p>
        ) : (
          <div className="space-y-1.5">
            {activeGoals.map((g: any, i: number) => {
              const statusColor = g.status === "active" ? "bg-green-900/50 text-green-300"
                : g.status === "completed" ? "bg-blue-900/50 text-blue-300"
                : "bg-gray-800 text-gray-500";
              const sourceColor = g.source === "personality" ? "text-gray-600" : "text-amber-500";
              return (
                <div key={i} className={`p-1.5 rounded border ${g.status === "active" ? "border-green-900/30 bg-green-900/10" : "border-gray-800 bg-gray-800/30"}`}>
                  <div className="flex items-start gap-1">
                    <span className={`text-[9px] px-1 rounded ${statusColor}`}>
                      {g.status}
                    </span>
                    <span className="text-gray-300 flex-1">{g.text}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[9px]">
                    <span className={sourceColor}>from {g.source}</span>
                    {g.created_tick > 0 && (
                      <span className="text-gray-600">tick {g.created_tick}</span>
                    )}
                    <span className="text-gray-600">P:{g.priority?.toFixed(1)}</span>
                  </div>
                  {/* Progress notes */}
                  {g.progress_notes && g.progress_notes.length > 0 && (
                    <div className="mt-1 pl-2 border-l border-gray-700 space-y-0.5">
                      {g.progress_notes.map((n: string, j: number) => (
                        <div key={j} className="text-[9px] text-gray-500">{n}</div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Opinions */}
      {Object.keys(opinions).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Opinions</div>
          <div className="space-y-1">
            {Object.entries(opinions).map(([topic, data]: [string, any]) => {
              const stance = data.stance ?? 0;
              const confidence = data.confidence ?? 0;
              const pct = Math.round(((stance + 1) / 2) * 100);
              const label = OPINION_LABELS[topic] || topic;
              return (
                <div key={topic} className="flex items-center gap-2">
                  <span className="text-[9px] text-gray-500 w-20 truncate">{label}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-2 relative">
                    {/* Center marker */}
                    <div className="absolute left-1/2 top-0 w-px h-2 bg-gray-600" />
                    <div
                      className={`h-2 rounded-full ${stance > 0.1 ? "bg-green-500" : stance < -0.1 ? "bg-red-500" : "bg-gray-600"}`}
                      style={{
                        width: `${Math.abs(stance) * 50}%`,
                        marginLeft: stance >= 0 ? "50%" : `${50 - Math.abs(stance) * 50}%`,
                      }}
                    />
                  </div>
                  <span className={`text-[9px] w-8 text-right ${stance > 0.2 ? "text-green-400" : stance < -0.2 ? "text-red-400" : "text-gray-500"}`}>
                    {stance > 0 ? "+" : ""}{stance.toFixed(1)}
                  </span>
                  <span className="text-[9px] text-gray-700 w-6 text-right">
                    c:{confidence.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Social Commitments */}
      {(detail as any)?.socialCommitments && (detail as any).socialCommitments.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Plans ({(detail as any).socialCommitments.length})
          </div>
          <div className="space-y-1">
            {(detail as any).socialCommitments.map((c: any, i: number) => (
              <div key={i} className="p-1.5 bg-cyan-900/15 border border-cyan-900/30 rounded text-[10px]">
                <div className="text-cyan-300">{c.what}</div>
                <div className="text-gray-500">
                  {c.where?.replace(/_/g, " ")}
                  {c.with && c.with.length > 0 && ` with ${c.with.join(", ")}`}
                  {c.recurring && <span className="ml-1 text-amber-500">(recurring)</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Working Memory */}
      {agent.workingMemory && agent.workingMemory.items?.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Working Memory</div>
          <div className="space-y-0.5">
            {agent.workingMemory.items.map((item: string, i: number) => (
              <div key={i} className="text-[10px] text-gray-400 p-1 bg-gray-800/30 rounded">
                {i === 0 && <span className="text-amber-400 mr-1">[focus]</span>}
                {item}
              </div>
            ))}
            {agent.workingMemory.worry && (
              <div className="text-[10px] text-red-400/70 p-1 bg-red-900/10 rounded">
                Worry: {agent.workingMemory.worry}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Beliefs */}
      {(detail as any)?.beliefs && (detail as any).beliefs.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Beliefs ({(detail as any).beliefs.length})
          </div>
          <div className="space-y-0.5">
            {(detail as any).beliefs.slice(0, 8).map((b: any, i: number) => (
              <div key={i} className="text-[10px] text-gray-400 p-1 bg-gray-800/20 rounded">
                {b.content}
                <span className="text-gray-600 ml-1">({Math.round(b.confidence * 100)}%)</span>
                {b.questioned && <span className="text-amber-400 ml-1">?</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Discovered Locations */}
      {(detail as any)?.worldKnowledge?.locations && Object.keys((detail as any).worldKnowledge.locations).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Discovered Places ({Object.keys((detail as any).worldKnowledge.locations).length})
          </div>
          <div className="flex flex-wrap gap-1">
            {Object.keys((detail as any).worldKnowledge.locations).map((loc: string) => (
              <span key={loc} className="text-[9px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-400">
                {loc.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Mental Models */}
      {(detail as any)?.mentalModels && Object.keys((detail as any).mentalModels).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Mental Models ({Object.keys((detail as any).mentalModels).length})
          </div>
          <div className="space-y-1">
            {Object.entries((detail as any).mentalModels).slice(0, 5).map(([name, model]: [string, any]) => (
              <div key={name} className="text-[10px] p-1 bg-gray-800/30 rounded">
                <span className="text-gray-300">{name}</span>
                <span className="text-gray-600 ml-1">trust:{model.trust?.toFixed(1)} comfort:{model.comfort?.toFixed(1)}</span>
                {model.personality && <div className="text-[9px] text-gray-500 mt-0.5">{model.personality.slice(0, 60)}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full Emotion Breakdown */}
      {agent.emotions && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Emotions</div>
          <div className="space-y-0.5">
            {Object.entries(agent.emotions)
              .filter(([k, v]) => k !== "dominant" && k !== "dominantIntensity" && k !== "valence" && k !== "arousal" && typeof v === "number" && (v as number) > 0.05)
              .sort((a, b) => (b[1] as number) - (a[1] as number))
              .map(([name, val]: [string, any]) => {
                const color = name === "joy" || name === "hope" || name === "gratitude" || name === "pride" ? "bg-green-500"
                  : name === "anger" || name === "resentment" ? "bg-red-500"
                  : name === "sadness" || name === "loneliness" ? "bg-blue-500"
                  : name === "anxiety" || name === "shame" ? "bg-yellow-500"
                  : "bg-gray-500";
                return (
                  <div key={name} className="flex items-center gap-1">
                    <span className="text-[9px] text-gray-600 w-16 capitalize">{name}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-1">
                      <div className={`${color} h-1 rounded-full`} style={{ width: `${val * 100}%` }} />
                    </div>
                    <span className="text-[9px] text-gray-600 w-6 text-right">{Math.round(val * 100)}%</span>
                  </div>
                );
              })}
            {Object.values(agent.emotions).filter((v: any) => typeof v === "number" && v > 0.05).length === 0 && (
              <p className="text-[9px] text-gray-600 italic">Emotionally neutral</p>
            )}
          </div>
        </div>
      )}

      {/* Drives (full display) */}
      {agent.drives && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Drives</div>
          <div className="space-y-0.5">
            {Object.entries(agent.drives).filter(([k]) => k !== "dominant").map(([name, val]: [string, any]) => {
              if (typeof val !== "number") return null;
              const color = val > 0.7 ? "bg-red-500" : val > 0.4 ? "bg-yellow-500" : "bg-green-500";
              return (
                <div key={name} className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-600 w-16 capitalize">{name}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-1">
                    <div className={`${color} h-1 rounded-full`} style={{ width: `${val * 100}%` }} />
                  </div>
                  <span className="text-[9px] text-gray-600 w-6 text-right">{Math.round(val * 100)}%</span>
                </div>
              );
            })}
          </div>
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
          <div className="text-[10px] text-gray-500 uppercase mb-1">Today's Plan</div>
          <p className="text-gray-400">{detail.dailyPlan}</p>
        </div>
      )}

      {/* Memories */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Recent Memories
        </div>
        {detail?.memories && detail.memories.length > 0 ? (
          <div className="space-y-1">
            {[...detail.memories].reverse().map((m: any, i: number) => (
              <div
                key={i}
                className={`p-1.5 border-l-2 ${MEMORY_COLORS[m.type] || "border-gray-600"} bg-gray-800/30 rounded-r`}
              >
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-[9px]">{MEMORY_ICONS[m.type] || "\u26AA"}</span>
                  <span className="text-[9px] text-gray-600 uppercase">{m.type}</span>
                  {m.importance >= 7 && <span className="text-[9px] text-amber-500">\u2605</span>}
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
