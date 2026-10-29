-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Menu dynamique : chaque categorie de materiel declare, via `category_menu`, le menu de l'interface
-- sous lequel son onglet apparait (Materiel, Reseau, Consommables et stocks, Logiciels).
-- Creer une categorie suffit : son onglet est genere automatiquement dans le bon menu.
-- Script rejouable.

-- L'ancien champ booleen est remplace par `category_menu`
ALTER TABLE categorie_materiel DROP COLUMN IF EXISTS afficher_menu;

ALTER TABLE categorie_materiel
    ADD COLUMN IF NOT EXISTS category_menu VARCHAR(30) NOT NULL DEFAULT 'Matériel';

ALTER TABLE categorie_materiel DROP CONSTRAINT IF EXISTS ck_categorie_materiel_category_menu;
ALTER TABLE categorie_materiel
    ADD CONSTRAINT ck_categorie_materiel_category_menu
    CHECK (category_menu IN ('Matériel', 'Réseau', 'Consommables et stocks', 'Logiciels'));

-- Reprise de l'existant : les categories reseau etaient deja regroupees dans le menu « Réseau et baies ».
-- (ne touche que les lignes encore a la valeur par defaut)
UPDATE categorie_materiel
   SET category_menu = 'Réseau'
 WHERE code IN ('RESEAU', 'BAIE', 'CHASSIS', 'PDU', 'PASSIF', 'CABLE', 'SIM')
   AND category_menu = 'Matériel';
