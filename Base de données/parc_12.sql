-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_12.sql : suppression d'un agent sans perdre le materiel + deux facons de recevoir un materiel.
-- A executer apres parc_11.sql. Script rejouable (sans danger si relance).
--
-- Un materiel peut etre RECU de deux facons :
--   1. ATTRIBUTION : le materiel n'a pas de detenteur (statut EN_STOCK) -> materiel neuf, ou materiel deja utilise dont
--      le detenteur a ete efface de la base. Il est donne directement a un agent.
--   2. AFFECTATION : le materiel est retire a son detenteur actuel et donne a un autre agent (transfert).
--
-- Un materiel deja utilise peut donc ne pas avoir de detenteur : quand un agent est supprime, ses affectations en cours
-- sont closes (le materiel redevient EN_STOCK, donc attribuable) et son nom reste lisible dans l'historique.
-- =====================================================================================================================

-- 1) Memoire du nom de l'agent : l'historique reste lisible apres sa suppression -------------------------------------
ALTER TABLE affectation
    ADD COLUMN IF NOT EXISTS agent_matricule VARCHAR(50),
    ADD COLUMN IF NOT EXISTS agent_nom VARCHAR(220);

ALTER TABLE fiche_detention
    ADD COLUMN IF NOT EXISTS agent_matricule VARCHAR(50),
    ADD COLUMN IF NOT EXISTS agent_nom VARCHAR(220);

-- Les affectations et dossiers existants gardent des maintenant le nom de leur agent
UPDATE affectation a SET agent_matricule = g.matricule, agent_nom = g.prenom || ' ' || g.nom
  FROM agent g WHERE g.id = a.agent_id AND a.agent_nom IS NULL;
UPDATE fiche_detention f SET agent_matricule = g.matricule, agent_nom = g.prenom || ' ' || g.nom
  FROM agent g WHERE g.id = f.agent_id AND f.agent_nom IS NULL;

-- 2) Les liens vers agent ne bloquent plus sa suppression -------------------------------------------------------------
ALTER TABLE affectation ALTER COLUMN agent_id DROP NOT NULL;
ALTER TABLE fiche_detention ALTER COLUMN agent_id DROP NOT NULL;

-- Recree la cle etrangere table.colonne -> agent(id) avec l'action voulue (quel que soit le nom d'origine de la contrainte)
CREATE OR REPLACE FUNCTION pg_temp.refaire_fk(p_table TEXT, p_colonne TEXT, p_action TEXT) RETURNS VOID AS $$
DECLARE c RECORD;
BEGIN
    FOR c IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
        WHERE con.contype = 'f' AND con.conrelid = p_table::regclass
          AND con.confrelid = 'agent'::regclass AND att.attname = p_colonne
    LOOP
        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', p_table, c.conname);
    END LOOP;
    EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES agent(id) ON DELETE %s',
                   p_table, p_table || '_' || p_colonne || '_fkey', p_colonne, p_action);
END;
$$ LANGUAGE plpgsql;

SELECT pg_temp.refaire_fk('affectation', 'agent_id', 'SET NULL');
SELECT pg_temp.refaire_fk('fiche_detention', 'agent_id', 'SET NULL');
SELECT pg_temp.refaire_fk('fiche_detention', 'ancien_agent_id', 'SET NULL');
SELECT pg_temp.refaire_fk('utilisateur', 'agent_id', 'SET NULL');          -- le compte survit, detache de l'agent
SELECT pg_temp.refaire_fk('service', 'chef_agent_id', 'SET NULL');         -- le service n'a plus de chef
SELECT pg_temp.refaire_fk('notification', 'destinataire_agent_id', 'CASCADE'); -- messages de la personne : sans objet

