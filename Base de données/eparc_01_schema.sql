-- =====================================================================================================================
-- eparc_01_schema.sql : CREATION de la base eparc (etat final, equivalent de parc_1.sql ... parc_14.sql)
-- Contenu : tables, contraintes, index, vues. AUCUN trigger, AUCUNE donnee.
-- Ordre d'execution : 1) eparc_01_schema.sql  2) eparc_02_donnees_initiales.sql  3) eparc_03_donnees_demo.sql (facultatif)
-- Script rejouable (CREATE ... IF NOT EXISTS / CREATE OR REPLACE).
-- =====================================================================================================================

-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

CREATE SCHEMA IF NOT EXISTS eparc;
SET search_path TO eparc, public;


-- ---------------------------------------------------------------------------------------------------------------------
-- 1. Organisation administrative
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS direction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

-- chef_agent_id : cle etrangere vers agent ajoutee en fin de script (dependance circulaire service <-> agent)
CREATE TABLE IF NOT EXISTS service (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    direction_id BIGINT NOT NULL REFERENCES direction(id),
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    site VARCHAR(150),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    chef_agent_id BIGINT
);

CREATE TABLE IF NOT EXISTS agent (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matricule VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    fonction VARCHAR(150),
    email VARCHAR(180),
    service_id BIGINT REFERENCES service(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    telephone VARCHAR(30),
    whatsapp VARCHAR(30),
    adresse_domicile_exacte TEXT
);

-- Le chef de service est un agent ; si l'agent est supprime, le service n'a plus de chef
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'service_chef_agent_id_fkey'
                   AND conrelid = 'eparc.service'::regclass) THEN
        ALTER TABLE service
            ADD CONSTRAINT service_chef_agent_id_fkey
            FOREIGN KEY (chef_agent_id) REFERENCES agent(id) ON DELETE SET NULL;
    END IF;
END $$;


