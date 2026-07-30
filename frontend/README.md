# Live — Frontend de l'assistant IA vérifié

Interface web (HTML / CSS / JS pur, aucune installation requise) connectée à ton backend Flask (`/api/chat/stream`).

## Aperçu du design

- **Orbe animée** (dégradé violet / bleu ciel / rose) : change de comportement selon l'état de l'agent
  — pulsation douce au repos, anneau de "scan" rotatif pendant la recherche web, pulsation plus rapide pendant la génération.
- **Cartes de sources** sous chaque réponse : nom de domaine, titre, lien cliquable — la "trace de vérification" visuelle du projet.
- **Badge de confiance** coloré (vert = haute / orange = moyenne / rouge = faible / gris = connaissance générale).
- **Streaming token par token** via lecture manuelle du flux SSE (`fetch` + `ReadableStream`), pas de librairie externe.

## Lancer le frontend

Deux façons de faire, au choix :

### Option A — Ouvrir directement le fichier
Double-clique sur `index.html`. Ça fonctionne dans la plupart des cas grâce à `flask-cors`, mais certains navigateurs bloquent les requêtes `fetch` depuis un fichier local (`file://`). Si tu vois "Serveur hors ligne" alors que ton backend tourne, passe à l'option B.

### Option B — Servir via un petit serveur local (recommandé)
Dans le dossier `frontend/` :

```powershell
python -m http.server 5500
```

Puis ouvre **http://localhost:5500** dans ton navigateur.

(Ou utilise l'extension **Live Server** de VS Code : clic droit sur `index.html` → "Open with Live Server".)

## Connexion au backend

Le frontend appelle par défaut :
```
http://localhost:5001
```

Si ton backend Flask tourne sur un autre port, modifie cette ligne tout en haut de `js/app.js` :

```js
const API_BASE = "http://localhost:5001";
```

⚠️ Assure-toi que ton serveur Flask (`python app.py`) tourne **avant** d'ouvrir le frontend.

## Structure du projet

```
frontend/
├── index.html      # structure de la page
├── css/
│   └── style.css   # design system (couleurs, typographie, animations)
├── js/
│   └── app.js       # logique : appel SSE, rendu des messages, états de l'orbe
└── README.md
```

## Personnalisation rapide

- **Couleurs** : toutes les variables sont en haut de `css/style.css`, dans `:root` (ex: `--violet`, `--sky`, `--pink`, `--teal`).
- **Suggestions de questions** : modifie les boutons `.chip` dans `index.html` (section `<div class="chips">`).
- **Nom affiché** : remplace "Mariouma" dans `index.html` (`<h1>Bonjour, <span class="accent">Mariouma</span></h1>`).

## Intégration future dans Angular

Cette version vanilla JS est pensée pour être testée immédiatement. Si tu veux la porter dans ton projet Angular (ToumiSmart-style) plus tard, la logique importante à reprendre est dans `js/app.js` :
- la fonction `streamChat()` (lecture du flux SSE)
- la fonction `handleEvent()` (dispatch des événements `session` / `status` / `sources` / `token` / `done` / `error`)

Le CSS peut être repris quasiment tel quel dans un composant Angular (styles scoped).
