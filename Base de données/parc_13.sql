-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_13.sql : un seul role, ADMIN. Les roles GESTIONNAIRE et LECTURE (et tout autre role cree dans l'interface)
-- sont supprimes ; tous les comptes deviennent ADMIN.
-- A executer apres parc_12.sql. Script rejouable (sans danger si relance).
-- Si parc_4.sql ou parc_10.sql est relance par erreur, les roles GESTIONNAIRE et LECTURE reapparaissent : relancer alors parc_13.sql.
--
-- Consequences sur le circuit de demande (parc_10.sql) : les cinq etapes restent les memes, mais ADMIN a TOUS les droits
-- (dont signer pour l'agent, signer pour le chef de service et approuver la reception) : un administrateur peut donc
-- faire chaque etape. Chaque signature reste tracee (utilisateur + date) dans fiche_detention.
--
-- ATTENTION : les comptes qui avaient le role GESTIONNAIRE ou LECTURE deviennent ADMIN (ils gagnent donc tous les droits).
-- Pour desactiver certains comptes plutot que les promouvoir, executer AVANT ce script :
--     UPDATE utilisateur SET actif = FALSE WHERE id IN (...);
-- =====================================================================================================================

-- 1) Le role ADMIN existe et porte un libelle simple ----------------------------------------------------------------
INSERT INTO role(code, libelle) VALUES ('ADMIN', 'Administrateur')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- 2) ADMIN a toutes les permissions (celles de GESTIONNAIRE et LECTURE comprises) ------------------------------------
INSERT INTO role_permission(role_id, permission_id)
SELECT r.id, p.id
FROM role r CROSS JOIN permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- 3) Tous les comptes passent au role ADMIN ---------------------------------------------------------------------------
UPDATE utilisateur
   SET role_id = (SELECT id FROM role WHERE code = 'ADMIN')
 WHERE role_id <> (SELECT id FROM role WHERE code = 'ADMIN');

-- 4) Suppression des autres roles (leurs lignes role_permission partent avec : ON DELETE CASCADE) --------------------
DELETE FROM role WHERE code <> 'ADMIN';

-- 5) La vue du circuit ne parle plus que de ADMIN : c'est lui qui fait toutes les etapes -------------------------------
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
