import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { environment } from '../environments/environment';
import { ChatMessage } from './models/message.model';
import { ChatService } from './services/chat.service';
import { OrbComponent } from './components/orb/orb.component';
import { MessageBubbleComponent } from './components/message-bubble/message-bubble.component';
import { ChatInputComponent } from './components/chat-input/chat-input.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, OrbComponent, MessageBubbleComponent, ChatInputComponent, SidebarComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit, AfterViewChecked {
  @ViewChild('scrollArea') private scrollArea?: ElementRef<HTMLDivElement>;

  messages: ChatMessage[] = [];
  sessionId: string | null = null;
  backendOnline: boolean | null = null;
  isStreaming = false;

  private shouldScroll = false;

  constructor(private chat: ChatService) {}

  ngOnInit(): void {
    this.checkHealth();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll && this.scrollArea) {
      this.scrollArea.nativeElement.scrollTop = this.scrollArea.nativeElement.scrollHeight;
      this.shouldScroll = false;
    }
  }

  private async checkHealth(): Promise<void> {
    try {
      const res = await fetch(`${environment.apiBaseUrl}/api/health`);
      this.backendOnline = res.ok;
    } catch {
      this.backendOnline = false;
    }
  }

  newConversation(): void {
    this.messages = [];
    this.sessionId = null;
  }

  async onSend(text: string): Promise<void> {
    const userMessage: ChatMessage = {
      id: uid(),
      role: 'user',
      text,
      status: 'done',
      sources: []
    };

    const assistantMessage: ChatMessage = {
      id: uid(),
      role: 'assistant',
      text: '',
      status: 'searching',
      statusLabel: 'Connexion à l\u2019agent…',
      sources: []
    };

    this.messages = [...this.messages, userMessage, assistantMessage];
    this.isStreaming = true;
    this.scrollToBottom();

    const patch = (fn: (m: ChatMessage) => ChatMessage) => {
      this.messages = this.messages.map((m) => (m.id === assistantMessage.id ? fn(m) : m));
      this.scrollToBottom();
    };

    try {
      await this.chat.streamChat(text, this.sessionId, {
        onSession: (sessionId) => {
          this.sessionId = sessionId;
        },
        onStatus: (label) => {
          patch((m) => ({
            ...m,
            status: label.toLowerCase().includes('génération') ? 'generating' : 'searching',
            statusLabel: label
          }));
        },
        onSources: (sources) => {
          patch((m) => ({ ...m, sources }));
        },
        onToken: (token) => {
          patch((m) => ({ ...m, status: 'generating', text: m.text + token }));
        },
        onDone: (payload) => {
          patch((m) => ({
            ...m,
            text: payload.response,
            sources: payload.sources ?? m.sources,
            confidence: payload.confidence,
            toolUsed: payload.tool_used,
            status: 'done',
            statusLabel: undefined
          }));
        },
        onError: (message) => {
          patch((m) => ({
            ...m,
            status: 'error',
            statusLabel: undefined,
            text: m.text || `Une erreur est survenue : ${message}`
          }));
        }
      });
    } catch (err) {
      patch((m) => ({
        ...m,
        status: 'error',
        text: m.text || 'Connexion au serveur impossible. Vérifie que le backend tourne bien.'
      }));
    } finally {
      this.isStreaming = false;
    }
  }

  private scrollToBottom(): void {
    this.shouldScroll = true;
  }
}
