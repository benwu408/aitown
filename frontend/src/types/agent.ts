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
  summary?: string;
  state: {
    energy: number;
    hunger: number;
    mood: number;
    wealth: number;
  };
  workingMemory?: {
    items?: string[];
    worry?: string;
    desire?: string;
    unfinished?: string;
    goal?: string;
  };
  socialCommitments?: any[];
  longTermGoals?: any[];
  activeIntentions?: any[];
  currentPlan?: any | null;
  fallbackPlan?: any | null;
  blockedReasons?: any[];
  decisionRationale?: any;
  inventory?: Array<{ name: string; quantity?: number }>;
  emotions?: Record<string, number | string>;
  drives?: Record<string, number | string>;
  currentInstitutionRoles?: any[];
  activeConflicts?: any[];
  planMode?: string;
  planDeviationReason?: string;
  currentPlanStep?: { hour: number; location: string; activity: string; label?: string } | null;
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
  activeGoals?: any[];
  longTermGoals?: any[];
  activeIntentions?: any[];
  currentPlan?: any | null;
  fallbackPlan?: any | null;
  blockedReasons?: any[];
  decisionRationale?: any;
  beliefs?: any[];
  mentalModels?: Record<string, any>;
  socialModels?: Record<string, any>;
  worldKnowledge?: Record<string, any>;
  skills?: Record<string, any>;
  socialCommitments?: any[];
  currentCommitment?: any;
  identityNarrative?: string;
  lifeEvents?: any[];
  reciprocityLedger?: Record<string, any>;
  proposalStances?: Record<string, any>;
  projectRoles?: any[];
  currentInstitutionRoles?: any[];
  activeConflicts?: any[];
  planMode?: string;
  planDeviationReason?: string;
  currentPlanStep?: { hour: number; location: string; activity: string; label?: string } | null;
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
