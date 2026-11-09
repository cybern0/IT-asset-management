-- =====================================================================================================================
-- eparc_02_donnees_initiales.sql : INSERTION des donnees predefinies (etat final apres parc_4 ... parc_14)
-- A executer apres eparc_01_schema.sql. Script rejouable (sans danger si relance).
--   - role : ADMIN uniquement
--   - permissions : toutes les permissions de l'application, toutes accordees a ADMIN
--   - categories de materiel, avec le menu de l'interface sous lequel elles apparaissent
-- Aucun utilisateur n'est cree ici.
-- =====================================================================================================================

-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- 1) Role --------------------------------------------------------------------------------------------------------
INSERT INTO role(code, libelle) VALUES
 ('ADMIN', 'Administrateur')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- 2) Permissions -------------------------------------------------------------------------------------------------
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
 ('affectation.transferer',    'Retirer un matériel à son détenteur et l''affecter à un autre agent')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- 3) ADMIN a toutes les permissions ----------------------------------------------------------------------------
INSERT INTO role_permission(role_id, permission_id)
SELECT r.id, p.id
FROM role r CROSS JOIN permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- 4) Categories de materiel ------------------------------------------------------------------------------------
-- category_menu : 'Matériel', 'Réseau', 'Consommables et stocks' ou 'Logiciels'
INSERT INTO categorie_materiel(code, libelle, category_menu) VALUES
 ('ORDINATEUR',   'Ordinateur',          'Matériel'),
 ('ECRAN',        'Écran',               'Matériel'),
 ('PERIPHERIQUE', 'Périphérique',        'Matériel'),
 ('TELEPHONE',    'Téléphone',           'Matériel'),
 ('IMPRIMANTE',   'Imprimante',          'Matériel'),
 ('NON_GERE',     'Équipement non géré', 'Matériel'),
 ('RESEAU',       'Équipement réseau',   'Réseau'),
 ('BAIE',         'Baie',                'Réseau'),
 ('CHASSIS',      'Châssis',             'Réseau'),
 ('PDU',          'PDU',                 'Réseau'),
 ('PASSIF',       'Équipement passif',   'Réseau'),
 ('CABLE',        'Câble',               'Réseau'),
 ('SIM',          'Carte SIM',           'Réseau')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle, category_menu = EXCLUDED.category_menu;
