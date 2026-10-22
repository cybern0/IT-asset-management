# nav_ui : interface du parc informatique

React Router v7 (mode framework) + Vite. Les donnees viennent de l'API `crud_api`.

## Demarrage

```bash
npm install
cp .env.example .env     # puis adapter VITE_API_URL si l'API n'est pas sur localhost:8000
npm run dev              # http://localhost:5173
```

Sous PowerShell : `Copy-Item .env.example .env`.

L'API doit tourner (voir `../crud_api/README.md`). Si elle est injoignable, un bandeau
« Certaines données n’ont pas pu être chargées » apparait avec un bouton Réessayer.

## Organisation

| Fichier | Role |
|---|---|
| `app/lib/env.ts` | lit `VITE_API_URL` |
| `app/lib/api.ts` | client HTTP (erreurs, delai, jeton Bearer optionnel) |
| `app/lib/mapping.ts` | formulaire (chaines) <-> JSON de l'API (types natifs) |
| `app/lib/store.tsx` | charge les tables depuis l'API, enregistre, supprime, recharge les effets de bord |
| `app/lib/schema.ts` | description des ecrans, calquee sur `parc.sql` ; `tableEndpoint` relie chaque table a sa route |
| `app/lib/dict.ts` | traductions FR / EN / MG |

Rubriques sans API pour l'instant (donnees en memoire) : Rules, Forms, Notification queue, Inventory.
Journal d'audit : lecture seule. Mouvements de stock : creation seulement.
