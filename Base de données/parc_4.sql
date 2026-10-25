-- Encodage : le script est en UTF-8, quel que soit le reglage par defaut du client (psql sous Windows = WIN1252)
SET client_encoding TO 'UTF8';

SET search_path TO eparc, public;


INSERT INTO role(code, libelle) VALUES -- Roles initiaux
 ('ADMIN', 'Administrateur'),
 ('GESTIONNAIRE', 'Gestionnaire du parc - Affectation seule'),
 ('LECTURE', 'Consultation seule')
ON CONFLICT (code) DO NOTHING;

-- Complement : categories de materiel utilisees par les onglets de l'interface
-- (a executer apres parc.sql, parc_2.sql et parc_3.sql ; sans danger si relance)
INSERT INTO categorie_materiel(code, libelle) VALUES
 ('ORDINATEUR', 'Ordinateur'),
 ('ECRAN', 'Écran'),
 ('PERIPHERIQUE', 'Périphérique'),
 ('TELEPHONE', 'Téléphone'),
 ('IMPRIMANTE', 'Imprimante'),
 ('NON_GERE', 'Équipement non géré'),
 ('RESEAU', 'Équipement réseau'),
 ('BAIE', 'Baie'),
 ('CHASSIS', 'Châssis'),
 ('PDU', 'PDU'),
 ('PASSIF', 'Équipement passif'),
 ('CABLE', 'Câble'),
 ('SIM', 'Carte SIM')
ON CONFLICT (code) DO NOTHING;
