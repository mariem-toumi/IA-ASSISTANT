import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Conversation } from '../../models/message.model';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent implements OnInit, OnChanges {
  @Input() sessionId: string | null = null;
  @Input() backendOnline: boolean | null = null; // null = vérification en cours
  @Input() activeSessionId: string | null = null;
  @Input() refreshTrigger: unknown; // change de valeur -> recharge la liste
  @Output() newConversation = new EventEmitter<void>();
  @Output() selectConversation = new EventEmitter<string>();
  @Output() conversationDeleted = new EventEmitter<string>();

  conversations: Conversation[] = [];
  searchQuery = '';
  searchResults: Conversation[] | null = null; // null = pas de recherche active
  isSearching = false;
  isLoading = false;
  deletingId: string | null = null;

  private searchDebounce?: ReturnType<typeof setTimeout>;

  constructor(private chat: ChatService) {}

  ngOnInit(): void {
    this.loadConversations();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['refreshTrigger'] && !changes['refreshTrigger'].firstChange) {
      this.loadConversations();
    }
  }

  private async loadConversations(): Promise<void> {
    this.isLoading = true;
    this.conversations = await this.chat.getConversations();
    this.isLoading = false;
  }

  onSearchInput(): void {
    clearTimeout(this.searchDebounce);

    const query = this.searchQuery.trim();
    if (!query) {
      this.searchResults = null;
      return;
    }

    this.searchDebounce = setTimeout(async () => {
      this.isSearching = true;
      this.searchResults = await this.chat.searchConversations(query);
      this.isSearching = false;
    }, 300);
  }

  clearSearch(): void {
    this.searchQuery = '';
    this.searchResults = null;
  }

  onSelect(sessionId: string): void {
    this.selectConversation.emit(sessionId);
  }

  onNewConversation(): void {
    this.clearSearch();
    this.newConversation.emit();
  }

  async onDelete(event: Event, sessionId: string, title: string): Promise<void> {
    event.stopPropagation(); // évite de déclencher onSelect en même temps

    const confirmed = window.confirm(`Supprimer définitivement "${title}" ?`);
    if (!confirmed) return;

    this.deletingId = sessionId;
    const success = await this.chat.deleteConversation(sessionId);
    this.deletingId = null;

    if (success) {
      this.conversations = this.conversations.filter((c) => c.session_id !== sessionId);
      if (this.searchResults) {
        this.searchResults = this.searchResults.filter((c) => c.session_id !== sessionId);
      }
      this.conversationDeleted.emit(sessionId);
    }
  }

  get displayedList(): Conversation[] {
    return this.searchResults ?? this.conversations;
  }

  relativeTime(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "à l'instant";
    if (minutes < 60) return `il y a ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `il y a ${hours} h`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `il y a ${days} j`;
    return new Date(iso).toLocaleDateString('fr-FR');
  }

  get shortSession(): string {
    return this.sessionId ? this.sessionId.slice(0, 8) : '—';
  }
}
