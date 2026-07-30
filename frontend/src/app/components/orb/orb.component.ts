import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

export type OrbStatus = 'idle' | 'searching' | 'generating' | 'done' | 'error';
export type OrbSize = 'hero' | 'button';

/**
 * L'orbe "Live" — élément signature de l'interface.
 * Repos : respiration lente du dégradé aurore.
 * Recherche : anneau de balayage qui tourne (l'agent explore le web).
 * Génération : pulsation plus rapide, légèrement plus lumineuse.
 * Terminé : bref halo émeraude "vérifié" puis retour au repos.
 */
@Component({
  selector: 'app-orb',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './orb.component.html',
  styleUrl: './orb.component.scss'
})
export class OrbComponent {
  @Input() status: OrbStatus = 'idle';
  @Input() size: OrbSize = 'hero';
  @Input() interactive = false;
  @Output() activate = new EventEmitter<void>();

  onClick(): void {
    if (this.interactive) this.activate.emit();
  }
}