-- 3) Suppression d'un agent : le materiel qu'il detenait n'a plus de detenteur ----------------------------------------
CREATE OR REPLACE FUNCTION trg_agent_avant_suppression() RETURNS TRIGGER AS $$
DECLARE nom TEXT := OLD.prenom || ' ' || OLD.nom;
BEGIN
    -- dossiers ouverts qui le concernent (futur detenteur ou ancien detenteur) : annules, le materiel reserve est libere
    UPDATE fiche_detention
       SET cloture = 'ANNULEE', motif_cloture = 'Agent supprimé de la base : ' || nom
     WHERE (agent_id = OLD.id OR ancien_agent_id = OLD.id) AND affectation_id IS NULL AND cloture IS NULL;

    -- materiel qu'il detenait : redevient disponible (EN_STOCK), sans detenteur
    UPDATE materiel m SET statut = 'EN_STOCK'
      FROM affectation a
     WHERE a.agent_id = OLD.id AND a.date_retour IS NULL AND a.materiel_id = m.id AND m.statut = 'ATTRIBUE';

    -- ses affectations en cours sont closes a la date du jour, avec la raison
    UPDATE affectation
       SET date_retour = GREATEST(CURRENT_DATE, date_remise),
           observations = concat_ws(E'\n', observations, 'Détenteur supprimé de la base : ' || nom || ' (' || OLD.matricule || ')')
     WHERE agent_id = OLD.id AND date_retour IS NULL;

    -- l'historique garde son nom (la cle etrangere passe a NULL juste apres)
    UPDATE affectation SET agent_matricule = OLD.matricule, agent_nom = nom WHERE agent_id = OLD.id;
    UPDATE fiche_detention SET agent_matricule = OLD.matricule, agent_nom = nom WHERE agent_id = OLD.id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agent_avant_suppression ON agent;
CREATE TRIGGER agent_avant_suppression BEFORE DELETE ON agent
    FOR EACH ROW EXECUTE FUNCTION trg_agent_avant_suppression();

-- Les nouvelles affectations et fiches recoivent le nom de l'agent a la creation
CREATE OR REPLACE FUNCTION trg_nom_agent_memorise() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.agent_id IS NOT NULL AND NEW.agent_nom IS NULL THEN
        SELECT g.matricule, g.prenom || ' ' || g.nom INTO NEW.agent_matricule, NEW.agent_nom FROM agent g WHERE g.id = NEW.agent_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS affectation_nom_agent ON affectation;
CREATE TRIGGER affectation_nom_agent BEFORE INSERT ON affectation FOR EACH ROW EXECUTE FUNCTION trg_nom_agent_memorise();
DROP TRIGGER IF EXISTS fiche_nom_agent ON fiche_detention;
CREATE TRIGGER fiche_nom_agent BEFORE INSERT ON fiche_detention FOR EACH ROW EXECUTE FUNCTION trg_nom_agent_memorise();

-- 4) Vue : materiels sans detenteur (a attribuer), neufs ou deja utilises ---------------------------------------------
CREATE OR REPLACE VIEW v_materiels_sans_detenteur AS
SELECT m.id AS materiel_id, m.code_inventaire, m.designation, m.categorie_id,
       EXISTS (SELECT 1 FROM affectation a WHERE a.materiel_id = m.id) AS deja_utilise,
       (SELECT a.agent_nom FROM affectation a WHERE a.materiel_id = m.id ORDER BY a.date_remise DESC, a.id DESC LIMIT 1) AS dernier_detenteur
FROM v_materiels_attribuables m;

-- Historique des transferts : le nouvel agent peut avoir ete supprime depuis
DROP VIEW IF EXISTS v_transferts;
CREATE VIEW v_transferts AS
SELECT f.id AS fiche_id, f.reference, f.materiel_id, m.code_inventaire,
       f.ancien_agent_id, f.agent_id AS nouvel_agent_id, f.agent_nom AS nouvel_agent_nom, f.date_remise, f.reception_approuvee_le
FROM fiche_detention f
JOIN materiel m ON m.id = f.materiel_id
WHERE f.type_demande = 'AFFECTATION' AND f.ancienne_affectation_id IS NOT NULL;
