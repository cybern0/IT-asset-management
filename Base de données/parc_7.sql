-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Etat de signature de la fiche (etape 4) fixe a la main par l'administrateur : on garde qui l'a fixe et quand.
-- La signature elle-meme a lieu hors de l'application ; `statut` (NON_SIGNEE / SIGNEE) et `date_signature` existent deja.
-- Script rejouable.
ALTER TABLE fiche_detention
    ADD COLUMN IF NOT EXISTS signature_modifiee_par VARCHAR(80),
    ADD COLUMN IF NOT EXISTS signature_modifiee_le TIMESTAMPTZ;
