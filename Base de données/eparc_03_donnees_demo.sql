-- =====================================================================================================================
-- eparc_03_donnees_demo.sql : donnees de DEMONSTRATION (fictives). Aucun utilisateur n'est cree.
-- A executer apres eparc_01_schema.sql et eparc_02_donnees_initiales.sql (categories requises).
-- Rejouable pour l'essentiel (ON CONFLICT / NOT EXISTS). Les noms, matricules et numeros sont inventes.
--
-- Section 8 : parcours de tracabilite (transferts, retours, dossier annule), visibles dans Global > Materiel.
--
-- Non inclus : utilisateur et mouvement_consommable (ce dernier exige un utilisateur : effectue_par).
-- Sans trigger, les colonnes agent_matricule / agent_nom sont renseignees ici explicitement.
-- =====================================================================================================================

-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;

-- ---------------------------------------------------------------------------------------------------------------------
-- 1. Organisation : directions, services, agents
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO direction(code, nom) VALUES
 ('DG',  'Direction Générale'),
 ('DAF', 'Direction Administrative et Financière'),
 ('DSI', 'Direction des Systèmes d''Information')
ON CONFLICT (code) DO NOTHING;

INSERT INTO service(direction_id, code, nom, site)
SELECT d.id, v.code, v.nom, v.site
FROM (VALUES
    ('DG',  'DG-SEC',  'Secrétariat de direction',     'Siège - Antananarivo'),
    ('DAF', 'DAF-CPT', 'Comptabilité et patrimoine',   'Siège - Antananarivo'),
    ('DAF', 'DAF-RH',  'Ressources humaines',          'Siège - Antananarivo'),
    ('DSI', 'DSI-INF', 'Support et infrastructure',    'Siège - Antananarivo'),
    ('DSI', 'DSI-RES', 'Réseaux et télécommunications','Siège - Antananarivo')
) AS v(dir_code, code, nom, site)
JOIN direction d ON d.code = v.dir_code
ON CONFLICT (code) DO NOTHING;

INSERT INTO agent(matricule, nom, prenom, fonction, email, service_id, telephone, whatsapp)
SELECT v.matricule, v.nom, v.prenom, v.fonction, v.email, s.id, v.tel, v.tel
FROM (VALUES
    ('M001', 'Rakoto',       'Jean',   'Technicien support',        'jean.rakoto@demo.example',        'DSI-INF', '+261340000001'),
    ('M002', 'Rasoa',        'Marie',  'Dépositaire comptable',     'marie.rasoa@demo.example',        'DAF-CPT', '+261340000002'),
    ('M003', 'Randria',      'Andry',  'Responsable RH',            'andry.randria@demo.example',      'DAF-RH',  '+261340000003'),
    ('M004', 'Rabe',         'Hery',   'Chef de secrétariat',       'hery.rabe@demo.example',          'DG-SEC',  '+261340000004'),
    ('M005', 'Razafy',       'Lalaina','Secrétaire',                'lalaina.razafy@demo.example',     'DG-SEC',  '+261340000005'),
    ('M006', 'Rakotomalala', 'Tiana',  'Ingénieur réseau',          'tiana.rakotomalala@demo.example', 'DSI-RES', '+261340000006'),
    ('M007', 'Rasolo',       'Fanja',  'Comptable',                 'fanja.rasolo@demo.example',       'DAF-CPT', '+261340000007'),
    ('M008', 'Ravelo',       'Mamy',   'Responsable infrastructure','mamy.ravelo@demo.example',        'DSI-INF', '+261340000008')
) AS v(matricule, nom, prenom, fonction, email, service_code, tel)
JOIN service s ON s.code = v.service_code
ON CONFLICT (matricule) DO NOTHING;

-- Chefs de service
UPDATE service s SET chef_agent_id = a.id
FROM (VALUES ('DG-SEC','M004'), ('DAF-CPT','M002'), ('DAF-RH','M003'), ('DSI-INF','M008'), ('DSI-RES','M006'))
     AS v(service_code, matricule)
JOIN agent a ON a.matricule = v.matricule
WHERE s.code = v.service_code AND s.chef_agent_id IS NULL;


-- ---------------------------------------------------------------------------------------------------------------------
-- 2. Materiels
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO materiel(code_inventaire, categorie_id, designation, marque, modele, numero_serie, caracteristiques,
                     provenance, provenance_detail, date_acquisition, valeur_acquisition, etat, statut, localisation)
