export type MessageRole = 'user' | 'assistant';

export type Confidence = 'haute' | 'moyenne' | 'faible' | 'low' | 'n/a' | 'unknown' | string;

export interface Source {
  title: string;
  url: string;
  content?: string;
  score?: number;
}

export interface Conversation {
  session_id: string;
  title: string;
  updated_at: string;
  message_count?: number;
  snippet?: string;
}

export interface ConversationMessage {
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  status: 'pending' | 'searching' | 'generating' | 'done' | 'error';
  sources: Source[];
  confidence?: Confidence;
  toolUsed?: boolean;
  statusLabel?: string;
}
