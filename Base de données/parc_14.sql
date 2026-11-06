-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_14.sql : un seul role, ADMIN. A executer apres parc_13.sql. Rejouable (sans effet si rien a retirer).
--
-- L'ecran « Demandes de materiel » est supprime : un utilisateur standard n'aurait plus aucun ecran. Ce script retire donc
-- le role UTILISATEUR s'il existe (cree par une version intermediaire de ce script) :
--   - ses comptes sont DESACTIVES (actif = FALSE), pour ne promouvoir personne en silence ; ils sont rattaches a ADMIN
--     (utilisateur.role_id est obligatoire) : ne les reactiver que si la personne doit vraiment etre administrateur ;
--   - le role et ses droits sont supprimes.
-- Il redefinit aussi la vue v_circuit_demande : l'ADMIN fait chaque etape (la vue n'annonce plus que ADMIN).
-- =====================================================================================================================

UPDATE utilisateur
   SET actif = FALSE,
       role_id = (SELECT id FROM role WHERE code = 'ADMIN')
 WHERE role_id IN (SELECT id FROM role WHERE code = 'UTILISATEUR');

DELETE FROM role WHERE code = 'UTILISATEUR';  -- ses lignes role_permission partent avec : ON DELETE CASCADE

CREATE OR REPLACE VIEW v_circuit_demande AS
SELECT f.id AS fiche_id,
       f.reference,
       f.type_demande,
       f.agent_id,
       ag.service_id,
       s.chef_agent_id,
       f.materiel_id,
       CASE
           WHEN f.cloture IS NOT NULL                                              THEN 'CLOTUREE'
           WHEN (f.approuve_le IS NULL AND f.valide_par IS NULL) OR f.materiel_id IS NULL THEN 'A_APPROUVER'
           WHEN f.signature_agent_le IS NULL AND f.statut <> 'SIGNEE'              THEN 'A_SIGNER_AGENT'
           WHEN f.signature_chef_le IS NULL AND f.statut <> 'SIGNEE'               THEN 'A_SIGNER_CHEF'
           WHEN f.date_remise IS NULL AND f.affectation_id IS NULL                 THEN 'A_REMETTRE'
           WHEN f.reception_approuvee_le IS NULL                                   THEN 'A_APPROUVER_RECEPTION'
           ELSE 'TERMINEE'
       END AS phase,
       CASE
           WHEN f.cloture IS NOT NULL                                              THEN NULL
           WHEN (f.approuve_le IS NULL AND f.valide_par IS NULL) OR f.materiel_id IS NULL THEN 'ADMIN'
           WHEN f.signature_agent_le IS NULL AND f.statut <> 'SIGNEE'              THEN 'ADMIN'
           WHEN f.signature_chef_le IS NULL AND f.statut <> 'SIGNEE'               THEN 'ADMIN'
           WHEN f.date_remise IS NULL AND f.affectation_id IS NULL                 THEN 'ADMIN'
           WHEN f.reception_approuvee_le IS NULL                                   THEN 'ADMIN'
           ELSE NULL
       END AS role_attendu
FROM fiche_detention f
JOIN agent ag ON ag.id = f.agent_id
LEFT JOIN service s ON s.id = ag.service_id;

-- ADMIN garde TOUS les droits
INSERT INTO role_permission(role_id, permission_id)
SELECT r.id, p.id
FROM role r CROSS JOIN permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;
