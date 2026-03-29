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
    items?: Array<string | { content: string; priority?: number; persistent?: boolean; source?: string }>;
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
  conversationId?: string;
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

export interface WorldObject {
  id: string;
  name: string;
  description: string;
  category: 'tool' | 'structure' | 'container' | 'food' | 'medicine' | 'art' | 'clothing' | 'document' | 'marker' | 'furniture' | 'mechanism' | 'other';
  effects: Record<string, number>;
  durability: number;
  size: 'tiny' | 'small' | 'medium' | 'large' | 'structure';
  portable: boolean;
  visual_description: string;
  created_by: string;
  created_on: number;
  location: string | null;
  owner: string | null;
}

export interface ActionResultEvent {
  agent_name: string;
  action_description: string;
  success: boolean;
  outcome_description: string;
  objects_created: string[];
  tick: number;
}

export interface InnovationEvent {
  id: string;
  name: string;
  description: string;
  inventor: string;
  invented_on: number;
  adoption_rate: number;
  adopters: string[];
  parent_id?: string;
}

export interface PatternEvent {
  type: 'economic' | 'social' | 'norm' | 'conflict' | 'innovation';
  name: string;
  description: string;
  emerged_on: number;
}

export interface TimelineEvent {
  tick: number;
  day: number;
  type: string;
  title: string;
  description: string;
  agents_involved: string[];
}
