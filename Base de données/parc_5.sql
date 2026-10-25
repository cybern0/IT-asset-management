SET search_path TO eparc, public;

-- Image du materiel : chemin relatif (dans UPLOAD_DIR) du fichier envoye par l'API
ALTER TABLE materiel ADD COLUMN IF NOT EXISTS image_chemin VARCHAR(255);

-- Dossier d'attribution = fiche de detention, suivant le processus en 6 etapes :
--   1 demande (+ validation du manager)   2 selection de l'equipement en stock
--   3 generation de la fiche              4 signature (detenteur + responsable)
--   5 remise physique (controle d'etat)   6 mise a jour du statut : materiel « Attribue » (affectation)
-- Script rejouable : migre aussi l'ancienne table creee par une version precedente de parc_5.sql.
CREATE TABLE IF NOT EXISTS fiche_detention (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference VARCHAR(30) UNIQUE NOT NULL,            -- FD-AAAA-NNNN
    affectation_id BIGINT UNIQUE REFERENCES affectation(id) ON DELETE CASCADE,  -- renseigne a l'etape 6
    statut VARCHAR(15) NOT NULL DEFAULT 'NON_SIGNEE'  -- etat de signature (etape 4)
        CHECK (statut IN ('NON_SIGNEE','SIGNEE')),
    date_signature DATE,
    fichier_signe_chemin VARCHAR(255),                -- scan du document signe (facultatif)
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((statut = 'SIGNEE') = (date_signature IS NOT NULL))
);

ALTER TABLE fiche_detention ALTER COLUMN affectation_id DROP NOT NULL;

ALTER TABLE fiche_detention
    -- etape 1 : demande et validation
    ADD COLUMN IF NOT EXISTS agent_id BIGINT REFERENCES agent(id),            -- futur detenteur
    ADD COLUMN IF NOT EXISTS categorie_id BIGINT REFERENCES categorie_materiel(id),  -- type demande
    ADD COLUMN IF NOT EXISTS besoin TEXT,                                      -- type, configuration
    ADD COLUMN IF NOT EXISTS canal VARCHAR(15) NOT NULL DEFAULT 'FORMULAIRE'
        CHECK (canal IN ('MAIL','TICKET','FORMULAIRE')),
    ADD COLUMN IF NOT EXISTS reference_canal VARCHAR(120),                     -- n° de ticket, objet du mail...
    ADD COLUMN IF NOT EXISTS demandeur VARCHAR(150),                           -- collaborateur ou responsable
    ADD COLUMN IF NOT EXISTS date_demande DATE NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN IF NOT EXISTS valide_par VARCHAR(150),                          -- manager qui valide
    ADD COLUMN IF NOT EXISTS date_validation DATE,
    -- etapes 2 et 3 : equipement choisi, fiche generee
    ADD COLUMN IF NOT EXISTS materiel_id BIGINT REFERENCES materiel(id),
    ADD COLUMN IF NOT EXISTS date_generation DATE,
    -- etape 4 : signature
    ADD COLUMN IF NOT EXISTS mode_signature VARCHAR(15) CHECK (mode_signature IN ('MANUSCRITE','ELECTRONIQUE')),
    ADD COLUMN IF NOT EXISTS signe_par VARCHAR(150),                           -- responsable informatique ou hierarchique
    -- etape 5 : remise physique
    ADD COLUMN IF NOT EXISTS date_remise DATE,
    ADD COLUMN IF NOT EXISTS etat_constate VARCHAR(15) CHECK (etat_constate IN ('NEUF','BON','A_REPARER')),
    ADD COLUMN IF NOT EXISTS accessoires VARCHAR(200),                         -- liste separee par des virgules
    ADD COLUMN IF NOT EXISTS accessoires_autre VARCHAR(100),
    ADD COLUMN IF NOT EXISTS observations_remise TEXT,
    -- cloture du dossier avant la fin
    ADD COLUMN IF NOT EXISTS cloture VARCHAR(10) CHECK (cloture IN ('REFUSEE','ANNULEE')),
    ADD COLUMN IF NOT EXISTS motif_cloture TEXT;

-- Anciennes fiches (une par affectation) : dossier deja termine
UPDATE fiche_detention f
SET agent_id = a.agent_id,
    materiel_id = a.materiel_id,
    date_demande = a.date_remise,
    valide_par = 'Régularisation',
    date_validation = a.date_remise,
    date_generation = a.date_remise,
    date_remise = a.date_remise,
    etat_constate = CASE WHEN a.etat_remise IN ('NEUF','BON','A_REPARER') THEN a.etat_remise END,
    besoin = 'Régularisation (affectation saisie hors circuit de demande)'
FROM affectation a
WHERE a.id = f.affectation_id AND f.agent_id IS NULL;

ALTER TABLE fiche_detention ALTER COLUMN agent_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fiche_detention_statut ON fiche_detention(statut);
CREATE INDEX IF NOT EXISTS idx_fiche_detention_agent ON fiche_detention(agent_id);
-- un materiel ne peut etre reserve que par un seul dossier ouvert
CREATE UNIQUE INDEX IF NOT EXISTS uq_fiche_materiel_reserve ON fiche_detention(materiel_id)
    WHERE materiel_id IS NOT NULL AND affectation_id IS NULL AND cloture IS NULL;

-- Dossiers des affectations deja existantes et sans fiche (sans danger si relance)
INSERT INTO fiche_detention (affectation_id, reference, agent_id, materiel_id, besoin,
                             date_demande, valide_par, date_validation, date_generation, date_remise, etat_constate)
SELECT a.id,
       'FD-' || to_char(a.date_remise, 'YYYY') || '-' ||
       lpad((COALESCE(m.max_n, 0)
             + ROW_NUMBER() OVER (PARTITION BY to_char(a.date_remise, 'YYYY') ORDER BY a.id))::text, 4, '0'),
       a.agent_id, a.materiel_id, 'Régularisation (affectation saisie hors circuit de demande)',
       a.date_remise, 'Régularisation', a.date_remise, a.date_remise, a.date_remise,
       CASE WHEN a.etat_remise IN ('NEUF','BON','A_REPARER') THEN a.etat_remise END
FROM affectation a
LEFT JOIN LATERAL (
    SELECT MAX(substring(f.reference FROM 9)::int) AS max_n
    FROM fiche_detention f
    WHERE f.reference LIKE 'FD-' || to_char(a.date_remise, 'YYYY') || '-%'
) m ON TRUE
WHERE NOT EXISTS (SELECT 1 FROM fiche_detention f WHERE f.affectation_id = a.id);