-- ---------------------------------------------------------------------------------------------------------------------
-- 2. Comptes et autorisations (RBAC)
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS role (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    libelle VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS permission (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(80) UNIQUE NOT NULL,
    libelle VARCHAR(180) NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permission (
    role_id BIGINT REFERENCES role(id) ON DELETE CASCADE,
    permission_id BIGINT REFERENCES permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS utilisateur (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_id BIGINT REFERENCES agent(id) ON DELETE SET NULL,   -- le compte survit, detache de l'agent
    nom_utilisateur VARCHAR(80) UNIQUE NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES role(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------------------------------------------------
-- 3. Materiels individualises et affectations
-- ---------------------------------------------------------------------------------------------------------------------

-- category_menu : menu de l'interface sous lequel l'onglet de la categorie apparait
CREATE TABLE IF NOT EXISTS categorie_materiel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    libelle VARCHAR(100) NOT NULL,
    category_menu VARCHAR(30) NOT NULL DEFAULT 'Matériel',
    CONSTRAINT ck_categorie_materiel_category_menu
        CHECK (category_menu IN ('Matériel', 'Réseau', 'Consommables et stocks', 'Logiciels'))
);

CREATE TABLE IF NOT EXISTS materiel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code_inventaire VARCHAR(60) UNIQUE NOT NULL,
    categorie_id BIGINT NOT NULL REFERENCES categorie_materiel(id),
    designation VARCHAR(180) NOT NULL,
    marque VARCHAR(100),
    modele VARCHAR(100),
    numero_serie VARCHAR(150) UNIQUE,

    -- Specifications techniques : liste "cle: valeur" separee par des virgules (format CSV)
    -- ex. : 'RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U'
    caracteristiques TEXT,

    -- Provenance du materiel (voir aussi provenance_detail pour la precision)
    provenance VARCHAR(20) NOT NULL DEFAULT 'ACHAT'
        CHECK (provenance IN ('ACHAT','DOTATION','AFFECTATION',
                              'PROJET','DON','AUTRE')),
    provenance_detail VARCHAR(180),  -- ex. : nom du projet, bailleur, structure d'origine, n° de bon de livraison

    date_acquisition DATE,
    valeur_acquisition NUMERIC(14,2)
        CHECK (valeur_acquisition IS NULL OR valeur_acquisition >= 0),
    etat VARCHAR(20) NOT NULL DEFAULT 'BON'
        CHECK (etat IN ('NEUF','BON','A_REPARER','EN_PANNE','REFORME')),
    statut VARCHAR(25) NOT NULL DEFAULT 'EN_STOCK'
        CHECK (statut IN ('EN_STOCK','ATTRIBUE',
                          'EN_MAINTENANCE','REFORME')),
    localisation VARCHAR(180),
    observations TEXT,
    image_chemin VARCHAR(255),       -- chemin relatif (dans UPLOAD_DIR) du fichier envoye par l'API
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- agent_id est nullable (ON DELETE SET NULL) : le nom de l'agent est memorise dans agent_matricule / agent_nom
-- pour que l'historique reste lisible apres suppression de l'agent (colonnes a renseigner par le backend).
CREATE TABLE IF NOT EXISTS affectation (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    materiel_id BIGINT NOT NULL REFERENCES materiel(id),
    agent_id BIGINT REFERENCES agent(id) ON DELETE SET NULL,
    date_remise DATE NOT NULL DEFAULT CURRENT_DATE,
    date_retour DATE,
    etat_remise VARCHAR(20),
    etat_retour VARCHAR(20),
    observations TEXT,
    cree_par BIGINT REFERENCES utilisateur(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_matricule VARCHAR(50),
    agent_nom VARCHAR(220),
    CHECK (date_retour IS NULL OR date_retour >= date_remise)
);

-- Un materiel ne peut avoir qu'une affectation active
CREATE UNIQUE INDEX IF NOT EXISTS uq_affectation_active
ON affectation(materiel_id)
WHERE date_retour IS NULL;


-- ---------------------------------------------------------------------------------------------------------------------
-- 4. Dossier d'attribution / d'affectation = fiche de detention
--    Circuit : demande -> approbation (depositaire comptable) -> signature agent puis chef de service
--              -> remise physique -> approbation de la reception.
--    ATTRIBUTION : on donne a un agent un materiel non affecte (EN_STOCK).
--    AFFECTATION : on retire un materiel a son detenteur actuel pour le donner a un autre agent (transfert).
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fiche_detention (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference VARCHAR(30) UNIQUE NOT NULL,            -- FD-AAAA-NNNN
    affectation_id BIGINT UNIQUE REFERENCES affectation(id) ON DELETE CASCADE,  -- renseigne a la remise
    statut VARCHAR(15) NOT NULL DEFAULT 'NON_SIGNEE'  -- etat de signature
        CHECK (statut IN ('NON_SIGNEE','SIGNEE')),
    date_signature DATE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- demande
    agent_id BIGINT REFERENCES agent(id) ON DELETE SET NULL,                  -- futur detenteur
    categorie_id BIGINT REFERENCES categorie_materiel(id),                    -- type demande
    besoin TEXT,                                                              -- type, configuration
    canal VARCHAR(15) NOT NULL DEFAULT 'FORMULAIRE',
    reference_canal VARCHAR(120),                                             -- n° de ticket, objet du mail...
    demandeur VARCHAR(150),                                                   -- collaborateur ou responsable
    date_demande DATE NOT NULL DEFAULT CURRENT_DATE,
    valide_par VARCHAR(150),                                                  -- personne qui valide
    date_validation DATE,
    type_demande VARCHAR(12) NOT NULL DEFAULT 'ATTRIBUTION',
    demande_par BIGINT REFERENCES utilisateur(id),

    -- equipement choisi, fiche generee
    materiel_id BIGINT REFERENCES materiel(id),
    date_generation DATE,

    -- signature
    mode_signature VARCHAR(15) CHECK (mode_signature IN ('MANUSCRITE','ELECTRONIQUE')),
    signe_par VARCHAR(150),
    signature_modifiee_par VARCHAR(80),
    signature_modifiee_le TIMESTAMPTZ,
    signature_agent_par BIGINT REFERENCES utilisateur(id),
    signature_agent_le TIMESTAMPTZ,
    signature_chef_par BIGINT REFERENCES utilisateur(id),
    signature_chef_le TIMESTAMPTZ,

    -- approbation de la demande
    approuve_par BIGINT REFERENCES utilisateur(id),
    approuve_le TIMESTAMPTZ,
    motif_refus TEXT,

    -- remise physique et reception
    date_remise DATE,
    etat_constate VARCHAR(15) CHECK (etat_constate IN ('NEUF','BON','A_REPARER')),
    accessoires VARCHAR(200),                                                 -- liste separee par des virgules
    accessoires_autre VARCHAR(100),
    observations_remise TEXT,
    reception_approuvee_par BIGINT REFERENCES utilisateur(id),
    reception_approuvee_le TIMESTAMPTZ,

    -- cloture du dossier avant la fin
    cloture VARCHAR(10) CHECK (cloture IN ('REFUSEE','ANNULEE')),
    motif_cloture TEXT,

    -- contact
    telephone VARCHAR(30),
    whatsapp VARCHAR(30),
    adresse_domicile_exacte TEXT,

    -- transfert (AFFECTATION) : de qui le materiel a ete retire, quelle affectation a ete cloturee
    ancien_agent_id BIGINT REFERENCES agent(id) ON DELETE SET NULL,
    ancienne_affectation_id BIGINT REFERENCES affectation(id),

    -- memoire du nom de l'agent (historique lisible apres suppression ; a renseigner par le backend)
    agent_matricule VARCHAR(50),
    agent_nom VARCHAR(220),

    CHECK ((statut = 'SIGNEE') = (date_signature IS NOT NULL)),
    CONSTRAINT ck_fiche_type_demande CHECK (type_demande IN ('ATTRIBUTION', 'AFFECTATION')),
    CONSTRAINT ck_fiche_canal CHECK (canal IN ('MAIL', 'TICKET', 'FORMULAIRE', 'SMS', 'WHATSAPP')),
    CONSTRAINT ck_fiche_transfert CHECK (
        (ancien_agent_id IS NULL AND ancienne_affectation_id IS NULL) OR type_demande = 'AFFECTATION'
    )
);

CREATE INDEX IF NOT EXISTS idx_fiche_detention_statut ON fiche_detention(statut);
CREATE INDEX IF NOT EXISTS idx_fiche_detention_agent ON fiche_detention(agent_id);
CREATE INDEX IF NOT EXISTS idx_fiche_approuve ON fiche_detention(approuve_le);
CREATE INDEX IF NOT EXISTS idx_fiche_ancien_agent ON fiche_detention(ancien_agent_id);
CREATE INDEX IF NOT EXISTS idx_service_chef ON service(chef_agent_id);
-- un materiel ne peut etre reserve que par un seul dossier ouvert
CREATE UNIQUE INDEX IF NOT EXISTS uq_fiche_materiel_reserve ON fiche_detention(materiel_id)
    WHERE materiel_id IS NOT NULL AND affectation_id IS NULL AND cloture IS NULL;


-- ---------------------------------------------------------------------------------------------------------------------
-- 5. Notifications (boite d'envoi, sans serveur : le backend range un lien mailto: / sms: / wa.me)
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS notification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fiche_id BIGINT REFERENCES fiche_detention(id) ON DELETE CASCADE,
    evenement VARCHAR(30) NOT NULL
        CONSTRAINT ck_notification_evenement CHECK (evenement IN (
            'DEMANDE_CREEE', 'DEMANDE_APPROUVEE', 'DEMANDE_REFUSEE', 'SIGNATURE_AGENT_REQUISE',
            'SIGNATURE_CHEF_REQUISE', 'MATERIEL_REMIS', 'RECEPTION_A_APPROUVER', 'DOSSIER_TERMINE',
            'MATERIEL_RETIRE')),
    destinataire_agent_id BIGINT NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
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
-- 6. Consommables et stocks
-- ---------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS article_consommable (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference VARCHAR(60) UNIQUE NOT NULL,
    designation VARCHAR(180) NOT NULL,
    categorie VARCHAR(100),
    unite VARCHAR(30) NOT NULL DEFAULT 'unite',
    seuil_alerte NUMERIC(14,3) NOT NULL DEFAULT 0
        CHECK (seuil_alerte >= 0),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS stock_consommable (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES article_consommable(id),
    service_id BIGINT REFERENCES service(id),
    quantite NUMERIC(14,3) NOT NULL DEFAULT 0
        CHECK (quantite >= 0),
    UNIQUE (article_id, service_id)
);

CREATE TABLE IF NOT EXISTS mouvement_consommable (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES article_consommable(id),
    service_source_id BIGINT REFERENCES service(id),
    service_destination_id BIGINT REFERENCES service(id),
    type_mouvement VARCHAR(20) NOT NULL
        CHECK (type_mouvement IN
          ('ENTREE','SORTIE','TRANSFERT','AJUSTEMENT')),
    quantite NUMERIC(14,3) NOT NULL CHECK (quantite > 0),
    reference_document VARCHAR(100),
    -- Provenance de l'entree en stock (dotation, projet, achat ...)
    provenance VARCHAR(20)
        CHECK (provenance IS NULL OR provenance IN
          ('ACHAT','DOTATION','AFFECTATION','PROJET','DON','AUTRE')),
    motif TEXT NOT NULL,
    effectue_par BIGINT NOT NULL REFERENCES utilisateur(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------------------------------------------------
-- 7. Logiciels et licences
--    Un logiciel SANS_LICENCE (libre) ne devrait avoir aucune licence : regle a verifier cote application
--    (le trigger de controle a ete retire).
-- ---------------------------------------------------------------------------------------------------------------------

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

CREATE INDEX IF NOT EXISTS idx_licence_logiciel ON licence(logiciel_id);
CREATE INDEX IF NOT EXISTS idx_licence_expiration ON licence(date_expiration);


-- ---------------------------------------------------------------------------------------------------------------------
-- 8. Journal d'audit
-- ---------------------------------------------------------------------------------------------------------------------

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

CREATE INDEX IF NOT EXISTS idx_audit_date ON journal_audit(cree_le DESC);


-- ---------------------------------------------------------------------------------------------------------------------
-- 9. Index de consultation
-- ---------------------------------------------------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_materiel_statut ON materiel(statut);
CREATE INDEX IF NOT EXISTS idx_materiel_categorie ON materiel(categorie_id);
CREATE INDEX IF NOT EXISTS idx_materiel_provenance ON materiel(provenance);
CREATE INDEX IF NOT EXISTS idx_agent_service ON agent(service_id);
CREATE INDEX IF NOT EXISTS idx_affectation_agent ON affectation(agent_id, date_remise DESC);
CREATE INDEX IF NOT EXISTS idx_mouvement_article_date ON mouvement_consommable(article_id, cree_le DESC);


-- ---------------------------------------------------------------------------------------------------------------------
-- 10. Vues
-- ---------------------------------------------------------------------------------------------------------------------

-- Phase du dossier, deduite des donnees (jamais stockee, donc jamais desynchronisee).
-- role_attendu : qui doit agir (l'ADMIN fait chaque etape).
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

-- Tableau de bord > Repartition : materiel actuellement detenu (affectation sans date de retour)
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

-- Droits de chaque role
CREATE OR REPLACE VIEW v_role_permissions AS
SELECT r.code AS role_code, r.libelle AS role_libelle, p.code AS permission_code, p.libelle AS permission_libelle
FROM role r
JOIN role_permission rp ON rp.role_id = r.id
JOIN permission p ON p.id = rp.permission_id;

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

-- Materiels sans detenteur (a attribuer), neufs ou deja utilises
CREATE OR REPLACE VIEW v_materiels_sans_detenteur AS
SELECT m.id AS materiel_id, m.code_inventaire, m.designation, m.categorie_id,
       EXISTS (SELECT 1 FROM affectation a WHERE a.materiel_id = m.id) AS deja_utilise,
       (SELECT a.agent_nom FROM affectation a WHERE a.materiel_id = m.id ORDER BY a.date_remise DESC, a.id DESC LIMIT 1) AS dernier_detenteur
FROM v_materiels_attribuables m;

-- Historique des transferts : de qui, vers qui (le nouvel agent peut avoir ete supprime depuis)
DROP VIEW IF EXISTS v_transferts;
CREATE VIEW v_transferts AS
SELECT f.id AS fiche_id, f.reference, f.materiel_id, m.code_inventaire,
       f.ancien_agent_id, f.agent_id AS nouvel_agent_id, f.agent_nom AS nouvel_agent_nom, f.date_remise, f.reception_approuvee_le
FROM fiche_detention f
JOIN materiel m ON m.id = f.materiel_id
WHERE f.type_demande = 'AFFECTATION' AND f.ancienne_affectation_id IS NOT NULL;
