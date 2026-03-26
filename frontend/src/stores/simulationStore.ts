import { create } from "zustand";
import { AgentData, AgentDetail, GameEvent, SimTime } from "../types/agent";

interface FeedEntry {
  id: number;
  tick: number;
  time: string;
  type: string;
  agentId?: string;
  agentName?: string;
  text: string;
}

interface SimulationState {
  connected: boolean;
  tick: number;
  time: SimTime | null;
  speed: number;
  agents: Record<string, AgentData>;
  selectedAgentId: string | null;
  selectedAgentDetail: AgentDetail | null;
  feed: FeedEntry[];
  dashboardData: any | null;

  setConnected: (v: boolean) => void;
  updateFromTick: (data: {
    tick: number;
    time: SimTime;
    events: GameEvent[];
    agents: AgentData[];
  }) => void;
  initFromWorldState: (data: {
    tick: number;
    time: SimTime;
    agents: AgentData[];
    weather: string;
    speed: number;
  }) => void;
  selectAgent: (id: string | null) => void;
  setAgentDetail: (detail: AgentDetail | null) => void;
  setSpeed: (speed: number) => void;
  setDashboardData: (data: any) => void;
}

let feedCounter = 0;

export const useSimulationStore = create<SimulationState>((set, get) => ({
  connected: false,
  tick: 0,
  time: null,
  speed: 1,
  agents: {},
  selectedAgentId: null,
  selectedAgentDetail: null,
  feed: [],
  dashboardData: null,

  setConnected: (v) => set({ connected: v }),

  initFromWorldState: (data) => {
    const agents: Record<string, AgentData> = {};
    for (const a of data.agents) {
      agents[a.id] = a;
    }
    set({
      tick: data.tick,
      time: data.time,
      speed: data.speed,
      agents,
    });
  },

  updateFromTick: (data) => {
    const agents: Record<string, AgentData> = {};
    for (const a of data.agents) {
      agents[a.id] = a;
    }

    // Generate feed entries from events
    const newFeedEntries: FeedEntry[] = [];
    for (const event of data.events) {
      const agent = agents[event.agentId || ""];
      let text = "";

      // System events (god mode) — no agent required
      if (event.type === "system_event") {
        const e = event as any;
        text = `[EVENT] ${e.label || e.eventType}: ${e.description || ""}`;
      } else if (event.type === "agent_thought") {
        const e = event as any;
        const name = agent?.name || e.agentId || "Someone";
        text = `${name} thinks: "${e.thought}"`;
      } else if (event.type === "transaction") {
        const e = event as any;
        const name = agent?.name || "Someone";
        text = `${name} ${e.action === "buy" ? "bought" : "sold"} ${e.item} for ${e.price} coins`;
      } else if (event.type === "gossip") {
        const e = event as any;
        const name = agent?.name || "Someone";
        text = `${name} heard gossip about ${e.about}`;
      } else if (!agent) {
        continue;
      } else if (event.type === "agent_move" && event.targetLocation) {
        text = `${agent.name} is walking to ${formatLocation(event.targetLocation)}`;
      } else if (event.type === "agent_action") {
        text = `${agent.name} is ${event.action} at ${formatLocation(agent.currentLocation)}`;
      } else if (event.type === "agent_speak") {
        text = `${agent.name}: "${event.speech}"`;
      }

      if (text) {
        newFeedEntries.push({
          id: ++feedCounter,
          tick: data.tick,
          time: data.time.time_string,
          type: event.type,
          agentId: event.agentId,
          agentName: agent.name,
          text,
        });
      }
    }

    set((state) => ({
      tick: data.tick,
      time: data.time,
      agents,
      feed: [...newFeedEntries, ...state.feed].slice(0, 200),
    }));
  },

  selectAgent: (id) => set({ selectedAgentId: id, selectedAgentDetail: null }),
  setAgentDetail: (detail) => set({ selectedAgentDetail: detail }),
  setSpeed: (speed) => set({ speed }),
  setDashboardData: (data: any) => set({ dashboardData: data }),
}));

function formatLocation(id: string): string {
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
