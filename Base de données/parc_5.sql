SET search_path TO eparc, public;

-- Image du materiel : chemin relatif (dans UPLOAD_DIR) du fichier envoye par l'API
ALTER TABLE materiel ADD COLUMN IF NOT EXISTS image_chemin VARCHAR(255);

-- Fiche de detention : une par affectation, creee automatiquement par l'API
CREATE TABLE IF NOT EXISTS fiche_detention (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    affectation_id BIGINT NOT NULL UNIQUE REFERENCES affectation(id) ON DELETE CASCADE,
    reference VARCHAR(30) UNIQUE NOT NULL,            -- FD-AAAA-NNNN
    statut VARCHAR(15) NOT NULL DEFAULT 'NON_SIGNEE'
        CHECK (statut IN ('NON_SIGNEE','SIGNEE')),
    date_signature DATE,
    fichier_signe_chemin VARCHAR(255),                -- scan du document signe (facultatif)
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((statut = 'SIGNEE') = (date_signature IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_fiche_detention_statut
ON fiche_detention(statut);

-- Fiches des affectations deja existantes (sans danger si relance)
INSERT INTO fiche_detention (affectation_id, reference)
SELECT a.id,
       'FD-' || to_char(a.date_remise, 'YYYY') || '-' ||
       lpad((COALESCE(m.max_n, 0)
             + ROW_NUMBER() OVER (PARTITION BY to_char(a.date_remise, 'YYYY') ORDER BY a.id))::text, 4, '0')
FROM affectation a
LEFT JOIN LATERAL (
    SELECT MAX(substring(f.reference FROM 9)::int) AS max_n
    FROM fiche_detention f
    WHERE f.reference LIKE 'FD-' || to_char(a.date_remise, 'YYYY') || '-%'
) m ON TRUE
WHERE NOT EXISTS (SELECT 1 FROM fiche_detention f WHERE f.affectation_id = a.id);