SELECT v.code, c.id, v.designation, v.marque, v.modele, v.serie, v.caract,
       v.provenance, v.prov_detail, v.date_acq::date, v.valeur::numeric, v.etat, v.statut, v.localisation
FROM (VALUES
 ('INV-PC-001',  'ORDINATEUR', 'Ordinateur portable', 'Dell',    'Latitude 5440', 'SN-DEMO-PC-001',
    'RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1335U',
    'ACHAT', 'BL-2025-014', '2025-02-10', '3200000', 'BON', 'ATTRIBUE', 'Siège - DSI'),
 ('INV-PC-002',  'ORDINATEUR', 'Ordinateur portable', 'HP',      'ProBook 450 G10', 'SN-DEMO-PC-002',
    'RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1335U',
    'ACHAT', 'BL-2025-014', '2025-02-10', '3100000', 'BON', 'ATTRIBUE', 'Siège - Comptabilité'),
 ('INV-PC-003',  'ORDINATEUR', 'Ordinateur portable', 'Lenovo',  'ThinkPad E14', 'SN-DEMO-PC-003',
    'RAM: 8 Go, Stockage: 256 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U',
    'DOTATION', 'Dotation ministère', '2024-06-03', '2800000', 'BON', 'ATTRIBUE', 'Siège - RH'),
 ('INV-PC-004',  'ORDINATEUR', 'Ordinateur de bureau', 'Dell',   'OptiPlex 7010', 'SN-DEMO-PC-004',
    'RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-13500',
    'ACHAT', 'BL-2024-077', '2024-09-15', '2600000', 'BON', 'ATTRIBUE', 'Siège - Secrétariat'),
 ('INV-PC-005',  'ORDINATEUR', 'Ordinateur portable', 'HP',      'EliteBook 840 G10', 'SN-DEMO-PC-005',
    'RAM: 32 Go, Stockage: 1 To SSD, OS: Windows 11 Pro, CPU: Intel i7-1355U',
    'ACHAT', 'BL-2026-003', '2026-01-20', '4800000', 'NEUF', 'EN_STOCK', 'Magasin informatique'),
 ('INV-PC-006',  'ORDINATEUR', 'Ordinateur portable', 'Lenovo',  'IdeaPad 3', 'SN-DEMO-PC-006',
    'RAM: 8 Go, Stockage: 256 Go SSD, OS: Windows 10 Pro, CPU: Intel i3-1115G4',
    'DON', 'Don partenaire', '2023-04-12', '1500000', 'BON', 'EN_STOCK', 'Magasin informatique'),
 ('INV-PC-007',  'ORDINATEUR', 'Ordinateur de bureau', 'HP',     'ProDesk 400 G7', 'SN-DEMO-PC-007',
    'RAM: 8 Go, Stockage: 500 Go HDD, OS: Windows 10 Pro, CPU: Intel i5-10500',
    'ACHAT', NULL, '2021-03-08', '2100000', 'EN_PANNE', 'EN_MAINTENANCE', 'Atelier DSI'),
 ('INV-ECR-001', 'ECRAN',      'Écran 24 pouces', 'Dell',    'P2422H', 'SN-DEMO-ECR-001',
    'Diagonale: 24", Résolution: 1920x1080, Connectique: HDMI/DP/VGA',
    'ACHAT', 'BL-2025-014', '2025-02-10', '650000', 'BON', 'ATTRIBUE', 'Siège - DSI'),
 ('INV-ECR-002', 'ECRAN',      'Écran 27 pouces', 'LG',      '27UL500', 'SN-DEMO-ECR-002',
    'Diagonale: 27", Résolution: 3840x2160, Connectique: HDMI/DP',
    'ACHAT', 'BL-2026-003', '2026-01-20', '900000', 'NEUF', 'EN_STOCK', 'Magasin informatique'),
 ('INV-IMP-001', 'IMPRIMANTE', 'Imprimante laser multifonction', 'HP', 'LaserJet Pro M428', 'SN-DEMO-IMP-001',
    'Type: Laser monochrome, Fonctions: impression/copie/scan, Réseau: Ethernet',
    'ACHAT', 'BL-2024-077', '2024-09-15', '1900000', 'BON', 'ATTRIBUE', 'Siège - Secrétariat'),
 ('INV-TEL-001', 'TELEPHONE',  'Smartphone', 'Samsung', 'Galaxy A54', 'SN-DEMO-TEL-001',
    'Stockage: 128 Go, RAM: 6 Go, OS: Android 14',
    'ACHAT', NULL, '2025-05-05', '1400000', 'BON', 'ATTRIBUE', 'Siège - Réseaux'),
 ('INV-PER-001', 'PERIPHERIQUE', 'Clavier et souris sans fil', 'Logitech', 'MK270', 'SN-DEMO-PER-001',
    'Type: Combo clavier/souris, Connexion: USB récepteur 2.4 GHz',
    'ACHAT', NULL, '2025-11-02', '95000', 'NEUF', 'EN_STOCK', 'Magasin informatique'),
 ('INV-RES-001', 'RESEAU',     'Switch 24 ports', 'Cisco',   'Catalyst 1000-24T', 'SN-DEMO-RES-001',
    'Ports: 24x 1 Gbit/s, Uplink: 4x SFP, Gestion: administrable',
    'ACHAT', NULL, '2023-08-21', '3500000', 'BON', 'EN_STOCK', 'Salle serveur'),
 ('INV-RES-002', 'RESEAU',     'Routeur', 'MikroTik', 'RB4011', 'SN-DEMO-RES-002',
    'Ports: 10x Gigabit, Gestion: RouterOS',
    'PROJET', 'Projet connectivité', '2023-08-21', '1200000', 'BON', 'EN_STOCK', 'Salle serveur'),
 ('INV-BAIE-001','BAIE',       'Baie serveur 42U', 'APC',    'NetShelter SX', 'SN-DEMO-BAIE-001',
    'Hauteur: 42U, Profondeur: 1070 mm',
    'ACHAT', NULL, '2023-08-21', '4200000', 'BON', 'EN_STOCK', 'Salle serveur')
) AS v(code, cat_code, designation, marque, modele, serie, caract, provenance, prov_detail,
       date_acq, valeur, etat, statut, localisation)
