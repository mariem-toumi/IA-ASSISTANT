import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import { Conversation, ConversationMessage, Source } from '../models/message.model';
import { getVisitorId } from './visitor';

export interface StreamEvent {
  type: 'session' | 'status' | 'sources' | 'token' | 'done' | 'error';
  data: any;
}

export interface StreamHandlers {
  onSession?: (sessionId: string) => void;
  onStatus?: (label: string) => void;
  onSources?: (sources: Source[]) => void;
  onToken?: (token: string) => void;
  onDone?: (payload: { response: string; sources: Source[]; confidence: string; tool_used: boolean }) => void;
  onError?: (message: string) => void;
}

/**
 * Parle au backend Flask /api/chat/stream (Server-Sent Events).
 * On utilise fetch + ReadableStream plutôt que EventSource natif car
 * EventSource ne permet pas d'envoyer un corps JSON en POST.
 *
 * Chaque appel inclut un visitor_id anonyme (généré côté navigateur, voir
 * visitor.ts) pour que l'historique de chaque visiteur reste privé.
 */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly baseUrl = environment.apiBaseUrl;

  async streamChat(message: string, sessionId: string | null, handlers: StreamHandlers, signal?: AbortSignal): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId ?? undefined,
        visitor_id: getVisitorId()
      }),
      signal
    });

    if (!response.ok || !response.body) {
      handlers.onError?.(`Le serveur a répondu avec le statut ${response.status}.`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split('\n\n');
      buffer = events.pop() ?? '';

      for (const rawEvent of events) {
        const line = rawEvent.trim();
        if (!line.startsWith('data:')) continue;

        const jsonPart = line.slice('data:'.length).trim();
        if (!jsonPart) continue;

        try {
          const parsed: StreamEvent = JSON.parse(jsonPart);
          this.dispatch(parsed, handlers);
        } catch {
          // fragment JSON incomplet ou malformé -> ignoré silencieusement
        }
      }
    }
  }

  /** Liste LES conversations DE CE visiteur, les plus récentes en premier. */
  async getConversations(): Promise<Conversation[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/conversations?visitor_id=${encodeURIComponent(getVisitorId())}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.conversations ?? [];
    } catch {
      return [];
    }
  }

  /** Recherche par mot-clé, restreinte aux conversations de ce visiteur. */
  async searchConversations(query: string): Promise<Conversation[]> {
    try {
      const params = new URLSearchParams({ q: query, visitor_id: getVisitorId() });
      const res = await fetch(`${this.baseUrl}/api/conversations/search?${params.toString()}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.results ?? [];
    } catch {
      return [];
    }
  }

  /** Récupère les messages d'une conversation (uniquement si elle appartient à ce visiteur). */
  async getConversationMessages(sessionId: string): Promise<ConversationMessage[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/conversations/${sessionId}?visitor_id=${encodeURIComponent(getVisitorId())}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.messages ?? [];
    } catch {
      return [];
    }
  }

  /** Supprime définitivement une conversation (si elle appartient à ce visiteur). */
  async deleteConversation(sessionId: string): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/api/conversations/${sessionId}?visitor_id=${encodeURIComponent(getVisitorId())}`, {
        method: 'DELETE'
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  private dispatch(event: StreamEvent, handlers: StreamHandlers): void {
    switch (event.type) {
      case 'session':
        handlers.onSession?.(event.data);
        break;
      case 'status':
        handlers.onStatus?.(event.data);
        break;
      case 'sources':
        handlers.onSources?.(event.data);
        break;
      case 'token':
        handlers.onToken?.(event.data);
        break;
      case 'done':
        handlers.onDone?.(event.data);
        break;
      case 'error':
        handlers.onError?.(typeof event.data === 'string' ? event.data : 'Une erreur est survenue.');
        break;
    }
  }
}
