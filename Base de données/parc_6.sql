-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Circuit d'attribution simplifie : la signature, la validation et la remise sont des gestes humains faits hors de
-- l'application, qui enregistre seulement qu'ils ont eu lieu. Le scan du document signe n'est donc plus gere.
-- Script rejouable. Les fichiers deja envoyes (dossier des fiches dans UPLOAD_DIR) peuvent etre supprimes a la main.
ALTER TABLE fiche_detention DROP COLUMN IF EXISTS fichier_signe_chemin;
