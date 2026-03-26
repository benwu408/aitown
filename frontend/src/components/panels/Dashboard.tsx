import { useEffect, useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { AGENT_COLORS } from "../../utils/formatting";

const TABS = ["overview", "agents", "economy", "timeline", "social"] as const;
type Tab = (typeof TABS)[number];

const FEED_FILTERS = ["All", "Conversations", "Thoughts", "Transactions", "Events", "Gossip"] as const;
type FeedFilter = (typeof FEED_FILTERS)[number];

const FEED_TYPE_MAP: Record<string, FeedFilter> = {
  agent_speak: "Conversations",
  agent_thought: "Thoughts",
  transaction: "Transactions",
  system_event: "Events",
  gossip: "Gossip",
};

const AGENT_SORTS = ["name", "wealth", "mood", "memories"] as const;
type AgentSort = (typeof AGENT_SORTS)[number];

interface Props {
  onSend: (msg: object) => void;
  onClose: () => void;
}

export default function Dashboard({ onSend, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const [feedFilter, setFeedFilter] = useState<FeedFilter>("All");
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [agentSort, setAgentSort] = useState<AgentSort>("name");

  const dashboardData = useSimulationStore((s) => s.dashboardData);
  const feed = useSimulationStore((s) => s.feed);
  const time = useSimulationStore((s) => s.time);
  const tick = useSimulationStore((s) => s.tick);
  const agents = useSimulationStore((s) => s.agents);

  useEffect(() => {
    onSend({ type: "request_dashboard" });
    const interval = setInterval(() => onSend({ type: "request_dashboard" }), 10000);
    return () => clearInterval(interval);
  }, []);

  const agentDetails = dashboardData?.agents || [];
  const economy = dashboardData?.economy || {};
  const townStats = dashboardData?.townStats || {};
  const activeEvents = dashboardData?.activeEvents || [];
  const eventLog = dashboardData?.eventLog || [];

  const filteredFeed = feed.filter((entry) => {
    if (feedFilter !== "All") {
      const cat = FEED_TYPE_MAP[entry.type] || "All";
      if (cat !== feedFilter) return false;
    }
    if (agentFilter && entry.agentId !== agentFilter) return false;
    if (search) return entry.text.toLowerCase().includes(search.toLowerCase());
    return true;
  });

  const feedCounts: Record<string, number> = {};
  for (const entry of feed) {
    const cat = FEED_TYPE_MAP[entry.type] || "Other";
    feedCounts[cat] = (feedCounts[cat] || 0) + 1;
  }

  return (
    <div className="fixed inset-0 bg-gray-950 z-50 flex flex-col" onClick={(e) => e.stopPropagation()}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900 shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-bold text-amber-400">Town Dashboard</h1>
          {time && (
            <span className="text-sm text-gray-400">
              Day {time.day} | {time.time_string} | {time.weather} | {time.season}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {activeEvents.length > 0 && (
            <span className="text-xs text-red-400 bg-red-900/30 px-2 py-0.5 rounded">
              {activeEvents.length} active event{activeEvents.length > 1 ? "s" : ""}
            </span>
          )}
          <button onClick={onClose} className="text-gray-400 hover:text-white text-sm px-3 py-1 rounded hover:bg-gray-800">
            {"<"} Back to Town
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800 bg-gray-900/50 px-6 shrink-0">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs uppercase tracking-wider ${
              tab === t ? "text-amber-400 border-b-2 border-amber-400" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {tab === "overview" && <OverviewTab stats={townStats} economy={economy} activeEvents={activeEvents} eventLog={eventLog} time={time} />}
        {tab === "agents" && (
          <AgentsTab agents={agentDetails.length > 0 ? agentDetails : Object.values(agents)} expanded={expandedAgent} onToggle={(id) => setExpandedAgent(expandedAgent === id ? null : id)} sort={agentSort} onSort={setAgentSort} />
        )}
        {tab === "economy" && <EconomyTab economy={economy} agents={agentDetails.length > 0 ? agentDetails : Object.values(agents)} />}
        {tab === "timeline" && (
          <TimelineTab feed={filteredFeed} filter={feedFilter} search={search} agentFilter={agentFilter} agents={Object.values(agents)} feedCounts={feedCounts} onFilter={setFeedFilter} onSearch={setSearch} onAgentFilter={setAgentFilter} />
        )}
        {tab === "social" && <SocialTab agents={agentDetails.length > 0 ? agentDetails : []} />}
      </div>
    </div>
  );
}

/* ==================== OVERVIEW TAB ==================== */
function OverviewTab({ stats, economy, activeEvents, eventLog, time }: any) {
  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Population" value={stats.population || 15} />
        <StatCard label="Day" value={time?.day || 1} />
        <StatCard label="Season" value={time?.season || "spring"} text />
        <StatCard label="Weather" value={time?.weather || "clear"} text />
        <StatCard label="Avg Mood" value={`${Math.round((stats.avgMood || 0) * 100)}%`} color={stats.avgMood > 0.6 ? "text-green-400" : stats.avgMood > 0.3 ? "text-yellow-400" : "text-red-400"} />
        <StatCard label="Avg Wealth" value={`${Math.round(stats.avgWealth || 0)}c`} color="text-amber-400" />
        <StatCard label="Total Wealth" value={`${stats.totalWealth || 0}c`} color="text-amber-400" />
        <StatCard label="Treasury" value={`${Math.round(economy.treasury || 0)}c`} color="text-blue-400" />
        <StatCard label="Conversations" value={stats.totalConversations || 0} />
        <StatCard label="Reflections" value={stats.totalReflections || 0} />
        <StatCard label="Transactions" value={stats.totalTransactions || 0} />
        <StatCard label="Total Memories" value={stats.totalMemories || 0} />
      </div>

      {/* Notable agents */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-3">Notable Agents</h3>
          <div className="space-y-2 text-xs">
            {stats.richest && <NotableLine emoji={"$"} label="Richest" name={stats.richest.name} detail={`${stats.richest.wealth}c`} />}
            {stats.poorest && <NotableLine emoji={"!"} label="Poorest" name={stats.poorest.name} detail={`${stats.poorest.wealth}c`} />}
            {stats.happiest && <NotableLine emoji={"+"} label="Happiest" name={stats.happiest.name} detail={`${Math.round(stats.happiest.mood * 100)}%`} />}
            {stats.saddest && <NotableLine emoji={"-"} label="Saddest" name={stats.saddest.name} detail={`${Math.round(stats.saddest.mood * 100)}%`} />}
            {stats.mostConnected && <NotableLine emoji={"*"} label="Most Connected" name={stats.mostConnected.name} detail={`${stats.mostConnected.connections} relationships`} />}
          </div>
        </div>

        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-3">
            God Mode Events ({stats.totalGodEvents || 0})
          </h3>
          {eventLog.length === 0 ? (
            <p className="text-xs text-gray-600 italic">No events injected yet</p>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {[...eventLog].reverse().map((e: any, i: number) => (
                <div key={i} className="text-xs text-gray-400">
                  <span className="text-red-400">[Tick {e.tick}]</span> {e.type.replace(/_/g, " ")}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Active events */}
      {activeEvents.length > 0 && (
        <div className="bg-red-950/30 rounded-lg border border-red-900/50 p-4">
          <h3 className="text-xs text-red-400 uppercase mb-2">Active Events</h3>
          {activeEvents.map((e: any, i: number) => (
            <div key={i} className="text-xs text-gray-300">
              {e.type.replace(/_/g, " ")} — {e.remaining_ticks} ticks remaining
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color = "text-gray-100", text = false }: { label: string; value: any; color?: string; text?: boolean }) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-3">
      <div className="text-[10px] text-gray-500 uppercase">{label}</div>
      <div className={`text-lg font-bold ${color} ${text ? "capitalize text-sm" : ""}`}>{value}</div>
    </div>
  );
}

function NotableLine({ emoji, label, name, detail }: { emoji: string; label: string; name: string; detail: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-600 w-3">{emoji}</span>
      <span className="text-gray-500 w-28">{label}</span>
      <span className="text-gray-300 flex-1">{name}</span>
      <span className="text-amber-400">{detail}</span>
    </div>
  );
}

/* ==================== AGENTS TAB ==================== */
function AgentsTab({ agents, expanded, onToggle, sort, onSort }: { agents: any[]; expanded: string | null; onToggle: (id: string) => void; sort: AgentSort; onSort: (s: AgentSort) => void }) {
  const sorted = [...agents].sort((a, b) => {
    if (sort === "wealth") return (b.state?.wealth || 0) - (a.state?.wealth || 0);
    if (sort === "mood") return (b.state?.mood || 0) - (a.state?.mood || 0);
    if (sort === "memories") return (b.memories?.length || 0) - (a.memories?.length || 0);
    return (a.name || "").localeCompare(b.name || "");
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Sort by:</span>
        {AGENT_SORTS.map((s) => (
          <button key={s} onClick={() => onSort(s)} className={`px-2 py-0.5 text-xs rounded ${sort === s ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
            {s}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {sorted.map((a: any) => {
          const color = AGENT_COLORS[(a.colorIndex || 0) % AGENT_COLORS.length];
          const isExp = expanded === a.id;
          const mood = Math.round((a.state?.mood || 0) * 100);
          const energy = Math.round((a.state?.energy || 0) * 100);
          const hunger = Math.round((a.state?.hunger || 0) * 100);
          const memCount = a.memories?.length || 0;
          const relCount = a.relationships ? Object.keys(a.relationships).length : 0;
          const txnCount = a.transactions?.length || 0;

          return (
            <div key={a.id} className={`bg-gray-900 rounded-lg border ${isExp ? "border-amber-700 col-span-3" : "border-gray-800 hover:border-gray-700"} cursor-pointer`} onClick={() => onToggle(a.id)}>
              <div className="p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold" style={{ backgroundColor: `#${color.toString(16).padStart(6, "0")}` }}>
                    {a.name?.[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-200 truncate">{a.name}</div>
                    <div className="text-[10px] text-gray-500">{a.age}yo {a.job}</div>
                  </div>
                  <div className="text-right text-[10px]">
                    <div className="text-amber-400 font-medium">{a.state?.wealth || 0}c</div>
                    <div className="text-gray-600">{a.currentAction}</div>
                  </div>
                </div>

                {/* Bars */}
                <div className="space-y-1">
                  <MiniBar label="Mood" value={mood} color={mood > 60 ? "bg-green-500" : mood > 30 ? "bg-yellow-500" : "bg-red-500"} />
                  <MiniBar label="Energy" value={energy} color="bg-blue-500" />
                  <MiniBar label="Hunger" value={hunger} color="bg-orange-500" />
                </div>

                {/* Stats row */}
                <div className="flex gap-3 mt-2 text-[9px] text-gray-500">
                  <span>{memCount} memories</span>
                  <span>{relCount} relationships</span>
                  <span>{txnCount} transactions</span>
                  <span className="ml-auto text-gray-600">{a.emotion}</span>
                </div>

                {a.innerThought && (
                  <div className="mt-1 text-[10px] text-gray-500 italic truncate">"{a.innerThought}"</div>
                )}
              </div>

              {/* Expanded */}
              {isExp && (
                <div className="border-t border-gray-800 p-3 space-y-3">
                  {/* Personality */}
                  {a.personality && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-1">Personality</div>
                      <div className="grid grid-cols-5 gap-2">
                        {Object.entries(a.personality).map(([trait, val]: [string, any]) => (
                          <div key={trait}>
                            <div className="text-[9px] text-gray-500 capitalize truncate">{trait.slice(0, 4)}</div>
                            <div className="bg-gray-800 rounded-full h-1.5 mt-0.5">
                              <div className="bg-purple-500 h-1.5 rounded-full" style={{ width: `${val * 100}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {a.dailyPlan && <div className="text-[10px] text-gray-400"><span className="text-gray-600 uppercase">Plan: </span>{a.dailyPlan}</div>}

                  {a.goals && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-0.5">Goals</div>
                      {a.goals.map((g: string, i: number) => <div key={i} className="text-[10px] text-gray-400">- {g}</div>)}
                    </div>
                  )}

                  {a.fears && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-0.5">Fears</div>
                      {a.fears.map((f: string, i: number) => <div key={i} className="text-[10px] text-red-400/70">- {f}</div>)}
                    </div>
                  )}

                  {a.backstory && <div className="text-[10px] text-gray-500">{a.backstory}</div>}

                  {/* Memories */}
                  <div>
                    <div className="text-[10px] text-gray-600 uppercase mb-1">All Memories ({memCount})</div>
                    <div className="space-y-0.5 max-h-60 overflow-y-auto">
                      {[...(a.memories || [])].reverse().map((m: any, i: number) => (
                        <div key={i} className="text-[10px] text-gray-400">
                          <span className={`${m.type === "conversation" ? "text-green-500" : m.type === "reflection" ? "text-purple-500" : m.type === "emotion" ? "text-red-500" : "text-blue-500"}`}>
                            [{m.type}]
                          </span> {m.content}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Relationships */}
                  {a.relationships && Object.keys(a.relationships).length > 0 && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-1">Relationships ({relCount})</div>
                      <table className="w-full text-[10px]">
                        <thead><tr className="text-gray-600"><th className="text-left py-0.5">Name</th><th className="text-right">Sentiment</th><th className="text-right">Trust</th><th className="text-right">Familiarity</th></tr></thead>
                        <tbody>
                          {Object.entries(a.relationships).map(([name, rel]: [string, any]) => (
                            <tr key={name} className="text-gray-400">
                              <td className="py-0.5">{name}</td>
                              <td className={`text-right ${rel.sentiment > 0.6 ? "text-green-400" : rel.sentiment < 0.3 ? "text-red-400" : ""}`}>{rel.sentiment?.toFixed(2)}</td>
                              <td className={`text-right ${rel.trust > 0.6 ? "text-blue-400" : rel.trust < 0.3 ? "text-red-400" : ""}`}>{rel.trust?.toFixed(2)}</td>
                              <td className="text-right">{rel.familiarity?.toFixed(2) || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Transactions */}
                  {txnCount > 0 && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-1">Transactions ({txnCount})</div>
                      <div className="space-y-0.5 max-h-32 overflow-y-auto">
                        {[...(a.transactions || [])].reverse().slice(0, 20).map((t: any, i: number) => (
                          <div key={i} className={`text-[10px] ${t.action === "buy" ? "text-red-400" : "text-green-400"}`}>
                            {t.action === "buy" ? "Bought" : "Sold"} {t.item} for {t.price}c
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MiniBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] text-gray-600 w-10">{label}</span>
      <div className="flex-1 bg-gray-800 rounded-full h-1">
        <div className={`${color} h-1 rounded-full`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-[9px] text-gray-600 w-6 text-right">{value}%</span>
    </div>
  );
}

/* ==================== ECONOMY TAB ==================== */
function EconomyTab({ economy, agents }: { economy: any; agents: any[] }) {
  const prices = economy.prices || {};
  const basePrices = economy.basePrices || {};
  const supply = economy.supply || {};
  const demand = economy.demand || {};
  const priceHistory = economy.priceHistory || {};

  const wealthRanking = [...agents].sort((a, b) => (b.state?.wealth || 0) - (a.state?.wealth || 0));

  return (
    <div className="space-y-6">
      {/* Top stats */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Treasury" value={`${Math.round(economy.treasury || 0)}c`} color="text-blue-400" />
        <StatCard label="Total Transactions" value={economy.totalTransactions || 0} />
        <StatCard label="Items Tracked" value={Object.keys(prices).length} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Prices with base comparison */}
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-3">Prices vs Base</h3>
          <table className="w-full text-xs">
            <thead><tr className="text-gray-600"><th className="text-left py-1">Item</th><th className="text-right">Base</th><th className="text-right">Current</th><th className="text-right">Change</th><th className="text-right">Trend</th></tr></thead>
            <tbody>
              {Object.entries(prices).map(([item, price]: [string, any]) => {
                const base = basePrices[item] || price;
                const pct = Math.round(((price - base) / base) * 100);
                const history = priceHistory[item] || [];
                return (
                  <tr key={item} className="text-gray-300">
                    <td className="py-1 capitalize">{item}</td>
                    <td className="text-right text-gray-500">{base}c</td>
                    <td className="text-right text-amber-400">{price}c</td>
                    <td className={`text-right ${pct > 10 ? "text-red-400" : pct < -10 ? "text-green-400" : "text-gray-500"}`}>
                      {pct > 0 ? "+" : ""}{pct}%
                    </td>
                    <td className="text-right">
                      <MiniSparkline values={history} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Supply & Demand */}
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-3">Supply & Demand</h3>
          <div className="space-y-3">
            {Object.entries(supply).map(([item, amount]: [string, any]) => {
              const dem = demand[item] || 0;
              return (
                <div key={item}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-gray-300 capitalize">{item}</span>
                    <span className="text-gray-500">S:{Math.round(amount)} D:{Math.round(dem)}</span>
                  </div>
                  <div className="flex gap-1">
                    <div className="flex-1 bg-gray-800 rounded-full h-2 relative">
                      <div className={`h-2 rounded-full ${amount > 15 ? "bg-green-600" : amount > 5 ? "bg-yellow-600" : "bg-red-600"}`} style={{ width: `${Math.min(100, (amount / 30) * 100)}%` }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Wealth Leaderboard */}
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h3 className="text-xs text-gray-500 uppercase mb-3">Wealth Leaderboard</h3>
        <div className="grid grid-cols-3 gap-2">
          {wealthRanking.map((a: any, i: number) => {
            const color = AGENT_COLORS[(a.colorIndex || 0) % AGENT_COLORS.length];
            const maxWealth = wealthRanking[0]?.state?.wealth || 1;
            const pct = Math.round(((a.state?.wealth || 0) / maxWealth) * 100);
            return (
              <div key={a.id} className="flex items-center gap-2 text-xs">
                <span className="text-gray-600 w-4">{i + 1}.</span>
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: `#${color.toString(16).padStart(6, "0")}` }} />
                <span className="text-gray-300 flex-1 truncate">{a.name?.split(" ")[0]}</span>
                <div className="w-20 bg-gray-800 rounded-full h-1.5">
                  <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-amber-400 w-10 text-right">{a.state?.wealth || 0}c</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function MiniSparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <span className="text-gray-600">-</span>;
  const last10 = values.slice(-10);
  const min = Math.min(...last10);
  const max = Math.max(...last10);
  const range = max - min || 1;
  const w = 40;
  const h = 12;
  const points = last10.map((v, i) => `${(i / (last10.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
  const trend = last10[last10.length - 1] > last10[0];
  return (
    <svg width={w} height={h} className="inline-block">
      <polyline points={points} fill="none" stroke={trend ? "#22c55e" : "#ef4444"} strokeWidth="1.5" />
    </svg>
  );
}

/* ==================== TIMELINE TAB ==================== */
function TimelineTab({ feed, filter, search, agentFilter, agents, feedCounts, onFilter, onSearch, onAgentFilter }: any) {
  const TYPE_COLORS: Record<string, string> = {
    agent_speak: "text-blue-400", agent_thought: "text-purple-400", transaction: "text-amber-400",
    system_event: "text-red-400", gossip: "text-pink-400", agent_move: "text-gray-500", agent_action: "text-gray-400",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {FEED_FILTERS.map((f) => (
          <button key={f} onClick={() => onFilter(f)} className={`px-2 py-1 text-xs rounded ${filter === f ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
            {f} {feedCounts[f] ? `(${feedCounts[f]})` : ""}
          </button>
        ))}
        <select value={agentFilter} onChange={(e) => onAgentFilter(e.target.value)} className="bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700">
          <option value="">All agents</option>
          {agents.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <input type="text" value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search..." className="ml-auto bg-gray-800 text-gray-200 text-xs rounded px-3 py-1 border border-gray-700 w-48" />
      </div>

      <div className="text-xs text-gray-600">{feed.length} events</div>

      <div className="space-y-0.5 max-h-[65vh] overflow-y-auto">
        {feed.length === 0 ? (
          <p className="text-gray-600 italic py-4">No events match filters</p>
        ) : (
          feed.map((entry: any) => (
            <div key={entry.id} className={`text-xs py-1 px-2 rounded hover:bg-gray-900 ${TYPE_COLORS[entry.type] || "text-gray-400"}`}>
              <span className="text-gray-600 mr-2">[{entry.time}]</span>{entry.text}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ==================== SOCIAL TAB ==================== */
function SocialTab({ agents }: { agents: any[] }) {
  const [sortBy, setSortBy] = useState<"sentiment" | "trust" | "familiarity">("sentiment");
  const pairs: Array<{ a: string; b: string; sentiment: number; trust: number; familiarity: number; notes: string }> = [];
  const seen = new Set<string>();

  for (const agent of agents) {
    if (!agent.relationships) continue;
    for (const [name, rel] of Object.entries(agent.relationships) as [string, any][]) {
      const key = [agent.name, name].sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      pairs.push({ a: agent.name, b: name, sentiment: rel.sentiment ?? 0.5, trust: rel.trust ?? 0.5, familiarity: rel.familiarity ?? 0, notes: rel.notes || "" });
    }
  }

  pairs.sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));

  const best = pairs[0];
  const worst = pairs[pairs.length - 1];

  return (
    <div className="space-y-4 max-w-4xl">
      {/* Highlights */}
      {pairs.length >= 2 && (
        <div className="grid grid-cols-2 gap-3">
          {best && (
            <div className="bg-green-950/30 rounded-lg border border-green-900/50 p-3">
              <div className="text-[10px] text-green-400 uppercase mb-1">Strongest Bond</div>
              <div className="text-xs text-gray-300">{best.a.split(" ")[0]} & {best.b.split(" ")[0]}</div>
              <div className="text-[10px] text-gray-500">Sentiment: {best.sentiment.toFixed(2)} | Trust: {best.trust.toFixed(2)}</div>
            </div>
          )}
          {worst && (
            <div className="bg-red-950/30 rounded-lg border border-red-900/50 p-3">
              <div className="text-[10px] text-red-400 uppercase mb-1">Weakest Bond</div>
              <div className="text-xs text-gray-300">{worst.a.split(" ")[0]} & {worst.b.split(" ")[0]}</div>
              <div className="text-[10px] text-gray-500">Sentiment: {worst.sentiment.toFixed(2)} | Trust: {worst.trust.toFixed(2)}</div>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">{pairs.length} relationships | Sort by:</span>
        {(["sentiment", "trust", "familiarity"] as const).map((s) => (
          <button key={s} onClick={() => setSortBy(s)} className={`px-2 py-0.5 text-xs rounded ${sortBy === s ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>
            {s}
          </button>
        ))}
      </div>

      {pairs.length === 0 ? (
        <p className="text-gray-600 italic">No relationships yet</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 text-left">
              <th className="py-1">Agent</th>
              <th className="py-1">With</th>
              <th className="py-1">Sentiment</th>
              <th className="py-1 w-12 text-right">Val</th>
              <th className="py-1 w-12 text-right">Trust</th>
              <th className="py-1 w-12 text-right">Fam</th>
              <th className="py-1">Notes</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((p, i) => {
              const sentPct = Math.round(((p.sentiment + 1) / 2) * 100);
              const sentColor = p.sentiment > 0.6 ? "bg-green-500" : p.sentiment > 0.3 ? "bg-emerald-600" : p.sentiment > 0 ? "bg-yellow-600" : "bg-red-500";
              return (
                <tr key={i} className="hover:bg-gray-900/50 border-t border-gray-800/50">
                  <td className="py-1.5 text-gray-300">{p.a.split(" ")[0]}</td>
                  <td className="py-1.5 text-gray-300">{p.b.split(" ")[0]}</td>
                  <td className="py-1.5 pr-2">
                    <div className="w-full bg-gray-800 rounded-full h-2 max-w-[120px]">
                      <div className={`h-2 rounded-full ${sentColor}`} style={{ width: `${sentPct}%` }} />
                    </div>
                  </td>
                  <td className={`py-1.5 text-right ${p.sentiment > 0.6 ? "text-green-400" : p.sentiment < 0.3 ? "text-red-400" : "text-gray-400"}`}>{p.sentiment.toFixed(2)}</td>
                  <td className={`py-1.5 text-right ${p.trust > 0.6 ? "text-blue-400" : p.trust < 0.3 ? "text-red-400" : "text-gray-500"}`}>{p.trust.toFixed(2)}</td>
                  <td className="py-1.5 text-right text-gray-500">{p.familiarity.toFixed(2)}</td>
                  <td className="py-1.5 text-gray-600 truncate max-w-[150px]">{p.notes}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
