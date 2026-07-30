import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage } from '../../models/message.model';
import { SourceChipComponent } from '../source-chip/source-chip.component';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, SourceChipComponent],
  templateUrl: './message-bubble.component.html',
  styleUrl: './message-bubble.component.scss'
})
export class MessageBubbleComponent {
  @Input({ required: true }) message!: ChatMessage;

  get confidenceLabel(): string {
    const map: Record<string, string> = {
      haute: 'Confiance haute',
      moyenne: 'Confiance moyenne',
      faible: 'Confiance faible',
      low: 'Confiance faible'
    };
    return map[this.message.confidence ?? ''] ?? '';
  }

  get confidenceClass(): string {
    const map: Record<string, string> = {
      haute: 'is-high',
      moyenne: 'is-medium',
      faible: 'is-low',
      low: 'is-low'
    };
    return map[this.message.confidence ?? ''] ?? '';
  }
}
