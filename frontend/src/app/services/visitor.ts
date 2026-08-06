const VISITOR_KEY = 'live_visitor_id';

/**
 * Retourne un identifiant anonyme unique pour ce navigateur, généré une seule
 * fois et stocké en local. Sert à isoler l'historique de chaque visiteur du
 * site (personne d'autre ne peut voir tes conversations, et toi tu ne vois
 * pas celles des autres), sans avoir besoin d'un vrai système de compte.
 */
export function getVisitorId(): string {
  let id = localStorage.getItem(VISITOR_KEY);
  if (!id) {
    id = (crypto as any).randomUUID
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(VISITOR_KEY, id);
  }
  return id;
}