JOIN categorie_materiel c ON c.code = v.cat_code
ON CONFLICT (code_inventaire) DO NOTHING;


-- ---------------------------------------------------------------------------------------------------------------------
-- 3. Affectations (7 en cours + 1 cloturee dans l'historique)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO affectation(materiel_id, agent_id, agent_matricule, agent_nom, date_remise, date_retour,
                        etat_remise, etat_retour, observations)
SELECT m.id, a.id, a.matricule, a.prenom || ' ' || a.nom,
       v.date_remise::date, v.date_retour::date, v.etat_remise, v.etat_retour, v.obs
FROM (VALUES
 ('INV-PC-001',  'M001', '2025-03-01', NULL,         'NEUF', NULL,  NULL),
 ('INV-PC-002',  'M002', '2025-03-01', NULL,         'NEUF', NULL,  NULL),
 ('INV-PC-003',  'M003', '2024-07-01', NULL,         'NEUF', NULL,  NULL),
 ('INV-PC-004',  'M004', '2024-10-01', NULL,         'NEUF', NULL,  NULL),
 ('INV-ECR-001', 'M001', '2025-03-01', NULL,         'NEUF', NULL,  NULL),
 ('INV-IMP-001', 'M005', '2024-10-01', NULL,         'NEUF', NULL,  'Imprimante partagée du secrétariat'),
 ('INV-TEL-001', 'M006', '2025-05-15', NULL,         'NEUF', NULL,  'Téléphone d''astreinte réseau'),
 ('INV-PC-006',  'M007', '2023-05-02', '2025-12-15', 'BON',  'BON', 'Restitué lors du remplacement du poste')
) AS v(code_inv, matricule, date_remise, date_retour, etat_remise, etat_retour, obs)
JOIN materiel m ON m.code_inventaire = v.code_inv
JOIN agent a ON a.matricule = v.matricule
WHERE NOT EXISTS (SELECT 1 FROM affectation x WHERE x.materiel_id = m.id AND x.date_remise = v.date_remise::date);


-- ---------------------------------------------------------------------------------------------------------------------
-- 4. Fiches de detention
--    a) une fiche terminee (regularisation) par affectation sans fiche
--    b) trois dossiers ouverts / clos pour illustrer le circuit
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO fiche_detention (affectation_id, reference, agent_id, agent_matricule, agent_nom, categorie_id, materiel_id,
        besoin, canal, demandeur, date_demande, valide_par, date_validation, approuve_le, date_generation,
        statut, date_signature, mode_signature, signe_par, signature_agent_le, signature_chef_le,
        date_remise, etat_constate, reception_approuvee_le, type_demande)
