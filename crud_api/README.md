# crud_api : API du parc informatique

FastAPI + SQLAlchemy (async) + PostgreSQL.

```
Requete -> routers/ (main.py les assemble) -> schemas/ (validation Pydantic)
        -> services/ (regles metier) -> models/ (SQLAlchemy) -> PostgreSQL
```

## Demarrage

1. Creer la base puis executer les scripts, dans l'ordre :
   `Base de données/parc.sql`, `parc_2.sql`, `parc_3.sql`, `parc_4.sql`
   (`parc_4.sql` ajoute les 13 categories de materiel attendues par l'interface).
2. Configurer :
   ```bash
   cp .env.example .env      # PowerShell : Copy-Item .env.example .env
   ```
   puis renseigner `DATABASE_URL`.
3. Lancer :
   ```bash
   uv sync
   uv run crud-api           # http://127.0.0.1:8000  (documentation : /docs)
   ```

## Regles metier (dossier `services/`)

- **Utilisateurs** : mot de passe hache (argon2), jamais renvoye ; il reste toujours un administrateur actif.
- **Materiel** : le statut « Attribue » ne s'obtient que par une affectation.
- **Affectations** : un materiel disponible (En stock) a la fois ; le retour remet le materiel en stock, ou en maintenance / reforme selon son etat ; une affectation rendue ne se rouvre pas.
- **Mouvements de stock** : mettent a jour `stock_consommable` (service vide = stock central), refusent un stock negatif, sont immuables.
- **Licences** : refusees sur un logiciel « sans licence ».
- **Journal d'audit** : ecrit automatiquement (creation, modification, suppression, connexion), lecture seule.

Erreurs : `{"detail": "message", "field": "nom_du_champ"}` (409 conflit, 422 regle ou donnee refusee) ;
les erreurs de validation Pydantic gardent le format FastAPI standard.

## Authentification

Desactivee par defaut (`AUTH_ENABLED=false`). Pour l'activer : definir `JWT_SECRET`, `AUTH_ENABLED=true`
et, au premier demarrage, `BOOTSTRAP_ADMIN_PASSWORD` pour creer le compte `admin`.
`POST /api/v1/auth/login` renvoie un jeton a envoyer en `Authorization: Bearer ...`.
Les permissions des roles ne sont pas encore appliquees route par route.

## Tests

Necessitent une base PostgreSQL vide dediee (le schema `eparc` y est supprime puis recree) :

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/parc_test
uv run pytest
```

## Images du matériel et dossiers d'attribution

Exécuter `Base de données/parc_5.sql` (colonne `materiel.image_chemin`, table `fiche_detention`, fiches des affectations existantes) puis `parc_6.sql` (retire le scan, plus géré) et `parc_7.sql` (état de signature fixé à la main), puis `uv sync` (ajoute `reportlab`, `openpyxl` et `python-multipart`).

- Les fichiers envoyés (images du matériel) sont dans `UPLOAD_DIR` (défaut `uploads/`) ; `STRUCTURE_NAME` est imprimé sur les fiches PDF.
- `POST/GET/DELETE /materiels/{id}/image` : image du matériel (JPEG, PNG, WebP, 5 Mo).
- **Dossier d'attribution = fiche de détention `FD-AAAA-NNNN`**, suivant les 6 étapes du processus. La validation du manager, la signature et la remise sont des gestes humains faits hors de l'application : elle se contente d'enregistrer qu'ils ont eu lieu (pas de scan, pas de contrôle de dates entre étapes). Trois actions suffisent :
  - `POST /attributions` crée la demande (étape 1) ; `GET /attributions`, `GET /attributions/{id}`, `GET /attributions/{id}/pdf` (fiche, dès qu'un équipement est choisi).
  - `POST /attributions/{id}/avancer` : l'étape en cours est faite → étape suivante. Corps facultatif selon l'étape : `valide_par` (1), `materiel_id` (2, la fiche est alors générée), `mode_signature` / `signe_par` (4), `etat_constate` / `accessoires` / `observations` (5 : l'affectation est créée et le matériel passe à « Attribué »). `date` (aujourd'hui par défaut) pour les étapes 1, 4 et 5.
  - `POST /attributions/{id}/signature` : l'administrateur fixe à la main l'état de la fiche (`{"signee": true|false, "date", "mode_signature", "signe_par"}`), dès que l'équipement est choisi et à tout moment ensuite. La date et le compte qui l'ont fixé sont conservés (`signature_modifiee_*`, `parc_7.sql`). Réservé au rôle ADMIN quand `AUTH_ENABLED=true`.
  - `POST /attributions/{id}/reculer` : défait la dernière étape faite (impossible une fois le matériel attribué : utiliser le retour dans Affectations).
  - `POST /attributions/{id}/clore` : refuse la demande (avant validation) ou annule le dossier (après).
- Créer une affectation directement crée un dossier de régularisation (`GET /affectations/{id}/attribution`).
- Une affectation dont la fiche est signée ne peut pas être supprimée (conservation 5 ans).

## Encodage (accents)

Les scripts SQL sont en UTF-8 et commencent par `SET client_encoding TO 'UTF8'`. Pour les exécuter sous Windows, utilisez `Base de données\charger.ps1 -Db <base>` (Linux : `./charger.sh <base>`) ; sinon faites `chcp 65001` et `$env:PGCLIENTENCODING = "UTF8"` avant `psql`. La base doit être créée en UTF8 : `CREATE DATABASE parc ENCODING 'UTF8' TEMPLATE template0;` (l'API journalise une erreur au démarrage si ce n'est pas le cas). L'API elle-même (asyncpg) échange toujours en UTF-8.
