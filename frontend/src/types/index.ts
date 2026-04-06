// ── User & Session ────────────────────────────────────────────────────────────

export interface User {
  user_id: string;
  name: string;
  city: string;
  lat: number;
  lng: number;
}

export interface Place {
  place_id: string;
  name: string;
  rating: number;
  distance_km: number;
  address?: string;
  cuisine_type?: string;
  open_now?: boolean;
  photo_ref?: string;
  score?: number;
}

export interface ScoredPlace extends Place {
  score: number;
}

export interface SavedSelection {
  place_id: string;
  name: string;
  cuisine_type?: string;
  rating: number;
  selected_at: string;
}

// ── Agent state / API ─────────────────────────────────────────────────────────

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result?: string;
  error?: string;
}

export interface AgentTurn {
  role: 'user' | 'assistant';
  message: string;
  places?: ScoredPlace[];
  toolCalls?: ToolCall[];
  timestamp: number;
}

export interface AgentState {
  user_id: string;
  session_id: string;
  user_message: string;
  final_response: string;
  is_done: boolean;
  places_scored?: ScoredPlace[];
  tool_calls?: ToolCall[];
}

export interface ApiError {
  detail: string;
}

// ── UI ────────────────────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
