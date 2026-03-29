import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { AGENT_COLORS } from "../../utils/formatting";
import MindTab from "./MindTab";
import RelationshipsTab from "./RelationshipsTab";

const TABS = ["Status", "Mind", "Relations", "Skills", "Knowledge", "Inventory"] as const;
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
      <div className="flex border-b border-gray-800 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-shrink-0 px-2 py-1.5 text-[9px] uppercase tracking-wider ${
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
        {tab === "Skills" && <SkillsContent agent={agent} detail={detail} />}
        {tab === "Knowledge" && <KnowledgeContent agent={agent} detail={detail} />}
        {tab === "Inventory" && <InventoryContent agent={agent} detail={detail} />}
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
        <Row label="Plan Mode" value={(detail?.planMode || agent.planMode || "improvising").replace(/_/g, " ")} />
        <Row
          label="Wealth"
          value={`${agent.state.wealth} coins`}
          valueClass="text-amber-400"
        />
      </div>

      {(detail?.currentPlanStep || agent.currentPlanStep) && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Current Plan Step</div>
          <div className="p-2 bg-amber-900/10 border border-amber-900/30 rounded text-gray-300">
            {((detail?.currentPlanStep || agent.currentPlanStep)?.label) || `${(detail?.currentPlanStep || agent.currentPlanStep)?.activity} at ${(detail?.currentPlanStep || agent.currentPlanStep)?.location}`}
          </div>
          {(detail?.planDeviationReason || agent.planDeviationReason) && (
            <div className="mt-1 text-[10px] text-red-300/80">
              Off-plan because of {detail?.planDeviationReason || agent.planDeviationReason}.
            </div>
          )}
        </div>
      )}

      {(detail?.decisionRationale || agent.decisionRationale) && (detail?.decisionRationale?.chosen || agent.decisionRationale?.chosen) && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Decision Rationale</div>
          <div className="p-2 bg-cyan-950/20 border border-cyan-900/30 rounded text-[11px]">
            <div className="text-cyan-300">{(detail?.decisionRationale || agent.decisionRationale).chosen.description}</div>
            <div className="text-gray-400 mt-1">{(detail?.decisionRationale || agent.decisionRationale).chosen.why}</div>
            <div className="text-[10px] text-gray-500 mt-1">
              Source: {(detail?.decisionRationale || agent.decisionRationale).chosen.source} | Score: {((detail?.decisionRationale || agent.decisionRationale).chosen.score ?? 0).toFixed?.(2) ?? (detail?.decisionRationale || agent.decisionRationale).chosen.score}
            </div>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        <BarRow label="Energy" value={agent.state.energy} color="bg-green-500" />
        <BarRow label="Hunger" value={agent.state.hunger} color="bg-orange-500" />
        <BarRow label="Mood" value={agent.state.mood} color="bg-blue-500" />
      </div>

      {/* Drives */}
      {agent.drives && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Drives</div>
          <div className="space-y-0.5">
            {Object.entries(agent.drives).filter(([k]) => k !== "dominant").map(([name, val]: [string, any]) => {
              if (typeof val !== "number") return null;
              const driveColor = val > 0.7 ? "bg-red-500" : val > 0.4 ? "bg-yellow-500" : "bg-green-500";
              return (
                <div key={name} className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-600 w-16 capitalize">{name}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-1">
                    <div className={`${driveColor} h-1 rounded-full`} style={{ width: `${val * 100}%` }} />
                  </div>
                  <span className="text-[9px] text-gray-600 w-6 text-right">{Math.round(val * 100)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {detail?.backstory && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Backstory</div>
          <p className="text-gray-400">{detail.backstory}</p>
        </div>
      )}

      {detail?.identityNarrative && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Identity Narrative</div>
          <p className="text-gray-400">{detail.identityNarrative}</p>
        </div>
      )}

      {detail?.activeConflicts && detail.activeConflicts.length > 0 && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Active Conflicts</div>
          <div className="space-y-1">
            {detail.activeConflicts.slice(0, 4).map((conflict: any, i: number) => (
              <div key={i} className="p-2 rounded bg-red-950/20 border border-red-900/30 text-[11px]">
                <div className="text-red-200">{conflict.with}</div>
                <div className="text-gray-400">{conflict.summary}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {detail?.currentInstitutionRoles && detail.currentInstitutionRoles.length > 0 && (
        <div className="pt-2 border-t border-gray-800">
          <div className="text-[10px] text-gray-500 uppercase mb-1">Institution Roles</div>
          <div className="space-y-1">
            {detail.currentInstitutionRoles.slice(0, 4).map((role: any, i: number) => (
              <div key={i} className="text-[11px] text-gray-400">
                {role.institution_name}: {role.role}
              </div>
            ))}
          </div>
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

function SkillsContent({ agent, detail }: { agent: any; detail: any }) {
  const skills = detail?.skills || {};
  const physicalTraits = detail?.physicalTraits || {};
  const worldObjects = useSimulationStore((s) => s.worldObjects);
  const createdObjects = worldObjects.filter(
    (o) => o.created_by === agent.name || o.created_by === agent.id
  );

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
                  <span className="text-[9px] text-gray-500">
                    {data.attempts || 0}a / {data.successes || 0}s
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Objects created by this agent */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Creations ({createdObjects.length})
        </div>
        {createdObjects.length === 0 ? (
          <p className="text-gray-600 italic">No objects created yet</p>
        ) : (
          <div className="space-y-0.5">
            {createdObjects.map((obj) => (
              <div key={obj.id} className="p-1.5 bg-gray-800/30 rounded text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">{obj.name}</span>
                  <span className="text-[9px] text-gray-600 capitalize">{obj.category}</span>
                </div>
                {obj.description && (
                  <div className="text-gray-500 mt-0.5">{obj.description}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {detail?.schedule && detail.schedule.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Daily Schedule</div>
          <div className="space-y-1">
            {detail.schedule.map((step: any, i: number) => (
              <div key={i} className={`p-1.5 rounded border text-[10px] ${detail?.currentPlanStep?.hour === step.hour && detail?.currentPlanStep?.activity === step.activity ? "bg-amber-900/15 border-amber-700/40 text-amber-200" : "bg-gray-800/30 border-gray-800 text-gray-400"}`}>
                <div>{step.label || `${String(step.hour).padStart(2, "0")}:00 ${step.activity}`}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KnowledgeContent({ agent, detail }: { agent: any; detail: any }) {
  const worldKnowledge = detail?.worldKnowledge || {};
  const beliefs = detail?.beliefs || [];
  const mentalModels = detail?.mentalModels || {};

  return (
    <div className="space-y-3 text-xs">
      {/* Beliefs with confidence */}
      {beliefs.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Beliefs ({beliefs.length})
          </div>
          <div className="space-y-0.5">
            {beliefs.slice(0, 12).map((b: any, i: number) => (
              <div key={i} className="text-[10px] text-gray-400 p-1.5 bg-gray-800/20 rounded flex items-start gap-1">
                <div className="flex-1">{b.content}</div>
                <div className="flex items-center gap-1 shrink-0">
                  <div className="w-8 bg-gray-800 rounded-full h-1">
                    <div
                      className={`h-1 rounded-full ${b.confidence > 0.7 ? "bg-green-500" : b.confidence > 0.4 ? "bg-yellow-500" : "bg-gray-500"}`}
                      style={{ width: `${(b.confidence || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-gray-600 text-[9px]">{Math.round((b.confidence || 0) * 100)}%</span>
                  {b.questioned && <span className="text-amber-400">?</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Discovered Locations */}
      {worldKnowledge.locations && Object.keys(worldKnowledge.locations).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Discovered Places ({Object.keys(worldKnowledge.locations).length})
          </div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(worldKnowledge.locations).map(([loc, data]: [string, any]) => (
              <span key={loc} className="text-[9px] px-1.5 py-0.5 bg-gray-800 rounded text-gray-400" title={data?.notes || ""}>
                {loc.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* World knowledge entries (other than locations) */}
      {Object.keys(worldKnowledge).filter(k => k !== "locations").length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">World Knowledge</div>
          <div className="space-y-1">
            {Object.entries(worldKnowledge)
              .filter(([k]) => k !== "locations")
              .slice(0, 10)
              .map(([key, val]: [string, any]) => (
                <div key={key} className="p-1.5 bg-gray-800/20 rounded text-[10px]">
                  <span className="text-gray-400 capitalize">{key.replace(/_/g, " ")}: </span>
                  <span className="text-gray-500">
                    {typeof val === "object" ? JSON.stringify(val).slice(0, 80) : String(val)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Mental Models */}
      {Object.keys(mentalModels).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Mental Models ({Object.keys(mentalModels).length})
          </div>
          <div className="space-y-1">
            {Object.entries(mentalModels).slice(0, 6).map(([name, model]: [string, any]) => (
              <div key={name} className="text-[10px] p-1.5 bg-gray-800/30 rounded">
                <span className="text-gray-300">{name}</span>
                <div className="flex gap-2 mt-0.5 text-[9px] text-gray-600">
                  {model.trust !== undefined && <span>trust: {model.trust?.toFixed?.(1) ?? model.trust}</span>}
                  {model.reliability !== undefined && <span>rely: {model.reliability?.toFixed?.(1) ?? model.reliability}</span>}
                  {model.emotional_safety !== undefined && <span>safe: {model.emotional_safety?.toFixed?.(1) ?? model.emotional_safety}</span>}
                </div>
                {model.personality && <div className="text-[9px] text-gray-500 mt-0.5">{model.personality.slice(0, 60)}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposal Stances */}
      {detail?.proposalStances && Object.keys(detail.proposalStances).length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Proposal Stances</div>
          <div className="space-y-1">
            {Object.entries(detail.proposalStances).slice(0, 5).map(([proposalId, stance]: [string, any]) => (
              <div key={proposalId} className="p-1.5 bg-gray-800/20 border border-gray-800 rounded text-[10px]">
                <div className="text-gray-300">{proposalId}</div>
                <div className="text-gray-500">{stance.stance} | legitimacy {stance.legitimacy}</div>
                {stance.reason && <div className="text-gray-600">{stance.reason}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InventoryContent({ agent, detail }: { agent: any; detail: any }) {
  const inventory = (agent as any)?.inventory || detail?.inventory || [];
  const worldObjects = useSimulationStore((s) => s.worldObjects);
  const ownedObjects = worldObjects.filter(
    (o) => o.owner === agent.name || o.owner === agent.id
  );
  const currentCommitment = detail?.currentCommitment;

  return (
    <div className="space-y-3 text-xs">
      {/* Inventory items */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase mb-1">
          Inventory ({inventory.length})
        </div>
        {inventory.length === 0 ? (
          <p className="text-gray-600 italic">Empty hands</p>
        ) : (
          <div className="space-y-0.5">
            {inventory.map((item: any, i: number) => (
              <div key={i} className="text-gray-400 p-1 bg-gray-800/20 rounded flex items-center justify-between">
                <span>{item.name || item}</span>
                {item.quantity && <span className="text-gray-600">x{item.quantity}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* World objects owned */}
      {ownedObjects.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">
            Owned Objects ({ownedObjects.length})
          </div>
          <div className="space-y-0.5">
            {ownedObjects.map((obj) => (
              <div key={obj.id} className="p-1.5 bg-gray-800/20 rounded text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">{obj.name}</span>
                  <span className="text-[9px] text-gray-600 capitalize">{obj.category} / {obj.size}</span>
                </div>
                {obj.description && <div className="text-gray-500 mt-0.5">{obj.description}</div>}
                {obj.effects && Object.keys(obj.effects).length > 0 && (
                  <div className="flex gap-1 mt-0.5">
                    {Object.entries(obj.effects).map(([k, v]) => (
                      <span key={k} className={`text-[9px] px-1 rounded ${v > 0 ? "bg-green-900/30 text-green-400" : "bg-red-900/30 text-red-400"}`}>
                        {k}: {v > 0 ? "+" : ""}{v}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Wealth */}
      <div className="p-2 bg-amber-900/10 border border-amber-900/30 rounded">
        <div className="flex items-center justify-between">
          <span className="text-gray-500">Coins</span>
          <span className="text-amber-400 font-medium">{agent.state.wealth}</span>
        </div>
      </div>

      {currentCommitment && (
        <div>
          <div className="text-[10px] text-gray-500 uppercase mb-1">Current Commitment</div>
          <div className="p-2 bg-cyan-900/15 border border-cyan-900/30 rounded text-gray-300">
            {(currentCommitment.description || currentCommitment.what) ?? "Following through on a plan"}
          </div>
        </div>
      )}
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
