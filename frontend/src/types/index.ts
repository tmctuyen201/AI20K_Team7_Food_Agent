// ── User & Session ────────────────────────────────────────────────────────────

export interface User {
  user_id: string;
  name: string;
  city: string;
  lat: number;
  lng: number;
}

// ── Places ──────────────────────────────────────────────────────────────────

export interface Place {
  place_id: string;
  name: string;
  rating: number;
  distance_km: number;
  address?: string;
  cuisine_type?: string;
  open_now?: boolean;
  score?: number;
}

export interface ScoredPlace extends Place {
  score: number;
}

// ── API responses ────────────────────────────────────────────────────────────

export interface SessionResponse {
  session_id: string;
  user_id: string;
  token: string;
  expires_at: string;
}

export interface HistoryResponse {
  selections: SavedSelection[];
  total: number;
  top_cuisines: CuisineStat[];
}

export interface SavedSelection {
  place_id: string;
  name: string;
  cuisine_type?: string;
  rating: number;
  selected_at: string;
}

export interface CuisineStat {
  cuisine: string;
  count: number;
  avg_rating: number;
}

// ── Agent version ─────────────────────────────────────────────────────────────

export type AgentVersion = "v1" | "v2" | "no-tools";

// ── Reasoning / Tool result ───────────────────────────────────────────────────

export interface ReasoningStep {
  step: number;
  text: string;
  tool: string | null;
}

export interface ToolResultEntry {
  tool: string;
  result: unknown;
  error: string | null;
}

// ── Compare result ────────────────────────────────────────────────────────────

export interface CompareVersionResult {
  text: string;
  places: ScoredPlace[];
  reasoning_steps: ReasoningStep[];
  tool_results: ToolResultEntry[];
}

export interface CompareResult {
  v1: CompareVersionResult;
  v2: CompareVersionResult;
  "no-tools": CompareVersionResult;
}

// ── WebSocket protocol ───────────────────────────────────────────────────────

export interface WsTokenMessage {
  type: 'token';
  data: string;
}

export interface WsDoneMessage {
  type: 'done';
  data: {
    places: ScoredPlace[];
  };
}

export interface WsErrorMessage {
  type: 'error';
  message: string;
}

export interface WsReasoningMessage {
  type: 'reasoning';
  step: number;
  text: string;
  tool: string | null;
}

export interface WsToolResultMessage {
  type: 'tool_result';
  tool: string;
  result: unknown;
  error: string | null;
}

export interface WsCompareResultMessage {
  type: 'compare_result';
  versions: CompareResult;
}

export type WsMessage =
  | WsTokenMessage
  | WsDoneMessage
  | WsErrorMessage
  | WsReasoningMessage
  | WsToolResultMessage
  | WsCompareResultMessage;

// ── Parsed place from assistant text ──────────────────────────────────────────

export interface ParsedPlace {
  name: string;
  rating: number;
  distance_km: number;
  description: string;
  address?: string;
}

// ── Agent UI state ──────────────────────────────────────────────────────────

export interface ToolCallEntry {
  tool: string;
  args: Record<string, unknown>;
  result?: string;
  error?: string;
}

export interface AgentTurn {
  role: 'user' | 'assistant';
  message: string;
  places?: ScoredPlace[];              // from WebSocket "done" payload
  parsedPlaces?: ParsedPlace[];        // extracted from assistant text
  toolCalls?: ToolCallEntry[];
  reasoningSteps?: ReasoningStep[];    // streaming reasoning steps
  toolResults?: ToolResultEntry[];     // tool call results
  timestamp: number;
}

// ── Chat session (sidebar history) ───────────────────────────────────────────

export interface ChatSession {
  id: string;
  user_id: string;
  model: string;
  version: AgentVersion;
  title: string;        // first message, truncated
  preview: string;      // last assistant message, truncated
  turns: AgentTurn[];
  created_at: number;
  updated_at: number;
}

// ── UI ───────────────────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
