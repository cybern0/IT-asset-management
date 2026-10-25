-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- Logiciels et licences
-- Un logiciel peut etre sans licence (libre) : dans ce cas, aucune licence ne peut lui etre rattachee.

CREATE TABLE IF NOT EXISTS logiciel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(180) NOT NULL,
    editeur VARCHAR(150),
    version VARCHAR(60),
    type_licence VARCHAR(20) NOT NULL DEFAULT 'PERPETUELLE'
        CHECK (type_licence IN ('SANS_LICENCE','PERPETUELLE','ABONNEMENT')),
    observations TEXT,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (nom, version)
);

CREATE TABLE IF NOT EXISTS licence (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    logiciel_id BIGINT NOT NULL REFERENCES logiciel(id),
    cle_licence VARCHAR(255),
    nombre_postes INTEGER NOT NULL DEFAULT 1
        CHECK (nombre_postes > 0),
    date_expiration DATE,
    observations TEXT,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -- Refuse une licence sur un logiciel declare « sans licence »
-- CREATE OR REPLACE FUNCTION verifier_logiciel_avec_licence()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     IF (SELECT type_licence FROM logiciel WHERE id = NEW.logiciel_id) = 'SANS_LICENCE' THEN
--         RAISE EXCEPTION 'Le logiciel % est sans licence : aucune licence a enregistrer', NEW.logiciel_id;
--     END IF;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- DROP TRIGGER IF EXISTS trg_licence_logiciel ON licence;
-- CREATE TRIGGER trg_licence_logiciel
-- BEFORE INSERT OR UPDATE OF logiciel_id ON licence
-- FOR EACH ROW EXECUTE FUNCTION verifier_logiciel_avec_licence();

-- CREATE INDEX IF NOT EXISTS idx_licence_logiciel
-- ON licence(logiciel_id);

-- CREATE INDEX IF NOT EXISTS idx_licence_expiration
-- ON licence(date_expiration);