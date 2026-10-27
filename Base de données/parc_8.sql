-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Menu dynamique : une categorie de materiel n'apparait dans le menu (onglets de l'interface) que si
-- `afficher_menu` vaut TRUE. Les onglets de l'interface forment le « dictionnaire » de routes possibles ;
-- la base decide lesquels sont affiches. Par defaut, toutes les categories existantes restent visibles.
-- Script rejouable.
ALTER TABLE categorie_materiel
    ADD COLUMN IF NOT EXISTS afficher_menu BOOLEAN NOT NULL DEFAULT TRUE;

-- Exemple : masquer les cartes SIM du menu, puis les remettre
-- UPDATE categorie_materiel SET afficher_menu = FALSE WHERE code = 'SIM';
-- UPDATE categorie_materiel SET afficher_menu = TRUE  WHERE code = 'SIM';
