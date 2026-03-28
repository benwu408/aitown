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
  followAgentId: string | null;
  autobiography: { agentId: string; text: string } | null;
  storyHighlights: any[];
  buildings: any[];
  tileGrid: any[][] | null;
  speechBubbles: Array<{ agentId: string; text: string; expires: number }>;

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
  setFollowAgent: (id: string | null) => void;
  setAutobiography: (data: { agentId: string; text: string } | null) => void;
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
  followAgentId: null,
  autobiography: null,
  storyHighlights: [],
  buildings: [],
  tileGrid: null,
  speechBubbles: [],

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
      buildings: (data as any).buildings || [],
      tileGrid: (data as any).tileGrid || null,
    });
  },

  updateFromTick: (data) => {
    // Merge agent data — lightweight ticks only have position/action, full ticks have everything
    const prevAgents = get().agents;
    const agents: Record<string, AgentData> = { ...prevAgents };
    for (const a of data.agents) {
      if (a.state) {
        // Full agent data — replace entirely
        agents[a.id] = a;
      } else {
        // Lightweight — only update position/action/emotion, keep rest
        const existing = agents[a.id];
        if (existing) {
          agents[a.id] = { ...existing, position: a.position, currentAction: a.currentAction, currentLocation: a.currentLocation, emotion: a.emotion || existing.emotion };
        } else {
          agents[a.id] = a as any;
        }
      }
    }

    // Generate feed entries from events
    const newFeedEntries: FeedEntry[] = [];
    const newSpeechBubbles: Array<{ agentId: string; text: string; expires: number }> = [];
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
        // Create speech bubble for the map
        if (event.agentId && event.speech) {
          newSpeechBubbles.push({
            agentId: event.agentId,
            text: event.speech,
            expires: Date.now() + 4000,  // 4 seconds
          });
        }
      }

      if (text) {
        newFeedEntries.push({
          id: ++feedCounter,
          tick: data.tick,
          time: data.time.time_string,
          type: event.type,
          agentId: event.agentId,
          agentName: agent?.name,
          text,
        });
      }
    }

    // Apply tile changes if any
    const tileChanges = (data as any).tileChanges;
    const fullTileGrid = (data as any).tileGrid;
    const fullBuildings = (data as any).buildings;

    set((state) => {
      // Update tile grid if we have changes
      let tileGrid = fullTileGrid || state.tileGrid;
      if (tileChanges && tileGrid && !fullTileGrid) {
        tileGrid = tileGrid.map((row: any[]) => [...row]);
        for (const change of tileChanges) {
          if (tileGrid[change.row]) {
            tileGrid[change.row] = [...tileGrid[change.row]];
            tileGrid[change.row][change.col] = change.tile;
          }
        }
      }

      return {
        tick: data.tick,
        time: data.time,
        agents,
        feed: [...newFeedEntries, ...state.feed].slice(0, 200),
        speechBubbles: (() => {
          // Merge: new bubbles replace existing ones from the same agent
          const merged = new Map<string, { agentId: string; text: string; expires: number }>();
          for (const b of state.speechBubbles) {
            if (b.expires > Date.now()) merged.set(b.agentId, b);
          }
          for (const b of newSpeechBubbles) {
            merged.set(b.agentId, b); // newer replaces older
          }
          return [...merged.values()].slice(0, 10);
        })(),
        storyHighlights: (data as any).storyHighlights || state.storyHighlights,
        ...(tileGrid ? { tileGrid } : {}),
        ...(fullBuildings ? { buildings: fullBuildings } : {}),
      };
    });
  },

  selectAgent: (id) => set({ selectedAgentId: id, selectedAgentDetail: null }),
  setAgentDetail: (detail) => set({ selectedAgentDetail: detail }),
  setSpeed: (speed) => set({ speed }),
  setDashboardData: (data: any) => set({ dashboardData: data, storyHighlights: data?.storyHighlights || [] }),
  setFollowAgent: (id) => set({ followAgentId: id }),
  setAutobiography: (data) => set({ autobiography: data }),
}));

function formatLocation(id: string): string {
  return id
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
