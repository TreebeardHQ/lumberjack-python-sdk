export interface LogEntry {
  id: string; // Changed to required UUID string
  timestamp: number;
  level: string;
  message: string;
  service: string;
  attributes: Record<string, any>;
  trace_id?: string;
  span_id?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ServicesResponse {
  services: string[];
}

export interface WebSocketMessage {
  type: 'new_log' | 'initial_logs' | 'ping';
  data?: LogEntry | LogEntry[];
}