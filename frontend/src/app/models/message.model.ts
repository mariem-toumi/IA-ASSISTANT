export type MessageRole = 'user' | 'assistant';

export type Confidence = 'haute' | 'moyenne' | 'faible' | 'low' | 'n/a' | 'unknown' | string;

export interface Source {
  title: string;
  url: string;
  content?: string;
  score?: number;
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
