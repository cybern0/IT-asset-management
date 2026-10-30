SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Ajout des informations de contact et d'adresse pour les agents
ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS telephone VARCHAR(30),
    ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(30),
    ADD COLUMN IF NOT EXISTS adresse_domicile_exacte TEXT;

-- Ajout des informations de contact et d'adresse pour les dossiers de détention
ALTER TABLE fiche_detention
    ADD COLUMN IF NOT EXISTS telephone VARCHAR(30),
    ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(30),
    ADD COLUMN IF NOT EXISTS adresse_domicile_exacte TEXT;
