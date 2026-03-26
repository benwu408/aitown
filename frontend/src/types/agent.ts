export type ActionType =
  | "idle"
  | "walking"
  | "working"
  | "talking"
  | "buying"
  | "selling"
  | "eating"
  | "sleeping"
  | "delivering"
  | "attending_event"
  | "reflecting"
  | "arguing"
  | "celebrating"
  | "stealing"
  | "giving"
  | "announcing";

export interface AgentData {
  id: string;
  name: string;
  age: number;
  job: string;
  position: [number, number];
  currentLocation: string;
  currentAction: ActionType;
  emotion: string;
  innerThought: string;
  colorIndex: number;
  state: {
    energy: number;
    hunger: number;
    mood: number;
    wealth: number;
  };
}

export interface AgentDetail extends AgentData {
  personality: Record<string, number>;
  values: string[];
  goals: string[];
  fears: string[];
  backstory: string;
  dailyPlan: string;
  memories: any[];
  relationships: Record<string, any>;
  schedule: Array<{ hour: number; location: string; activity: string }>;
}

export interface GameEvent {
  type: string;
  agentId?: string;
  action?: ActionType;
  targetLocation?: string;
  targetAgent?: string;
  path?: [number, number][];
  speech?: string;
  innerThought?: string;
  emotion?: string;
  item?: string;
}

export interface SimTime {
  tick_in_day: number;
  day: number;
  hour: number;
  minute: number;
  time_string: string;
  time_of_day: string;
  season: string;
  weather: string;
  is_night: boolean;
}

export interface TickData {
  tick: number;
  time: SimTime;
  events: GameEvent[];
  agents: AgentData[];
}
