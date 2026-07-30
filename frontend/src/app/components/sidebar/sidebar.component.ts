import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  @Input() sessionId: string | null = null;
  @Input() backendOnline: boolean | null = null; // null = vérification en cours
  @Output() newConversation = new EventEmitter<void>();

  get shortSession(): string {
    return this.sessionId ? this.sessionId.slice(0, 8) : '—';
  }
}
