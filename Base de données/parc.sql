-- eparc : Systeme de gestion du parc informatique

CREATE SCHEMA IF NOT EXISTS eparc;
SET search_path TO eparc, public;

-- Organisation administrative
-- (creee avant les comptes : utilisateur depend de agent)

CREATE TABLE IF NOT EXISTS direction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

-- CREATE TABLE division ();

CREATE TABLE IF NOT EXISTS service (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    direction_id BIGINT NOT NULL REFERENCES direction(id),
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    site VARCHAR(150),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS agent (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matricule VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    fonction VARCHAR(150),
    email VARCHAR(180),
    service_id BIGINT REFERENCES service(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

-- Comptes et autorisations

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
    agent_id BIGINT REFERENCES agent(id),
    nom_utilisateur VARCHAR(80) UNIQUE NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES role(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO role(code, libelle) VALUES -- Roles initiaux
 ('ADMIN', 'Administrateur'),
 ('GESTIONNAIRE', 'Gestionnaire du parc - Affectation seule'),
 ('LECTURE', 'Consultation seule')
ON CONFLICT (code) DO NOTHING;

-- Affectation et Materiels individualises

CREATE TABLE IF NOT EXISTS categorie_materiel (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    libelle VARCHAR(100) NOT NULL
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
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS affectation (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    materiel_id BIGINT NOT NULL REFERENCES materiel(id),
    agent_id BIGINT NOT NULL REFERENCES agent(id),
    date_remise DATE NOT NULL DEFAULT CURRENT_DATE,
    date_retour DATE,
    etat_remise VARCHAR(20),
    etat_retour VARCHAR(20),
    observations TEXT,
    cree_par BIGINT REFERENCES utilisateur(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (date_retour IS NULL OR date_retour >= date_remise)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_affectation_active -- Un materiel ne peut avoir qu'une affectation active
ON affectation(materiel_id)
WHERE date_retour IS NULL;

-- Consommables et stocks

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

-- Index de consultation
CREATE INDEX IF NOT EXISTS idx_materiel_statut
ON materiel(statut);

CREATE INDEX IF NOT EXISTS idx_materiel_categorie
ON materiel(categorie_id);

CREATE INDEX IF NOT EXISTS idx_materiel_provenance
ON materiel(provenance);

CREATE INDEX IF NOT EXISTS idx_agent_service
ON agent(service_id);

CREATE INDEX IF NOT EXISTS idx_affectation_agent
ON affectation(agent_id, date_remise DESC);

CREATE INDEX IF NOT EXISTS idx_mouvement_article_date
ON mouvement_consommable(article_id, cree_le DESC);