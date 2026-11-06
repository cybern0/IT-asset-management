-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_11.sql : definition precise de l'ATTRIBUTION et de l'AFFECTATION. A executer apres parc_10.sql. Rejouable.
--
--   ATTRIBUTION = on donne a un agent un materiel NON AFFECTE (statut EN_STOCK).
--   AFFECTATION = l'administrateur (depositaire comptable) RETIRE un materiel a son detenteur actuel et l'AFFECTE a un
--                 autre agent : l'ancienne affectation est cloturee et la nouvelle ouverte dans la meme operation.
-- =====================================================================================================================

-- Memoire du transfert : de qui le materiel a ete retire, et quelle affectation a ete cloturee
ALTER TABLE fiche_detention
    ADD COLUMN IF NOT EXISTS ancien_agent_id BIGINT REFERENCES agent(id),
    ADD COLUMN IF NOT EXISTS ancienne_affectation_id BIGINT REFERENCES affectation(id);

ALTER TABLE fiche_detention DROP CONSTRAINT IF EXISTS ck_fiche_transfert;
ALTER TABLE fiche_detention
    ADD CONSTRAINT ck_fiche_transfert CHECK (
        (ancien_agent_id IS NULL AND ancienne_affectation_id IS NULL) OR type_demande = 'AFFECTATION'
    );

CREATE INDEX IF NOT EXISTS idx_fiche_ancien_agent ON fiche_detention(ancien_agent_id);

-- Les demandes « affectation » en cours de l'ancienne definition (materiel deja choisi en stock) sont des attributions
UPDATE fiche_detention
   SET type_demande = 'ATTRIBUTION'
 WHERE type_demande = 'AFFECTATION' AND materiel_id IS NOT NULL AND ancienne_affectation_id IS NULL
   AND affectation_id IS NULL AND cloture IS NULL;

-- Droit de retirer un materiel a son detenteur pour l'affecter a un autre (reserve au depositaire comptable)
INSERT INTO permission(code, libelle) VALUES
 ('affectation.transferer', 'Retirer un matériel à son détenteur et l''affecter à un autre agent')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

INSERT INTO role_permission(role_id, permission_id)
SELECT r.id, p.id FROM role r, permission p
WHERE r.code = 'ADMIN' AND p.code = 'affectation.transferer'
ON CONFLICT DO NOTHING;

-- Nouveau message : l'ancien detenteur est prevenu que le materiel lui est retire
ALTER TABLE notification DROP CONSTRAINT IF EXISTS notification_evenement_check;
ALTER TABLE notification DROP CONSTRAINT IF EXISTS ck_notification_evenement;
ALTER TABLE notification
    ADD CONSTRAINT ck_notification_evenement CHECK (evenement IN (
        'DEMANDE_CREEE', 'DEMANDE_APPROUVEE', 'DEMANDE_REFUSEE', 'SIGNATURE_AGENT_REQUISE',
        'SIGNATURE_CHEF_REQUISE', 'MATERIEL_REMIS', 'RECEPTION_A_APPROUVER', 'DOSSIER_TERMINE', 'MATERIEL_RETIRE'));

-- Materiels qu'une ATTRIBUTION peut donner : en stock et non reserves par un dossier ouvert
CREATE OR REPLACE VIEW v_materiels_attribuables AS
SELECT m.*
FROM materiel m
WHERE m.statut = 'EN_STOCK'
  AND NOT EXISTS (SELECT 1 FROM fiche_detention f
                  WHERE f.materiel_id = m.id AND f.affectation_id IS NULL AND f.cloture IS NULL);

-- Materiels qu'une AFFECTATION peut reprendre : actuellement detenus, avec leur detenteur
CREATE OR REPLACE VIEW v_materiels_affectables AS
SELECT m.id AS materiel_id, m.code_inventaire, m.designation, m.categorie_id,
       af.id AS affectation_id, af.agent_id AS detenteur_id,
       ag.matricule AS detenteur_matricule, ag.nom AS detenteur_nom, ag.prenom AS detenteur_prenom,
       ag.service_id AS detenteur_service_id, af.date_remise
FROM materiel m
JOIN affectation af ON af.materiel_id = m.id AND af.date_retour IS NULL
JOIN agent ag ON ag.id = af.agent_id
WHERE m.statut = 'ATTRIBUE'
  AND NOT EXISTS (SELECT 1 FROM fiche_detention f
                  WHERE f.materiel_id = m.id AND f.affectation_id IS NULL AND f.cloture IS NULL);

-- Historique des transferts : de qui, vers qui
-- (DROP puis CREATE : parc_12.sql ajoute une colonne a cette vue, et CREATE OR REPLACE ne sait pas en retirer une au rejeu)
DROP VIEW IF EXISTS v_transferts;
CREATE VIEW v_transferts AS
SELECT f.id AS fiche_id, f.reference, f.materiel_id, m.code_inventaire,
       f.ancien_agent_id, f.agent_id AS nouvel_agent_id, f.date_remise, f.reception_approuvee_le
FROM fiche_detention f
JOIN materiel m ON m.id = f.materiel_id
WHERE f.type_demande = 'AFFECTATION' AND f.ancienne_affectation_id IS NOT NULL;