SELECT a.id,
       'FD-' || to_char(a.date_remise, 'YYYY') || '-' ||
       lpad((COALESCE(m.max_n, 0)
             + ROW_NUMBER() OVER (PARTITION BY to_char(a.date_remise, 'YYYY') ORDER BY a.date_remise, a.id))::text, 4, '0'),
       a.agent_id, a.agent_matricule, a.agent_nom, mat.categorie_id, a.materiel_id,
       'Attribution de ' || lower(mat.designation), 'FORMULAIRE', a.agent_nom,
       a.date_remise - 7, 'Marie Rasoa', a.date_remise - 5, (a.date_remise - 5)::timestamptz, a.date_remise - 3,
       'SIGNEE', a.date_remise, 'MANUSCRITE', 'Chef de service',
       a.date_remise::timestamptz, a.date_remise::timestamptz,
       a.date_remise, CASE WHEN a.etat_remise IN ('NEUF','BON','A_REPARER') THEN a.etat_remise END,
       a.date_remise::timestamptz, 'ATTRIBUTION'
FROM affectation a
JOIN materiel mat ON mat.id = a.materiel_id
LEFT JOIN LATERAL (
    SELECT MAX(substring(f.reference FROM 9)::int) AS max_n
    FROM fiche_detention f
    WHERE f.reference LIKE 'FD-' || to_char(a.date_remise, 'YYYY') || '-%'
) m ON TRUE
WHERE NOT EXISTS (SELECT 1 FROM fiche_detention f WHERE f.affectation_id = a.id);

-- b1) Demande tout juste faite : phase A_APPROUVER (aucun materiel choisi)
INSERT INTO fiche_detention (reference, agent_id, agent_matricule, agent_nom, categorie_id, besoin, canal, reference_canal,
                             demandeur, date_demande, type_demande, telephone, whatsapp)
SELECT 'FD-2026-0101', a.id, a.matricule, a.prenom || ' ' || a.nom, c.id,
       'Second écran 27" pour travail sur tableaux comptables', 'MAIL', 'Demande d''écran supplémentaire',
       a.prenom || ' ' || a.nom, CURRENT_DATE - 3, 'ATTRIBUTION', a.telephone, a.whatsapp
FROM agent a, categorie_materiel c
WHERE a.matricule = 'M007' AND c.code = 'ECRAN'
ON CONFLICT (reference) DO NOTHING;

-- b2) Demande approuvee, materiel reserve : phase A_SIGNER_AGENT
INSERT INTO fiche_detention (reference, agent_id, agent_matricule, agent_nom, categorie_id, materiel_id, besoin, canal,
                             demandeur, date_demande, valide_par, date_validation, approuve_le, date_generation,
                             type_demande, telephone, whatsapp)
SELECT 'FD-2026-0102', a.id, a.matricule, a.prenom || ' ' || a.nom, m.categorie_id, m.id,
       'Remplacement du portable (ancien modèle en fin de vie)', 'TICKET',
       a.prenom || ' ' || a.nom, CURRENT_DATE - 6, 'Marie Rasoa', CURRENT_DATE - 2,
       (CURRENT_DATE - 2)::timestamptz, CURRENT_DATE - 2, 'ATTRIBUTION', a.telephone, a.whatsapp
FROM agent a, materiel m
WHERE a.matricule = 'M008' AND m.code_inventaire = 'INV-PC-005'
ON CONFLICT (reference) DO NOTHING;

UPDATE fiche_detention SET reference_canal = 'TCK-2026-0457' WHERE reference = 'FD-2026-0102' AND reference_canal IS NULL;

-- b3) Demande refusee : phase CLOTUREE
INSERT INTO fiche_detention (reference, agent_id, agent_matricule, agent_nom, categorie_id, besoin, canal,
                             demandeur, date_demande, type_demande, cloture, motif_cloture, motif_refus, valide_par, date_validation)
SELECT 'FD-2026-0103', a.id, a.matricule, a.prenom || ' ' || a.nom, c.id,
       'Smartphone personnel professionnel', 'WHATSAPP',
       a.prenom || ' ' || a.nom, CURRENT_DATE - 20, 'ATTRIBUTION', 'REFUSEE',
       'Aucun téléphone disponible en stock', 'Aucun téléphone disponible en stock', 'Marie Rasoa', CURRENT_DATE - 18
