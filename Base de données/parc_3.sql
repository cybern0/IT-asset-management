-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

CREATE TABLE IF NOT EXISTS journal_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    utilisateur_id BIGINT REFERENCES utilisateur(id),
    action VARCHAR(80) NOT NULL,
    table_cible VARCHAR(100),
    identifiant_cible BIGINT,
    details JSONB,
    adresse_ip INET,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_date
ON journal_audit(cree_le DESC);