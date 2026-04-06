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

export type WsMessage = WsTokenMessage | WsDoneMessage | WsErrorMessage;

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
  places?: ScoredPlace[];
  toolCalls?: ToolCallEntry[];
  timestamp: number;
}

// ── UI ───────────────────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