FROM agent a, categorie_materiel c
WHERE a.matricule = 'M005' AND c.code = 'TELEPHONE'
ON CONFLICT (reference) DO NOTHING;


-- ---------------------------------------------------------------------------------------------------------------------
-- 5. Notifications (exemples, rattachees aux dossiers ouverts)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO notification(fiche_id, evenement, destinataire_agent_id, canal, adresse, sujet, message, lien, statut)
SELECT f.id, 'DEMANDE_CREEE', d.id, 'APPLICATION', NULL, NULL,
       'Nouvelle demande ' || f.reference || ' à approuver.', NULL, 'A_ENVOYER'
FROM fiche_detention f, agent d
WHERE f.reference = 'FD-2026-0101' AND d.matricule = 'M002'
  AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.fiche_id = f.id AND n.evenement = 'DEMANDE_CREEE');

INSERT INTO notification(fiche_id, evenement, destinataire_agent_id, canal, adresse, sujet, message, lien, statut)
SELECT f.id, 'SIGNATURE_AGENT_REQUISE', d.id, 'MAIL', d.email,
       'Fiche ' || f.reference || ' à signer',
       'Votre demande est approuvée : merci de signer la fiche ' || f.reference || '.',
       'mailto:' || d.email || '?subject=Fiche%20' || f.reference || '%20%C3%A0%20signer',
       'A_ENVOYER'
FROM fiche_detention f, agent d
WHERE f.reference = 'FD-2026-0102' AND d.matricule = 'M008'
  AND NOT EXISTS (SELECT 1 FROM notification n WHERE n.fiche_id = f.id AND n.evenement = 'SIGNATURE_AGENT_REQUISE');


-- ---------------------------------------------------------------------------------------------------------------------
-- 6. Consommables et stocks (sans mouvements : ils exigent un utilisateur)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO article_consommable(reference, designation, categorie, unite, seuil_alerte) VALUES
 ('CONS-TON-HP',  'Cartouche toner HP 58A noir',     'Toner',       'unite', 3),
 ('CONS-PAP-A4',  'Papier A4 80 g (ramette 500 f.)', 'Papeterie',   'ramette', 20),
 ('CONS-CAB-RJ',  'Câble réseau RJ45 cat.6 - 3 m',   'Câblage',     'unite', 10),
 ('CONS-USB-32',  'Clé USB 32 Go',                   'Stockage',    'unite', 5)
ON CONFLICT (reference) DO NOTHING;

INSERT INTO stock_consommable(article_id, service_id, quantite)
SELECT ar.id, s.id, v.quantite
FROM (VALUES
 ('CONS-TON-HP', 'DSI-INF', 6),
 ('CONS-TON-HP', 'DG-SEC',  2),
 ('CONS-PAP-A4', 'DSI-INF', 80),
 ('CONS-PAP-A4', 'DG-SEC',  35),
 ('CONS-PAP-A4', 'DAF-CPT', 18),
 ('CONS-CAB-RJ', 'DSI-RES', 25),
 ('CONS-USB-32', 'DSI-INF', 4)
) AS v(ref, service_code, quantite)
JOIN article_consommable ar ON ar.reference = v.ref
JOIN service s ON s.code = v.service_code
ON CONFLICT (article_id, service_id) DO NOTHING;


-- ---------------------------------------------------------------------------------------------------------------------
-- 7. Logiciels et licences
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO logiciel(nom, editeur, version, type_licence, observations) VALUES
 ('Windows 11 Pro',   'Microsoft', '23H2',    'PERPETUELLE', 'Licence OEM livrée avec les postes'),
 ('Microsoft 365',    'Microsoft', 'Business','ABONNEMENT',  'Abonnement annuel par utilisateur'),
 ('LibreOffice',      'The Document Foundation', '24.2', 'SANS_LICENCE', 'Logiciel libre'),
 ('Antivirus Endpoint','ESET',     '10',       'ABONNEMENT',  NULL)
ON CONFLICT (nom, version) DO NOTHING;

