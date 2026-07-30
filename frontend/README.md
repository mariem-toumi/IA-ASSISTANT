# Live — Frontend Angular

Interface Angular 18 (standalone components) pour le Live AI Assistant : agent + recherche web + vérification de sources, avec streaming en direct (SSE).

## Design

Palette "aurore sur encre" : fond quasi noir indigo (`#0a0a12`), avec un dégradé violet → turquoise → rose réservé à l'orbe et aux halos de vérification — c'est l'élément signature de l'interface, il change d'état visuellement pendant la recherche, la génération, et la vérification des sources.

- Display : **Fraunces** (serif variable, pour le titre d'accueil)
- Corps : **Manrope**
- Données/citations : **IBM Plex Mono** (URLs, badges de confiance, session id)

## Installation

```bash
npm install
```

## Configuration du backend

Le fichier `src/environments/environment.ts` pointe par défaut sur :

```ts
apiBaseUrl: 'http://localhost:5001'
```

Adapte cette valeur si ton backend Flask tourne sur un autre port (vérifie `PORT` dans `config.py` côté backend).

## Lancer en développement

```bash
npm start
```

Puis ouvre `http://localhost:4200`. Assure-toi que le backend Flask (`python app.py`) tourne en parallèle.

## Build de production

```bash
npm run build
```

Les fichiers sont générés dans `dist/live-ai-assistant`.

## Structure

```
src/app/
├── components/
│   ├── orb/              → élément signature animé (repos / recherche / génération / vérifié)
│   ├── message-bubble/   → bulle de message + badge de confiance
│   ├── source-chip/      → vignette de source vérifiée (cliquable)
│   ├── chat-input/       → barre de saisie + suggestions
│   └── sidebar/          → branding, nouvelle conversation, statut backend
├── services/
│   └── chat.service.ts   → connexion SSE à /api/chat/stream (fetch + ReadableStream)
├── models/
│   └── message.model.ts
└── app.component.*       → orchestration de l'état de la conversation
```
