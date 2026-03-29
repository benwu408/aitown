import { useEffect, useMemo, useRef, useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";
import { AGENT_COLORS } from "../../utils/formatting";

const TABS = ["overview", "agents", "timeline", "social", "constitution", "resources"] as const;
type Tab = (typeof TABS)[number];

const FEED_FILTERS = ["All", "Conversations", "Thoughts", "Actions", "Events", "Gossip"] as const;
type FeedFilter = (typeof FEED_FILTERS)[number];

const FEED_TYPE_MAP: Record<string, FeedFilter> = {
  agent_speak: "Conversations",
  agent_thought: "Thoughts",
  transaction: "Actions",
  system_event: "Events",
  gossip: "Gossip",
};

const AGENT_SORTS = ["name", "wealth", "mood", "memories"] as const;
type AgentSort = (typeof AGENT_SORTS)[number];

interface Props {
  onSend: (msg: object) => void;
  onClose: () => void;
}

function formatStoryHighlight(h: any): { title: string; detail: string } {
  const raw = String(h?.text || "").trim();
  const agentName = h?.agentName || "";
  if (raw.includes(":")) {
    const [title, ...rest] = raw.split(":");
    return { title: title.trim(), detail: rest.join(":").trim() };
  }
  return { title: agentName || "Story beat", detail: raw };
}

function buildCurrentSituations(agents: any[], feed: any[]) {
  const situations: Array<{ key: string; title: string; detail: string; tone: string; priority: number }> = [];

  for (const agent of agents) {
    const shortName = agent.name?.split(" ")[0] || agent.name || "Someone";
    if (agent.currentAction === "building") {
      situations.push({ key: `${agent.id}-building`, title: `${shortName} is building`, detail: agent.currentLocation?.replace(/_/g, " ") || "a shelter site", tone: "border-green-800/50 bg-green-950/20 text-green-200", priority: 100 });
    } else if (agent.currentAction === "talking") {
      situations.push({ key: `${agent.id}-talking`, title: `${shortName} is talking`, detail: `near ${agent.currentLocation?.replace(/_/g, " ") || "the settlement"}`, tone: "border-blue-800/50 bg-blue-950/20 text-blue-200", priority: 92 });
    } else if (agent.currentCommitment) {
      situations.push({ key: `${agent.id}-commitment`, title: `${shortName} is following through`, detail: agent.currentCommitment.description || "a commitment", tone: "border-cyan-800/50 bg-cyan-950/20 text-cyan-200", priority: 88 });
    } else if (agent.currentAction === "sleeping") {
      situations.push({ key: `${agent.id}-sleeping`, title: `${shortName} is asleep`, detail: agent.currentLocation?.replace(/_/g, " ") || "resting", tone: "border-indigo-800/50 bg-indigo-950/20 text-indigo-200", priority: 50 });
    } else if ((agent.state?.hunger || 0) > 0.78) {
      situations.push({ key: `${agent.id}-hunger`, title: `${shortName} urgently needs food`, detail: agent.innerThought || "trying to sort out hunger", tone: "border-orange-800/50 bg-orange-950/20 text-orange-200", priority: 80 });
    } else if (agent.planMode === "deviating") {
      situations.push({ key: `${agent.id}-deviating`, title: `${shortName} went off-plan`, detail: agent.planDeviationReason || agent.innerThought || "changing course", tone: "border-amber-800/50 bg-amber-950/20 text-amber-200", priority: 70 });
    }
  }

  const conversationStarts = feed
    .filter((entry: any) => entry.type === "system_event" && entry.text.includes("Conversation:"))
    .slice(0, 4)
    .map((entry: any) => ({
      key: `feed-${entry.id}`,
      title: "Conversation started",
      detail: entry.text.replace("[EVENT] ", ""),
      tone: "border-sky-800/50 bg-sky-950/20 text-sky-200",
      priority: 85,
    }));

  return [...situations, ...conversationStarts].sort((a, b) => b.priority - a.priority).slice(0, 8);
}

function collapseFeed(entries: any[]) {
  const collapsed: any[] = [];
  let i = 0;
  while (i < entries.length) {
    const entry = entries[i];
    if (entry.type === "agent_speak") {
      const group = [entry];
      let j = i + 1;
      while (j < entries.length && entries[j].type === "agent_speak" && Math.abs(entries[j].tick - entry.tick) <= 8) {
        group.push(entries[j]);
        j += 1;
      }
      const names = [...new Set(group.map((g: any) => (g.agentName || "Someone").split(" ")[0]))];
      collapsed.push({
        id: `conversation-${entry.id}`,
        type: "conversation_summary",
        tick: entry.tick,
        time: entry.time,
        title: `${names.join(" & ")} talked`,
        text: `${group.length} lines exchanged`,
        lines: group,
      });
      i = j;
      continue;
    }
    collapsed.push({ ...entry, title: entry.text, lines: null });
    i += 1;
  }
  return collapsed;
}

export default function Dashboard({ onSend, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const [feedFilter, setFeedFilter] = useState<FeedFilter>("All");
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [agentSort, setAgentSort] = useState<AgentSort>("name");
  const [rawLogOpen, setRawLogOpen] = useState(false);
  const [rawLogFrozen, setRawLogFrozen] = useState(false);
  const [rawLogSnapshot, setRawLogSnapshot] = useState<any[]>([]);
  const [newRawCount, setNewRawCount] = useState(0);
  const rawLogRef = useRef<HTMLDivElement | null>(null);

  const dashboardData = useSimulationStore((s) => s.dashboardData);
  const feed = useSimulationStore((s) => s.feed);
  const time = useSimulationStore((s) => s.time);
  const agents = useSimulationStore((s) => s.agents);
  const storyHighlights = useSimulationStore((s) => s.storyHighlights);

  useEffect(() => {
    onSend({ type: "request_dashboard" });
    const interval = setInterval(() => onSend({ type: "request_dashboard" }), 10000);
    return () => clearInterval(interval);
  }, [onSend]);

  const agentDetails = dashboardData?.agents || [];
  const townStats = dashboardData?.townStats || {};
  const debugEvents = dashboardData?.debugEvents || [];
  const quietFeed = useMemo(
    () => feed.filter((entry) => entry.type !== "agent_move" && !(entry.type === "agent_action" && entry.text.includes("is working at"))),
    [feed]
  );
  const collapsedFeed = useMemo(() => collapseFeed(quietFeed), [quietFeed]);
  const currentSituations = useMemo(
    () => buildCurrentSituations(agentDetails.length > 0 ? agentDetails : Object.values(agents), quietFeed),
    [agentDetails, agents, quietFeed]
  );

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

  useEffect(() => {
    if (!rawLogOpen || !rawLogFrozen) {
      setRawLogSnapshot(feed);
      setNewRawCount(0);
      return;
    }
    setNewRawCount(Math.max(0, feed.length - rawLogSnapshot.length));
  }, [feed, rawLogOpen, rawLogFrozen, rawLogSnapshot.length]);

  const handleRawScroll = () => {
    const el = rawLogRef.current;
    if (!el) return;
    const shouldFreeze = el.scrollTop > 24;
    if (!shouldFreeze && rawLogFrozen) {
      setRawLogFrozen(false);
      setRawLogSnapshot(feed);
      setNewRawCount(0);
      return;
    }
    if (shouldFreeze !== rawLogFrozen) setRawLogFrozen(shouldFreeze);
  };

  const unfreezeRawLog = () => {
    setRawLogFrozen(false);
    setRawLogSnapshot(feed);
    setNewRawCount(0);
    if (rawLogRef.current) rawLogRef.current.scrollTop = 0;
  };

  return (
    <div className="fixed inset-0 bg-gray-950 z-50 flex flex-col" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-gray-900 shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-bold text-amber-400">Polis Dashboard</h1>
          {time && (
            <span className="text-sm text-gray-400">
              Day {time.day} | {time.time_string} | {time.weather} | {time.season}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {debugEvents.length > 0 && (
            <span className="text-xs text-red-400 bg-red-900/30 px-2 py-0.5 rounded">
              {debugEvents.length} debug event{debugEvents.length > 1 ? "s" : ""}
            </span>
          )}
          <button onClick={onClose} className="text-gray-400 hover:text-white text-sm px-3 py-1 rounded hover:bg-gray-800">
            {"<"} Back to Town
          </button>
        </div>
      </div>

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

      <div className="flex-1 overflow-y-auto p-6">
        {tab === "overview" && (
          <OverviewTab
            stats={townStats}
            debugEvents={debugEvents}
            time={time}
            worldSummary={dashboardData?.worldSummary || ""}
            storyHighlights={dashboardData?.storyHighlights || storyHighlights}
            currentSituations={currentSituations}
            collapsedFeed={collapsedFeed}
            activeProposals={dashboardData?.activeProposals || []}
            meetings={dashboardData?.meetings || []}
            projects={dashboardData?.projects || []}
            rawLogOpen={rawLogOpen}
            onToggleRawLog={() => setRawLogOpen((v) => !v)}
          />
        )}
        {tab === "agents" && (
          <AgentsTab agents={agentDetails.length > 0 ? agentDetails : Object.values(agents)} expanded={expandedAgent} onToggle={(id) => setExpandedAgent(expandedAgent === id ? null : id)} sort={agentSort} onSort={setAgentSort} />
        )}
        {tab === "timeline" && (
          <TimelineTab feed={filteredFeed} filter={feedFilter} search={search} agentFilter={agentFilter} agents={Object.values(agents)} feedCounts={feedCounts} onFilter={setFeedFilter} onSearch={setSearch} onAgentFilter={setAgentFilter} dayRecaps={dashboardData?.dayRecaps || []} />
        )}
        {tab === "social" && <SocialTab agents={agentDetails.length > 0 ? agentDetails : []} />}
        {tab === "constitution" && <ConstitutionTab constitution={dashboardData?.constitution || {}} />}
        {tab === "resources" && <ResourcesTab resources={dashboardData?.resources || {}} />}
      </div>

      {rawLogOpen && (
        <RawLogDrawer
          feed={rawLogFrozen ? rawLogSnapshot : feed}
          frozen={rawLogFrozen}
          newCount={newRawCount}
          rawLogRef={rawLogRef}
          onScroll={handleRawScroll}
          onResume={unfreezeRawLog}
          onClose={() => setRawLogOpen(false)}
        />
      )}
    </div>
  );
}

function OverviewTab({ stats, debugEvents, time, worldSummary, storyHighlights = [], currentSituations = [], collapsedFeed = [], activeProposals = [], meetings = [], projects = [], rawLogOpen, onToggleRawLog }: any) {
  return (
    <div className="space-y-6">
      {worldSummary && (
        <div className="p-3 bg-gray-900 rounded-lg border border-gray-800 text-sm text-gray-300">
          {worldSummary}
        </div>
      )}

      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Population" value={stats.population || 15} />
        <StatCard label="Day" value={time?.day || 1} />
        <StatCard label="Season" value={time?.season || "spring"} text />
        <StatCard label="Weather" value={time?.weather || "clear"} text />
        <StatCard label="Avg Mood" value={`${Math.round((stats.avgMood || 0) * 100)}%`} color={stats.avgMood > 0.6 ? "text-green-400" : stats.avgMood > 0.3 ? "text-yellow-400" : "text-red-400"} />
        <StatCard label="Claimed Buildings" value={stats.claimedBuildings || 0} />
        <StatCard label="Unclaimed" value={stats.unclaimedBuildings || 0} />
        <StatCard label="Total Memories" value={stats.totalMemories || 0} />
        <StatCard label="Skills Found" value={stats.totalSkillsDiscovered || 0} />
        <StatCard label="Places Found" value={stats.totalLocationsDiscovered || 0} />
        <StatCard label="Proposals" value={activeProposals.length || 0} />
        <StatCard label="Projects" value={projects.length || 0} />
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-3 bg-gray-900 rounded-lg border border-gray-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs text-gray-500 uppercase">Story Highlights</h3>
            <button onClick={onToggleRawLog} className="text-[10px] text-amber-400 hover:text-amber-300">
              {rawLogOpen ? "Hide raw log" : "Open raw log"}
            </button>
          </div>
          <div className="space-y-2 max-h-[55vh] overflow-y-auto pr-1">
            {storyHighlights.length === 0 ? (
              <p className="text-xs text-gray-600 italic">No story beats yet</p>
            ) : (
              [...storyHighlights].slice(-10).reverse().map((h: any, i: number) => {
                const formatted = formatStoryHighlight(h);
                return (
                  <div key={i} className="rounded border border-gray-800 bg-gray-950/50 p-2">
                    <div className="text-xs text-amber-200 font-medium">{formatted.title}</div>
                    <div className="text-[11px] text-gray-400">{formatted.detail}</div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="col-span-6 bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-3">Current Situations</h3>
          <div className="grid grid-cols-2 gap-3">
            {currentSituations.length === 0 ? (
              <p className="text-xs text-gray-600 italic">The settlement is quiet right now.</p>
            ) : (
              currentSituations.map((s: any) => (
                <div key={s.key} className={`rounded-lg border p-3 ${s.tone}`}>
                  <div className="text-xs font-semibold">{s.title}</div>
                  <div className="text-[11px] opacity-90">{s.detail}</div>
                </div>
              ))
            )}
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[10px] text-gray-500 uppercase">Now</h4>
              <button onClick={onToggleRawLog} className="text-[10px] text-gray-400 hover:text-gray-200">
                Open raw event log
              </button>
            </div>
            <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
              {collapsedFeed.length === 0 ? (
                <p className="text-xs text-gray-600 italic">Nothing notable yet.</p>
              ) : (
                collapsedFeed.slice(0, 10).map((entry: any) => (
                  <div key={entry.id} className="rounded border border-gray-800 bg-gray-950/40 px-3 py-2">
                    <div className="flex items-center gap-2 text-[10px] text-gray-500">
                      <span>{entry.time}</span>
                      {entry.type === "conversation_summary" && <span className="text-blue-300">Conversation</span>}
                    </div>
                    <div className="text-xs text-gray-200">{entry.title || entry.text}</div>
                    <div className="text-[11px] text-gray-500">{entry.text}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-3">
              <div className="text-[10px] text-gray-500 uppercase mb-2">Active Proposals</div>
              {activeProposals.length === 0 ? <div className="text-[11px] text-gray-600 italic">No active proposals</div> : activeProposals.slice(0, 4).map((proposal: any) => (
                <div key={proposal.id} className="mb-2 text-[11px]">
                  <div className="text-amber-300">{proposal.description}</div>
                  <div className="text-gray-500">{proposal.status} | legitimacy {proposal.legitimacy}</div>
                </div>
              ))}
            </div>
            <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-3">
              <div className="text-[10px] text-gray-500 uppercase mb-2">Meetings</div>
              {meetings.length === 0 ? <div className="text-[11px] text-gray-600 italic">No meetings queued</div> : meetings.slice(0, 4).map((meeting: any) => (
                <div key={meeting.id} className="mb-2 text-[11px]">
                  <div className="text-cyan-300">{meeting.topic}</div>
                  <div className="text-gray-500">{meeting.status} at {meeting.location?.replace(/_/g, " ")}</div>
                </div>
              ))}
            </div>
            <div className="rounded-lg border border-gray-800 bg-gray-950/40 p-3">
              <div className="text-[10px] text-gray-500 uppercase mb-2">Projects</div>
              {projects.length === 0 ? <div className="text-[11px] text-gray-600 italic">No projects underway</div> : projects.slice(0, 4).map((project: any) => (
                <div key={project.id} className="mb-2 text-[11px]">
                  <div className="text-green-300">{project.name}</div>
                  <div className="text-gray-500">{project.status} | {Math.round((project.progress || 0) * 100)}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-3 space-y-3">
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h3 className="text-xs text-gray-500 uppercase mb-3">Notable Agents</h3>
            <div className="space-y-2 text-xs">
              {stats.richest && <NotableLine emoji={"$"} label="Most Resourced" name={stats.richest.name} detail={`${stats.richest.wealth}`} />}
              {stats.poorest && <NotableLine emoji={"!"} label="Least Resourced" name={stats.poorest.name} detail={`${stats.poorest.wealth}`} />}
              {stats.happiest && <NotableLine emoji={"+"} label="Happiest" name={stats.happiest.name} detail={`${Math.round(stats.happiest.mood * 100)}%`} />}
              {stats.saddest && <NotableLine emoji={"-"} label="Saddest" name={stats.saddest.name} detail={`${Math.round(stats.saddest.mood * 100)}%`} />}
              {stats.mostConnected && <NotableLine emoji={"*"} label="Most Connected" name={stats.mostConnected.name} detail={`${stats.mostConnected.connections} relationships`} />}
            </div>
          </div>

          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h3 className="text-xs text-gray-500 uppercase mb-3">Debug ({debugEvents.length || 0})</h3>
            {debugEvents.length === 0 ? (
              <p className="text-xs text-gray-600 italic">Debug is quiet.</p>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {[...debugEvents].reverse().slice(0, 8).map((e: any, i: number) => (
                  <div key={i} className="text-xs text-gray-400">
                    <span className="text-red-400">[Tick {e.tick}]</span> {e.description || e.type.replace(/_/g, " ")}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h3 className="text-xs text-gray-500 uppercase mb-3">Emergent Patterns</h3>
            <p className="text-xs text-gray-600">
              Watch the Constitution and Timeline tabs for markets, leadership, rituals, and other systems if they emerge.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function RawLogDrawer({ feed, frozen, newCount, rawLogRef, onScroll, onResume, onClose }: any) {
  const [expandedConversations, setExpandedConversations] = useState<Record<string, boolean>>({});
  const collapsed = useMemo(() => collapseFeed(feed), [feed]);

  return (
    <div className="absolute right-0 bottom-0 top-24 w-[420px] border-l border-gray-800 bg-gray-950/96 backdrop-blur-sm z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div>
          <div className="text-xs text-gray-400 uppercase">Raw Event Log</div>
          <div className="text-[11px] text-gray-600">{frozen ? "Frozen while you scroll" : "Live"}</div>
        </div>
        <div className="flex items-center gap-2">
          {newCount > 0 && (
            <button onClick={onResume} className="px-2 py-1 rounded bg-amber-700 text-white text-[11px]">
              {newCount} new events
            </button>
          )}
          <button onClick={onClose} className="text-xs text-gray-400 hover:text-white">Close</button>
        </div>
      </div>
      <div ref={rawLogRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {collapsed.map((entry: any) => (
          <div key={entry.id} className="rounded border border-gray-800 bg-gray-900/60 p-2">
            <div className="text-[10px] text-gray-600 mb-1">[{entry.time}]</div>
            {entry.type === "conversation_summary" ? (
              <>
                <button
                  onClick={() => setExpandedConversations((prev) => ({ ...prev, [entry.id]: !prev[entry.id] }))}
                  className="w-full text-left"
                >
                  <div className="text-xs text-blue-300">{entry.title}</div>
                  <div className="text-[11px] text-gray-500">{entry.text}</div>
                </button>
                {expandedConversations[entry.id] && (
                  <div className="mt-2 space-y-1 border-t border-gray-800 pt-2">
                    {entry.lines.map((line: any) => (
                      <div key={line.id} className="text-[11px] text-gray-300">{line.text}</div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-xs text-gray-300">{entry.text}</div>
            )}
          </div>
        ))}
      </div>
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
          const commitmentCount = a.socialCommitments?.length || 0;

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
                    <div className="text-amber-400 font-medium">{a.state?.wealth || 0}</div>
                    <div className="text-gray-600">{a.currentAction}</div>
                  </div>
                </div>

                <div className="space-y-1">
                  <MiniBar label="Mood" value={mood} color={mood > 60 ? "bg-green-500" : mood > 30 ? "bg-yellow-500" : "bg-red-500"} />
                  <MiniBar label="Energy" value={energy} color="bg-blue-500" />
                  <MiniBar label="Hunger" value={hunger} color="bg-orange-500" />
                </div>

                <div className="flex gap-3 mt-2 text-[9px] text-gray-500">
                  <span>{memCount} memories</span>
                  <span>{relCount} relationships</span>
                  <span>{commitmentCount} commitments</span>
                  <span className="ml-auto text-gray-600">{a.emotion}</span>
                </div>

                {a.innerThought && <div className="mt-1 text-[10px] text-gray-500 italic truncate">"{a.innerThought}"</div>}
              </div>

              {isExp && (
                <div className="border-t border-gray-800 p-3 space-y-3">
                  {a.dailyPlan && <div className="text-[10px] text-gray-400"><span className="text-gray-600 uppercase">Plan: </span>{a.dailyPlan}</div>}
                  {(a.planMode || a.currentPlanStep) && (
                    <div className="text-[10px] text-gray-400">
                      <span className="text-gray-600 uppercase">Plan Mode: </span>
                      {(a.planMode || "improvising").replace(/_/g, " ")}
                      {a.planDeviationReason ? ` (${a.planDeviationReason})` : ""}
                    </div>
                  )}
                  {a.currentPlanStep && <div className="p-2 bg-amber-900/10 border border-amber-900/30 rounded text-[10px] text-amber-100">{a.currentPlanStep.label || `${String(a.currentPlanStep.hour).padStart(2, "0")}:00 ${a.currentPlanStep.activity}`}</div>}
                  {a.goals && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-0.5">Goals</div>
                      {a.goals.map((g: string, i: number) => <div key={i} className="text-[10px] text-gray-400">- {g}</div>)}
                    </div>
                  )}
                  {a.socialCommitments && a.socialCommitments.length > 0 && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-1">Plans ({a.socialCommitments.length})</div>
                      <div className="space-y-0.5">
                        {a.socialCommitments.map((c: any, i: number) => (
                          <div key={i} className="text-[10px] text-cyan-400">{c.description || c.what} — {(c.location || c.where || "").replace(/_/g, " ")}{c.with?.length > 0 ? ` with ${c.with.join(", ")}` : ""}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  {a.schedule && a.schedule.length > 0 && (
                    <div>
                      <div className="text-[10px] text-gray-600 uppercase mb-1">Daily Schedule ({a.schedule.length})</div>
                      <div className="space-y-1">
                        {a.schedule.map((step: any, i: number) => (
                          <div key={i} className={`text-[10px] p-1.5 rounded border ${a.currentPlanStep?.hour === step.hour && a.currentPlanStep?.activity === step.activity ? "bg-amber-900/15 border-amber-700/40 text-amber-100" : "bg-gray-800/20 border-gray-800 text-gray-400"}`}>
                            {step.label || `${String(step.hour).padStart(2, "0")}:00 ${step.activity}`}
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

function TimelineTab({ feed, filter, search, agentFilter, agents, feedCounts, onFilter, onSearch, onAgentFilter, dayRecaps = [] }: any) {
  const TYPE_COLORS: Record<string, string> = {
    agent_speak: "text-blue-400", agent_thought: "text-purple-400", transaction: "text-amber-400",
    system_event: "text-red-400", gossip: "text-pink-400", agent_move: "text-gray-500", agent_action: "text-gray-400",
  };

  return (
    <div className="space-y-3">
      {dayRecaps.length > 0 && (
        <div className="space-y-1 mb-3">
          <div className="text-[10px] text-gray-500 uppercase">Daily Recaps</div>
          {[...dayRecaps].reverse().slice(0, 5).map((r: any, i: number) => (
            <div key={i} className="p-2 bg-amber-950/20 border border-amber-900/30 rounded text-xs text-gray-300">
              <span className="text-amber-400 font-medium mr-1">Day {r.day}:</span>
              {r.summary}
            </div>
          ))}
        </div>
      )}

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
      {pairs.length >= 2 && (
        <div className="grid grid-cols-2 gap-3">
          {best && <div className="bg-green-950/30 rounded-lg border border-green-900/50 p-3"><div className="text-[10px] text-green-400 uppercase mb-1">Strongest Bond</div><div className="text-xs text-gray-300">{best.a.split(" ")[0]} & {best.b.split(" ")[0]}</div><div className="text-[10px] text-gray-500">Sentiment: {best.sentiment.toFixed(2)} | Trust: {best.trust.toFixed(2)}</div></div>}
          {worst && <div className="bg-red-950/30 rounded-lg border border-red-900/50 p-3"><div className="text-[10px] text-red-400 uppercase mb-1">Weakest Bond</div><div className="text-xs text-gray-300">{worst.a.split(" ")[0]} & {worst.b.split(" ")[0]}</div><div className="text-[10px] text-gray-500">Sentiment: {worst.sentiment.toFixed(2)} | Trust: {worst.trust.toFixed(2)}</div></div>}
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">{pairs.length} relationships | Sort by:</span>
        {(["sentiment", "trust", "familiarity"] as const).map((s) => (
          <button key={s} onClick={() => setSortBy(s)} className={`px-2 py-0.5 text-xs rounded ${sortBy === s ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}>{s}</button>
        ))}
      </div>

      {pairs.length === 0 ? <p className="text-gray-600 italic">No relationships yet</p> : (
        <table className="w-full text-xs">
          <thead><tr className="text-gray-500 text-left"><th className="py-1">Agent</th><th className="py-1">With</th><th className="py-1">Sentiment</th><th className="py-1 w-12 text-right">Val</th><th className="py-1 w-12 text-right">Trust</th><th className="py-1 w-12 text-right">Fam</th><th className="py-1">Notes</th></tr></thead>
          <tbody>
            {pairs.map((p, i) => {
              const sentPct = Math.round(((p.sentiment + 1) / 2) * 100);
              const sentColor = p.sentiment > 0.6 ? "bg-green-500" : p.sentiment > 0.3 ? "bg-emerald-600" : p.sentiment > 0 ? "bg-yellow-600" : "bg-red-500";
              return (
                <tr key={i} className="hover:bg-gray-900/50 border-t border-gray-800/50">
                  <td className="py-1.5 text-gray-300">{p.a.split(" ")[0]}</td>
                  <td className="py-1.5 text-gray-300">{p.b.split(" ")[0]}</td>
                  <td className="py-1.5 pr-2"><div className="w-full bg-gray-800 rounded-full h-2 max-w-[120px]"><div className={`h-2 rounded-full ${sentColor}`} style={{ width: `${sentPct}%` }} /></div></td>
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

function ConstitutionTab({ constitution }: { constitution: any }) {
  const norms = constitution.norms || [];
  const institutions = constitution.institutions || [];
  const patterns = constitution.patterns || [];
  const history = constitution.history || [];

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h3 className="text-xs text-gray-500 uppercase mb-2">Emergent Systems</h3>
        <p className="text-sm text-gray-300">
          Leadership, markets, rituals, and other institutions only appear here once the simulation actually produces them.
        </p>
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h3 className="text-xs text-gray-500 uppercase mb-2">Detected Patterns ({patterns.length})</h3>
        {patterns.length === 0 ? <p className="text-xs text-gray-600 italic">No stable patterns detected yet</p> : (
          <div className="space-y-2">
            {patterns.map((pattern: any, i: number) => (
              <div key={i} className="text-xs text-gray-300 border border-gray-800 rounded p-2">
                <div>{pattern.name}</div>
                <div className="text-[10px] text-gray-500 mt-1">
                  {pattern.type} | day {pattern.emerged_on}
                </div>
                {pattern.description && <div className="text-[10px] text-gray-500 mt-1">{pattern.description}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <h3 className="text-xs text-gray-500 uppercase mb-2">Social Norms ({norms.length})</h3>
        {norms.length === 0 ? <p className="text-xs text-gray-600 italic">No norms have emerged yet</p> : (
          <div className="space-y-2">
            {norms.map((n: any, i: number) => (
              <div key={i} className="text-xs text-gray-300 border border-gray-800 rounded p-2">
                <div>- {typeof n === "string" ? n : n.text}</div>
                {typeof n !== "string" && (
                  <div className="text-[10px] text-gray-500 mt-1">
                    {n.category} | strength {n.strength} | violations {n.violations}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {institutions.length > 0 && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs text-gray-500 uppercase mb-2">Institutions ({institutions.length})</h3>
          {institutions.map((inst: any, i: number) => (
            <div key={i} className="text-xs text-gray-300 mb-2 border border-gray-800 rounded p-2">
              <div><span className="text-amber-400">{inst.name}</span>: {inst.purpose || "no stated purpose"}</div>
              {inst.members?.length > 0 && <div className="text-[10px] text-gray-500 mt-1">Members: {inst.members.join(", ")}</div>}
              {inst.legitimacy !== undefined && <div className="text-[10px] text-gray-600">Legitimacy: {inst.legitimacy}</div>}
            </div>
          ))}
        </div>
      )}

      {history.length > 0 && (
        <div>
          <h3 className="text-xs text-gray-500 uppercase mb-2">Change History ({history.length})</h3>
          <div className="space-y-1">{[...history].reverse().slice(0, 15).map((h: any, i: number) => <div key={i} className="text-[10px] text-gray-500"><span className="text-gray-600">[Tick {h.tick}]</span> {h.type}: {h.description}</div>)}</div>
        </div>
      )}
    </div>
  );
}

function ResourcesTab({ resources }: { resources: any }) {
  const entries = Object.entries(resources || {});
  return (
    <div className="space-y-4 max-w-2xl">
      <div className="text-xs text-gray-500">{entries.length} resource types in the world</div>
      {entries.length === 0 ? <p className="text-gray-600 italic text-sm">No resource data available</p> : (
        <div className="space-y-2">
          {entries.map(([name, data]: [string, any]) => {
            const qty = data.quantity || 0;
            const renewable = data.renewable;
            const regen = data.regen_rate || 0;
            const locations = Array.isArray(data.locations) ? data.locations : [data.locations];
            const pct = Math.min(100, (qty / 500) * 100);
            const color = qty > 100 ? "bg-green-500" : qty > 30 ? "bg-yellow-500" : "bg-red-500";
            return (
              <div key={name} className="bg-gray-900 rounded-lg border border-gray-800 p-3">
                <div className="flex items-center justify-between mb-1"><span className="text-sm text-gray-200 capitalize">{name.replace(/_/g, " ")}</span><span className="text-xs text-gray-400">{qty} {renewable ? `(+${regen}/cycle)` : "(finite)"}</span></div>
                <div className="w-full bg-gray-800 rounded-full h-2 mb-1"><div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} /></div>
                <div className="text-[10px] text-gray-600">Found at: {locations.join(", ")}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