INSERT INTO licence(logiciel_id, cle_licence, nombre_postes, date_expiration, observations)
SELECT l.id, v.cle, v.postes, v.expiration::date, v.obs
FROM (VALUES
 ('Windows 11 Pro',    '23H2',     'DEMO-WIN-XXXXX-XXXXX-00001', 20, NULL,         'Volume OEM'),
 ('Microsoft 365',     'Business', 'DEMO-M365-TENANT-001',       25, '2027-03-31', 'Renouvellement annuel'),
 ('Antivirus Endpoint','10',       'DEMO-ESET-XXXX-0001',        50, '2026-12-15', 'Expire bientôt')
) AS v(nom, version, cle, postes, expiration, obs)
JOIN logiciel l ON l.nom = v.nom AND l.version = v.version
WHERE NOT EXISTS (SELECT 1 FROM licence x WHERE x.logiciel_id = l.id AND x.cle_licence = v.cle);


-- ---------------------------------------------------------------------------------------------------------------------
-- 8. Tracabilite : parcours complets de materiels (detenteurs successifs, transferts, retours, dossier annule)
--    A voir dans l'interface : Global > Materiel > choisir le materiel.
--      INV-PC-008 : M005 -> (transfert) M007 -> (transfert) M006 = detenteur actuel   [3 affectations, 2 transferts]
--      INV-PC-009 : M008 puis rendu en panne, en maintenance                          [retour avec etat EN_PANNE]
--      INV-PC-010 : M004 puis rendu, de nouveau en stock                              [+ dossier de demande annule]
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO materiel(code_inventaire, categorie_id, designation, marque, modele, numero_serie, caracteristiques,
                     provenance, provenance_detail, date_acquisition, valeur_acquisition, etat, statut, localisation)
SELECT v.code, c.id, v.designation, v.marque, v.modele, v.serie, v.caract,
       v.provenance, v.prov_detail, v.date_acq::date, v.valeur::numeric, v.etat, v.statut, v.localisation
FROM (VALUES
 ('INV-PC-008', 'ORDINATEUR', 'Ordinateur portable', 'Lenovo', 'ThinkPad T14', 'SN-DEMO-PC-008',
    'RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1135G7',
    'ACHAT', 'BL-2023-021', '2023-03-10', '3000000', 'BON', 'ATTRIBUE', 'Siège - Réseaux'),
 ('INV-PC-009', 'ORDINATEUR', 'Ordinateur portable', 'Dell', 'Latitude 7420', 'SN-DEMO-PC-009',
    'RAM: 16 Go, Stockage: 256 Go SSD, OS: Windows 10 Pro, CPU: Intel i5-1145G7',
    'ACHAT', 'BL-2022-088', '2022-11-15', '3300000', 'EN_PANNE', 'EN_MAINTENANCE', 'Atelier DSI'),
 ('INV-PC-010', 'ORDINATEUR', 'Ordinateur portable', 'HP', 'ProBook 440 G9', 'SN-DEMO-PC-010',
    'RAM: 8 Go, Stockage: 256 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U',
    'DOTATION', 'Dotation ministère', '2023-12-18', '2500000', 'BON', 'EN_STOCK', 'Magasin informatique')
) AS v(code, cat_code, designation, marque, modele, serie, caract, provenance, prov_detail,
       date_acq, valeur, etat, statut, localisation)
JOIN categorie_materiel c ON c.code = v.cat_code
ON CONFLICT (code_inventaire) DO NOTHING;

-- Affectations : chaque ligne = un detenteur (date_retour NULL = detenteur actuel)
INSERT INTO affectation(materiel_id, agent_id, agent_matricule, agent_nom, date_remise, date_retour,
                        etat_remise, etat_retour, observations)
SELECT m.id, a.id, a.matricule, a.prenom || ' ' || a.nom,
       v.date_remise::date, v.date_retour::date, v.etat_remise, v.etat_retour, v.obs
FROM (VALUES
 ('INV-PC-008', 'M005', '2023-04-03', '2024-05-20', 'NEUF', 'BON',      'Restitué : le poste est réaffecté à la comptabilité'),
 ('INV-PC-008', 'M007', '2024-05-20', '2025-09-10', 'BON',  'BON',      'Transfert depuis le secrétariat, retiré pour réaffectation'),
 ('INV-PC-008', 'M006', '2025-09-10', NULL,         'BON',  NULL,       'Poste repris de la comptabilité pour l''équipe réseau'),
 ('INV-PC-009', 'M008', '2023-01-09', '2026-03-12', 'NEUF', 'EN_PANNE', 'Rendu en panne : carte mère défectueuse, envoyé en maintenance'),
 ('INV-PC-010', 'M004', '2024-01-15', '2025-11-30', 'NEUF', 'BON',      'Remplacé par un poste de bureau')
) AS v(code_inv, matricule, date_remise, date_retour, etat_remise, etat_retour, obs)
JOIN materiel m ON m.code_inventaire = v.code_inv
JOIN agent a ON a.matricule = v.matricule
WHERE NOT EXISTS (SELECT 1 FROM affectation x WHERE x.materiel_id = m.id AND x.date_remise = v.date_remise::date);

