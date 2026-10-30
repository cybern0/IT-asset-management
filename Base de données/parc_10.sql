-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- =====================================================================================================================
-- parc_10.sql : roles modulaires (RBAC), nouveau circuit de demande et communication a distance sans serveur.
-- A executer apres parc_1.sql ... parc_9.sql. Script rejouable (sans danger si relance).
--
-- 1. Roles de parc_4.sql mis a jour : les CODES ne changent pas (ADMIN, GESTIONNAIRE, LECTURE), donc les comptes
--    existants et le code actuel continuent de fonctionner ; seuls les libelles et les droits changent.
--      ADMIN        = Depositaire comptable (Mme Jacky) : approuve les demandes et modifie la base
--      GESTIONNAIRE = Gestionnaire d'activite (chef de service) : approuve la reception des materiels, rien d'autre
--      LECTURE      = Agent, utilisateur standard : voit la repartition du materiel ; fait ses demandes et signe les siennes
-- 2. Droits stockes en base (permission / role_permission) : changer qui fait quoi = modifier ces lignes, pas le code.
-- 3. Circuit : agent demande -> Mme Jacky approuve et met a jour la base -> signature de l'agent puis du chef de
--    service -> remise -> le chef de service approuve la reception.
-- 4. Communication sans serveur : table `notification` (boite d'envoi). Le backend y range un lien pret a l'emploi
--    (mailto:, sms:, https://wa.me/) que l'appareil de l'utilisateur ouvre : aucun serveur SMTP ni passerelle SMS.
-- 5. Vues pour le sous-onglet « Repartition » du tableau de bord (diagramme par services, nombres par categorie).
-- =====================================================================================================================


-- ---------------------------------------------------------------------------------------------------------------------
-- 1. Roles : mise a jour des lignes inserees par parc_4.sql
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO role(code, libelle) VALUES
 ('ADMIN',        'Dépositaire comptable (administrateur)'),
 ('GESTIONNAIRE', 'Gestionnaire d''activité - approbation de la réception'),
 ('LECTURE',      'Agent - utilisateur standard')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;


-- ---------------------------------------------------------------------------------------------------------------------
-- 2. Permissions (RBAC modulaire) : table `permission` + liaison `role_permission` (creees par parc_1.sql)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO permission(code, libelle) VALUES
 ('dashboard.voir',            'Voir le tableau de bord'),
 ('dashboard.repartition',     'Voir la répartition du matériel par service (tableau de bord)'),
 ('parc.lire',                 'Consulter le matériel, les agents et les stocks'),
 ('parc.ecrire',               'Créer et modifier les données du parc (base de données)'),
 ('parc.supprimer',            'Supprimer des données du parc'),
 ('demande.creer',             'Faire une demande de matériel (attribution ou affectation)'),
 ('demande.voir_propres',      'Voir ses propres demandes'),
 ('demande.voir_service',      'Voir les demandes des agents de son service'),
 ('demande.voir_toutes',       'Voir toutes les demandes'),
 ('demande.approuver',         'Approuver ou refuser une demande et mettre à jour la base'),
 ('fiche.signer_agent',        'Signer la fiche en tant qu''agent demandeur'),
 ('fiche.signer_chef',         'Signer la fiche en tant que chef de service'),
 ('fiche.remettre',            'Enregistrer la remise physique du matériel'),
 ('reception.approuver',       'Approuver la réception du matériel'),
 ('notification.envoyer',      'Envoyer les notifications (mail, SMS, WhatsApp)'),
 ('acces.gerer',               'Gérer les comptes, les rôles et les droits'),
 ('audit.lire',                'Consulter le journal d''audit')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- On repart d'une base propre pour ces trois roles : le script redonne toujours le meme resultat.
-- (Les roles crees par l'administrateur dans l'interface ne sont pas touches.)
DELETE FROM role_permission
 WHERE role_id IN (SELECT id FROM role WHERE code IN ('ADMIN', 'GESTIONNAIRE', 'LECTURE'));

INSERT INTO role_permission(role_id, permission_id)
SELECT r.id, p.id
FROM (VALUES
    -- Depositaire comptable : tout
    ('ADMIN', 'dashboard.voir'), ('ADMIN', 'dashboard.repartition'),
    ('ADMIN', 'parc.lire'), ('ADMIN', 'parc.ecrire'), ('ADMIN', 'parc.supprimer'),
    ('ADMIN', 'demande.creer'), ('ADMIN', 'demande.voir_toutes'), ('ADMIN', 'demande.approuver'),
    ('ADMIN', 'fiche.remettre'), ('ADMIN', 'notification.envoyer'),
    ('ADMIN', 'acces.gerer'), ('ADMIN', 'audit.lire'),
    -- Gestionnaire d'activite (chef de service) : signe la fiche et approuve la reception, rien d'autre
    ('GESTIONNAIRE', 'dashboard.repartition'),
    ('GESTIONNAIRE', 'demande.voir_service'),
    ('GESTIONNAIRE', 'fiche.signer_chef'),
    ('GESTIONNAIRE', 'reception.approuver'),
    -- Agent : voit la repartition ; demande et signe pour lui-meme (aucune ecriture sur le parc)
    ('LECTURE', 'dashboard.repartition'),
    ('LECTURE', 'demande.creer'), ('LECTURE', 'demande.voir_propres'),
    ('LECTURE', 'fiche.signer_agent')
) AS v(role_code, perm_code)
JOIN role r ON r.code = v.role_code
JOIN permission p ON p.code = v.perm_code
ON CONFLICT DO NOTHING;


-- ---------------------------------------------------------------------------------------------------------------------
-- 3. Circuit de demande : chef de service, type de demande, approbation, double signature, approbation de reception
-- ---------------------------------------------------------------------------------------------------------------------

-- Le chef de service est un agent : son compte (utilisateur.agent_id) signe et approuve la reception pour ce service.
ALTER TABLE service
    ADD COLUMN IF NOT EXISTS chef_agent_id BIGINT REFERENCES agent(id);

CREATE INDEX IF NOT EXISTS idx_service_chef ON service(chef_agent_id);

ALTER TABLE fiche_detention
    -- etape 1 : l'agent demande une attribution ou une affectation
    ADD COLUMN IF NOT EXISTS type_demande VARCHAR(12) NOT NULL DEFAULT 'ATTRIBUTION',
    ADD COLUMN IF NOT EXISTS demande_par BIGINT REFERENCES utilisateur(id),
    -- etape 2 : Mme Jacky (depositaire comptable) approuve, choisit le materiel et met la base a jour
    ADD COLUMN IF NOT EXISTS approuve_par BIGINT REFERENCES utilisateur(id),
    ADD COLUMN IF NOT EXISTS approuve_le TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS motif_refus TEXT,
    -- etape 3 : signature de l'agent demandeur, puis du chef de son service
    ADD COLUMN IF NOT EXISTS signature_agent_par BIGINT REFERENCES utilisateur(id),
    ADD COLUMN IF NOT EXISTS signature_agent_le TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS signature_chef_par BIGINT REFERENCES utilisateur(id),
    ADD COLUMN IF NOT EXISTS signature_chef_le TIMESTAMPTZ,
    -- apres la remise : le chef de service approuve la reception dans l'application
    ADD COLUMN IF NOT EXISTS reception_approuvee_par BIGINT REFERENCES utilisateur(id),
    ADD COLUMN IF NOT EXISTS reception_approuvee_le TIMESTAMPTZ;

ALTER TABLE fiche_detention DROP CONSTRAINT IF EXISTS ck_fiche_type_demande;
ALTER TABLE fiche_detention
    ADD CONSTRAINT ck_fiche_type_demande CHECK (type_demande IN ('ATTRIBUTION', 'AFFECTATION'));

-- Canal d'arrivee de la demande : on ajoute SMS et WhatsApp (contrainte creee par parc_5.sql, remplacee ici)
ALTER TABLE fiche_detention DROP CONSTRAINT IF EXISTS fiche_detention_canal_check;
ALTER TABLE fiche_detention DROP CONSTRAINT IF EXISTS ck_fiche_canal;
ALTER TABLE fiche_detention
    ADD CONSTRAINT ck_fiche_canal CHECK (canal IN ('MAIL', 'TICKET', 'FORMULAIRE', 'SMS', 'WHATSAPP'));

-- Dossiers deja existants (avant parc_10) : on reprend les gestes deja faits, sans rien inventer
UPDATE fiche_detention
   SET approuve_le = date_validation::timestamptz
 WHERE approuve_le IS NULL AND date_validation IS NOT NULL;

UPDATE fiche_detention
   SET signature_agent_le = date_signature::timestamptz,
       signature_chef_le  = date_signature::timestamptz
 WHERE statut = 'SIGNEE' AND date_signature IS NOT NULL
   AND signature_agent_le IS NULL AND signature_chef_le IS NULL;

UPDATE fiche_detention
   SET reception_approuvee_le = date_remise::timestamptz
 WHERE reception_approuvee_le IS NULL AND date_remise IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fiche_approuve ON fiche_detention(approuve_le);

-- Phase du dossier, deduite des donnees (comme `etape_of` cote API) : jamais stockee, donc jamais desynchronisee.
-- La phase indique AUSSI qui doit agir : c'est ce que le backend utilise pour notifier la bonne personne.
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
           WHEN f.signature_agent_le IS NULL AND f.statut <> 'SIGNEE'              THEN 'LECTURE'
           WHEN f.signature_chef_le IS NULL AND f.statut <> 'SIGNEE'               THEN 'GESTIONNAIRE'
           WHEN f.date_remise IS NULL AND f.affectation_id IS NULL                 THEN 'ADMIN'
           WHEN f.reception_approuvee_le IS NULL                                   THEN 'GESTIONNAIRE'
           ELSE NULL
       END AS role_attendu
FROM fiche_detention f
JOIN agent ag ON ag.id = f.agent_id
LEFT JOIN service s ON s.id = ag.service_id;


-- ---------------------------------------------------------------------------------------------------------------------
-- 4. Communication a distance sans serveur : boite d'envoi des notifications
--    Le backend ecrit ici ; `lien` est un lien pret a ouvrir sur l'appareil de la personne :
--      MAIL      mailto:adresse?subject=...&body=...
--      SMS       sms:+261340000000?body=...
--      WHATSAPP  https://wa.me/261340000000?text=...
--      APPLICATION  (pas de lien) message affiche dans l'application
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fiche_id BIGINT REFERENCES fiche_detention(id) ON DELETE CASCADE,
    evenement VARCHAR(30) NOT NULL
        CHECK (evenement IN ('DEMANDE_CREEE', 'DEMANDE_APPROUVEE', 'DEMANDE_REFUSEE',
                             'SIGNATURE_AGENT_REQUISE', 'SIGNATURE_CHEF_REQUISE',
                             'MATERIEL_REMIS', 'RECEPTION_A_APPROUVER', 'DOSSIER_TERMINE')),
    destinataire_agent_id BIGINT NOT NULL REFERENCES agent(id),
    destinataire_utilisateur_id BIGINT REFERENCES utilisateur(id),
    canal VARCHAR(12) NOT NULL
        CHECK (canal IN ('APPLICATION', 'MAIL', 'SMS', 'WHATSAPP')),
    adresse VARCHAR(180),                       -- email ou numero utilise (copie de l'agent au moment de l'envoi)
    sujet VARCHAR(180),
    message TEXT NOT NULL,
    lien TEXT,                                  -- mailto: / sms: / wa.me ; vide pour APPLICATION
    statut VARCHAR(10) NOT NULL DEFAULT 'A_ENVOYER'
        CHECK (statut IN ('A_ENVOYER', 'ENVOYEE', 'LUE')),
    cree_par BIGINT REFERENCES utilisateur(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    envoye_le TIMESTAMPTZ,
    lu_le TIMESTAMPTZ,
    CHECK (canal = 'APPLICATION' OR lien IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_notification_destinataire
    ON notification(destinataire_agent_id, statut, cree_le DESC);
CREATE INDEX IF NOT EXISTS idx_notification_fiche ON notification(fiche_id);


-- ---------------------------------------------------------------------------------------------------------------------
-- 5. Tableau de bord > Repartition : diagramme par services, nombres par categorie
--    Compte uniquement le materiel actuellement detenu (affectation sans date de retour).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_repartition_service_categorie AS
WITH detenus AS (
    SELECT ag.service_id, m.categorie_id, m.id AS materiel_id, ag.id AS agent_id
    FROM affectation af
    JOIN agent ag ON ag.id = af.agent_id
    JOIN materiel m ON m.id = af.materiel_id
    WHERE af.date_retour IS NULL
)
SELECT s.id   AS service_id,
       s.code AS service_code,
       s.nom  AS service_nom,
       c.id   AS categorie_id,
       c.code AS categorie_code,
       c.libelle AS categorie_libelle,
       c.category_menu,
       COUNT(d.materiel_id)          AS nb_materiels,
       COUNT(DISTINCT d.agent_id)    AS nb_agents
FROM service s
CROSS JOIN categorie_materiel c
LEFT JOIN detenus d ON d.service_id = s.id AND d.categorie_id = c.id
WHERE s.actif
GROUP BY s.id, s.code, s.nom, c.id, c.code, c.libelle, c.category_menu;

-- Une ligne par service : total du diagramme
CREATE OR REPLACE VIEW v_repartition_service AS
SELECT s.id   AS service_id,
       s.code AS service_code,
       s.nom  AS service_nom,
       (SELECT COUNT(*) FROM agent a WHERE a.service_id = s.id AND a.actif) AS nb_agents,
       COALESCE(SUM(r.nb_materiels), 0)::bigint AS nb_materiels,
       (SELECT COUNT(DISTINCT af.agent_id)
          FROM affectation af JOIN agent a ON a.id = af.agent_id
         WHERE a.service_id = s.id AND af.date_retour IS NULL) AS nb_agents_detenteurs
FROM service s
LEFT JOIN v_repartition_service_categorie r ON r.service_id = s.id
WHERE s.actif
GROUP BY s.id, s.code, s.nom;

-- Droits de chaque role, lisibles d'un coup d'oeil (le frontend et l'API peuvent s'en servir directement)
CREATE OR REPLACE VIEW v_role_permissions AS
SELECT r.code AS role_code, r.libelle AS role_libelle, p.code AS permission_code, p.libelle AS permission_libelle
FROM role r
JOIN role_permission rp ON rp.role_id = r.id
JOIN permission p ON p.id = rp.permission_id;
