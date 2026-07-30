import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Source } from '../../models/message.model';

@Component({
  selector: 'app-source-chip',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './source-chip.component.html',
  styleUrl: './source-chip.component.scss'
})
export class SourceChipComponent {
  @Input({ required: true }) source!: Source;

  get domain(): string {
    try {
      return new URL(this.source.url).hostname.replace('www.', '');
    } catch {
      return this.source.url;
    }
  }

  get initial(): string {
    return this.domain.charAt(0).toUpperCase();
  }
}