-- Dossiers (fiches de detention) : attributions et transferts. Un transfert (type AFFECTATION) garde l'ancien
-- detenteur et l'ancienne affectation, ce qui alimente la vue v_transferts et « Repris de ... » dans la timeline.
INSERT INTO fiche_detention (reference, type_demande, affectation_id, agent_id, agent_matricule, agent_nom, categorie_id, materiel_id,
        besoin, canal, demandeur, date_demande, valide_par, date_validation, approuve_le, date_generation,
        statut, date_signature, mode_signature, signe_par, signature_agent_le, signature_chef_le,
        date_remise, etat_constate, reception_approuvee_le, ancien_agent_id, ancienne_affectation_id)
SELECT v.reference, v.type_demande, a.id, a.agent_id, a.agent_matricule, a.agent_nom, mat.categorie_id, mat.id,
       v.besoin, 'FORMULAIRE', a.agent_nom, a.date_remise - 7, 'Marie Rasoa', a.date_remise - 5,
       (a.date_remise - 5)::timestamptz, a.date_remise - 3,
       'SIGNEE', a.date_remise, 'MANUSCRITE', 'Chef de service',
       a.date_remise::timestamptz, a.date_remise::timestamptz,
       a.date_remise, CASE WHEN a.etat_remise IN ('NEUF','BON','A_REPARER') THEN a.etat_remise END,
       a.date_remise::timestamptz, prev.agent_id, prev.id
FROM (VALUES
 ('FD-2023-0101', 'ATTRIBUTION', 'INV-PC-008', '2023-04-03', NULL,         'Poste portable pour le secrétariat de direction'),
 ('FD-2024-0102', 'AFFECTATION', 'INV-PC-008', '2024-05-20', '2023-04-03', 'Affectation directe : matériel retiré à Lalaina Razafy'),
 ('FD-2025-0101', 'AFFECTATION', 'INV-PC-008', '2025-09-10', '2024-05-20', 'Affectation directe : matériel retiré à Fanja Rasolo'),
 ('FD-2023-0102', 'ATTRIBUTION', 'INV-PC-009', '2023-01-09', NULL,         'Portable pour la responsable infrastructure'),
 ('FD-2024-0101', 'ATTRIBUTION', 'INV-PC-010', '2024-01-15', NULL,         'Poste portable pour le chef de secrétariat')
) AS v(reference, type_demande, code_inv, date_remise, prev_remise, besoin)
JOIN materiel mat ON mat.code_inventaire = v.code_inv
JOIN affectation a ON a.materiel_id = mat.id AND a.date_remise = v.date_remise::date
LEFT JOIN affectation prev ON prev.materiel_id = mat.id AND prev.date_remise = v.prev_remise::date
ON CONFLICT (reference) DO NOTHING;

-- Dossier annule : INV-PC-010 avait ete reserve pour M001 (demande, approbation, puis annulation)
INSERT INTO fiche_detention (reference, type_demande, agent_id, agent_matricule, agent_nom, categorie_id, materiel_id,
        besoin, canal, demandeur, date_demande, valide_par, date_validation, approuve_le, date_generation,
        cloture, motif_cloture)
SELECT 'FD-2025-0102', 'ATTRIBUTION', a.id, a.matricule, a.prenom || ' ' || a.nom, m.categorie_id, m.id,
       'Poste de secours pour les interventions', 'MAIL', a.prenom || ' ' || a.nom,
       DATE '2025-12-01', 'Marie Rasoa', DATE '2025-12-05', TIMESTAMPTZ '2025-12-05 09:00+00', DATE '2025-12-05',
       'ANNULEE', 'Agent finalement équipé d''un autre poste'
FROM agent a, materiel m
WHERE a.matricule = 'M001' AND m.code_inventaire = 'INV-PC-010'
ON CONFLICT (reference) DO NOTHING;