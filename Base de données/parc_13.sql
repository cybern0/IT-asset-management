-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_13.sql : suppression des roles GESTIONNAIRE et LECTURE (et de tout autre role cree dans l'interface).
-- Ne reste que ADMIN. (Le role UTILISATEUR, s'il a ete cree par une version intermediaire de parc_14.sql, est retire
-- par parc_14.sql : lancer parc_14.sql juste apres ce script.)
-- A executer apres parc_12.sql. Script rejouable (sans danger si relance).
-- Si parc_4.sql ou parc_10.sql est relance par erreur, GESTIONNAIRE et LECTURE reapparaissent : relancer alors parc_13.sql.
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

-- 3) Les comptes des roles supprimes passent au role ADMIN (UTILISATEUR, lui, est conserve) --------------------------
UPDATE utilisateur
   SET role_id = (SELECT id FROM role WHERE code = 'ADMIN')
 WHERE role_id IN (SELECT id FROM role WHERE code NOT IN ('ADMIN', 'UTILISATEUR'));

-- 4) Suppression des autres roles (leurs lignes role_permission partent avec : ON DELETE CASCADE) --------------------
DELETE FROM role WHERE code NOT IN ('ADMIN', 'UTILISATEUR');
