import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { OrbComponent } from '../orb/orb.component';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule, OrbComponent],
  templateUrl: './chat-input.component.html',
  styleUrl: './chat-input.component.scss'
})
export class ChatInputComponent {
  @Input() disabled = false;
  @Input() showSuggestions = false;
  @Output() send = new EventEmitter<string>();

  value = '';

  readonly suggestions = [
    { label: "Actualité du jour", prompt: "Quelles sont les principales actualités aujourd'hui ?" },
    { label: 'Vérifier un fait', prompt: 'Peux-tu vérifier une information avec plusieurs sources récentes ?' },
    { label: 'Comparer des sources', prompt: 'Compare deux sources récentes sur un même sujet et signale les divergences.' },
    { label: 'Résumer un sujet', prompt: 'Fais-moi un résumé à jour sur un sujet précis.' }
  ];

  submit(): void {
    const text = this.value.trim();
    if (!text || this.disabled) return;
    this.send.emit(text);
    this.value = '';
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.submit();
    }
  }

  useSuggestion(prompt: string): void {
    this.value = prompt;
    this.submit();
  }
}
