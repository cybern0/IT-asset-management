/* =====================================================================
   Schéma de l'UI, calqué sur « parc.sql » (schéma PostgreSQL eparc).
   - table  : table PostgreSQL correspondante (plusieurs onglets peuvent
              partager une table, ex. materiel filtré par catégorie)
   - where  : filtre d'onglet (et valeur pré-remplie à la création)
   - local  : rubrique absente de parc.sql (champs provisoires)
   ===================================================================== */

export type Row = { id: string } & Record<string, string>;
export type Opt = { v: string; l: string };

export type FieldType =
  | "text" | "number" | "select" | "textarea" | "date" | "email" | "password"
  | "ref" // clé étrangère -> liste déroulante
  | "multiref"; // table de liaison (ex. role_permission) -> cases à cocher

export type Field = {
  name: string; // nom de la colonne SQL
  label: string;
  type: FieldType;
  options?: Opt[];
  ref?: string; // table référencée
  required?: boolean; // NOT NULL
  unique?: boolean; // UNIQUE
  min?: number; // CHECK (>= min)
  gt?: number; // CHECK (> gt)
  readonly?: boolean;
  auto?: "today";
  default?: string; // "today" accepté
  placeholder?: string;
  hint?: string;
};

export type Ctx = {
  label: (table: string, id: string) => string;
  find: (table: string, id: string) => Row | undefined;
  rows: (table: string) => Row[];
  t?: (s: string, vars?: Record<string, string | number>) => string;
};

export type Entity = {
  key: string; // dernier segment de l'URL
  label: string; // libellé de l'onglet
  singular: string; // « un ordinateur » (bouton +)
  table: string;
  where?: { field: string; value: string; negate?: boolean };
  titleFields: string[];
  subtitleFields?: string[];
  badgeField?: string;
  badgeFn?: (row: Row, ctx: Ctx) => string;
  fields: Field[];
  seed?: Record<string, string>[];
  local?: boolean;
  validate?: (
    draft: Record<string, string>,
    env: { rows: Row[]; selfId: string | null; ctx: Ctx },
  ) => Record<string, string>;
};

export type IconName =
  | "monitor" | "layers" | "printer" | "network" | "rack"
  | "globe" | "users" | "sliders" | "clock" | "scan";

export type Group = {
  slug: string;
  label: string;
  description: string;
  icon: IconName;
  kind?: "crud" | "global";
  entities: Entity[];
};

export type Section = {
  slug: "assets" | "administration";
  label: string;
  groups: Group[];
};

/* ---------- helpers de définition ---------- */
const norm = (o: (string | Opt)[]): Opt[] => o.map((x) => (typeof x === "string" ? { v: x, l: x } : x));
const optsL = (m: Record<string, string>): Opt[] => Object.entries(m).map(([v, l]) => ({ v, l }));

const text = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "text", ...o });
const num = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "number", ...o });
const date = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "date", ...o });
const email = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "email", ...o });
const area = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "textarea", ...o });
const pass = (name: string, label: string, o: Partial<Field> = {}): Field => ({ name, label, type: "password", ...o });
const pick = (name: string, label: string, options: (string | Opt)[], o: Partial<Field> = {}): Field => ({
  name, label, type: "select", options: norm(options), ...o,
});
const ref = (name: string, label: string, table: string, o: Partial<Field> = {}): Field => ({
  name, label, type: "ref", ref: table, ...o,
});
const multiref = (name: string, label: string, table: string, o: Partial<Field> = {}): Field => ({
  name, label, type: "multiref", ref: table, ...o,
});
const created = () => date("cree_le", "Créé le", { readonly: true, auto: "today" });

const YESNO = optsL({ true: "Oui", false: "Non" });
const actif = () => pick("actif", "Actif", YESNO, { required: true });

const PROVENANCE = optsL({ ACHAT: "Achat", DOTATION: "Dotation", AFFECTATION: "Affectation", PROJET: "Projet", DON: "Don", AUTRE: "Autre" });
const ETAT = optsL({ NEUF: "Neuf", BON: "Bon", A_REPARER: "À réparer", EN_PANNE: "En panne", REFORME: "Réformé" });
const STATUT = optsL({ EN_STOCK: "En stock", ATTRIBUE: "Attribué", EN_MAINTENANCE: "En maintenance", REFORME: "Réformé" });
const MOUVEMENT = optsL({ ENTREE: "Entrée", SORTIE: "Sortie", TRANSFERT: "Transfert", AJUSTEMENT: "Ajustement" });

function ent(e: Omit<Entity, "table"> & { table?: string }): Entity {
  return { table: e.key, ...e };
}

/** Onglet « matériel » : table materiel filtrée sur une catégorie (categorie_id). */
function materielTab(
  key: string, label: string, singular: string, categorieId: string, hint: string,
  seed: Record<string, string>[] = [],
): Entity {
  return ent({
    key, label, singular, table: "materiel",
    where: { field: "categorie_id", value: categorieId },
    titleFields: ["designation"], subtitleFields: ["code_inventaire"], badgeField: "statut",
    fields: [
      text("code_inventaire", "Code d’inventaire", { required: true, unique: true }),
      ref("categorie_id", "Catégorie", "categorie_materiel", { required: true }),
      text("designation", "Désignation", { required: true }),
      text("marque", "Marque"),
      text("modele", "Modèle"),
      text("numero_serie", "N° de série", { unique: true }),
      area("caracteristiques", "Caractéristiques", {
        placeholder: hint, hint: "Format « clé: valeur », séparées par des virgules.",
      }),
      pick("provenance", "Provenance", PROVENANCE, { required: true }),
      text("provenance_detail", "Précision sur la provenance", { hint: "Projet, bailleur, structure d’origine, n° de bon de livraison…" }),
      date("date_acquisition", "Date d’acquisition"),
      num("valeur_acquisition", "Valeur d’acquisition", { min: 0 }),
      pick("etat", "État", ETAT, { required: true, default: "BON" }),
      pick("statut", "Statut", STATUT, { required: true }),
      text("localisation", "Localisation"),
      area("observations", "Observations"),
      created(),
    ],
    seed,
  });
}

/* ================= ASSETS ================= */
const materiel: Entity[] = [
  materielTab("computers", "Computers", "un ordinateur", "ORDINATEUR",
    "RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U", [
      { code_inventaire: "ORD-0001", designation: "Dell Latitude 5440", marque: "Dell", modele: "Latitude 5440", numero_serie: "7KQ2N93", caracteristiques: "RAM: 16 Go, Stockage: 512 Go SSD, OS: Windows 11 Pro, CPU: Intel i5-1235U", provenance: "ACHAT", etat: "BON", statut: "ATTRIBUE", localisation: "Bureau 12" },
      { code_inventaire: "ORD-0002", designation: "HP ProDesk 400", marque: "HP", modele: "ProDesk 400", caracteristiques: "RAM: 8 Go, Stockage: 256 Go SSD, OS: Windows 10 Pro", provenance: "DOTATION", etat: "BON", statut: "EN_STOCK", localisation: "Magasin" },
    ]),
  materielTab("monitors", "Monitors", "un écran", "ECRAN", "Taille: 24 pouces, Résolution: 1920x1080, Ports: HDMI/VGA"),
  materielTab("peripherals", "Peripherals", "un périphérique", "PERIPHERIQUE", "Type: Clavier, Connectique: USB"),
  materielTab("phones", "Phones", "un téléphone", "TELEPHONE", "Ligne: 034 00 000 00, IMEI: 000000000000000"),
  materielTab("printers", "Printers", "une imprimante", "IMPRIMANTE", "Type: Laser, IP: 10.0.0.41, Service: Comptabilité", [
    { code_inventaire: "IMP-0001", designation: "Canon iR 1643", marque: "Canon", modele: "iR 1643", caracteristiques: "Type: Multifonction, IP: 10.0.0.41", provenance: "ACHAT", etat: "BON", statut: "EN_STOCK" },
  ]),
  materielTab("unmanaged", "Unmanaged assets", "un équipement non géré", "NON_GERE", "IP: 10.0.0.77, MAC: AA:BB:CC:DD:EE:FF, Type détecté: caméra"),
  ent({
    key: "affectations", label: "Affectations", singular: "une affectation", table: "affectation",
    titleFields: ["materiel_id"], subtitleFields: ["agent_id"],
    badgeFn: (r) => (r.date_retour ? "Rendue" : "Active"),
    fields: [
      ref("materiel_id", "Matériel", "materiel", { required: true }),
      ref("agent_id", "Agent", "agent", { required: true }),
      date("date_remise", "Date de remise", { required: true, default: "today" }),
      date("date_retour", "Date de retour"),
      pick("etat_remise", "État à la remise", ETAT),
      pick("etat_retour", "État au retour", ETAT),
      ref("cree_par", "Enregistrée par", "utilisateur"),
      area("observations", "Observations"),
      created(),
    ],
    validate: (d, { rows, selfId }) => {
      const e: Record<string, string> = {};
      if (d.date_retour && d.date_remise && d.date_retour < d.date_remise)
        e.date_retour = "Le retour ne peut pas précéder la remise.";
      if (!d.date_retour && d.materiel_id &&
          rows.some((r) => r.id !== selfId && r.materiel_id === d.materiel_id && !r.date_retour))
        e.materiel_id = "Ce matériel a déjà une affectation active. Enregistrez d’abord son retour.";
      return e;
    },
    seed: [{ materiel_id: "computers-seed-0", agent_id: "a1", date_remise: "2026-09-01", etat_remise: "BON" }],
  }),
];

const reseau: Entity[] = [
  materielTab("network", "Network devices", "un équipement réseau", "RESEAU", "Type: Switch, Ports: 24, IP: 10.0.0.2", [
    { code_inventaire: "RES-0001", designation: "Cisco Catalyst 2960", marque: "Cisco", modele: "Catalyst 2960", caracteristiques: "Type: Switch, Ports: 24, IP: 10.0.0.2", provenance: "ACHAT", etat: "BON", statut: "ATTRIBUE", localisation: "Salle serveur" },
  ]),
  materielTab("racks", "Racks", "une baie", "BAIE", "Salle: Serveur, Hauteur: 42U"),
  materielTab("enclosures", "Enclosures", "un châssis", "CHASSIS", "Baie: BAI-0001, Position: 12U"),
  materielTab("pdus", "PDUs", "une PDU", "PDU", "Baie: BAI-0001, Puissance max: 3600 W, Prises: 12"),
  materielTab("passive", "Passive devices", "un équipement passif", "PASSIF", "Type: Panneau de brassage, Baie: BAI-0001, Position: 40U"),
  materielTab("cables", "Cables", "un câble", "CABLE", "Type: RJ45 Cat6, Longueur: 3 m"),
  materielTab("simcards", "SIM cards", "une carte SIM", "SIM", "Numéro: 034 00 000 00, Opérateur: Telma, Forfait: Pro"),
];

const consommables: Entity[] = [
  ent({
    key: "cartridges", label: "Cartridges", singular: "une cartouche", table: "article_consommable",
    where: { field: "categorie", value: "Cartouche" },
    titleFields: ["designation"], subtitleFields: ["reference"], badgeField: "actif",
    fields: [
      text("reference", "Référence", { required: true, unique: true }),
      text("designation", "Désignation", { required: true }),
      text("categorie", "Catégorie"),
      text("unite", "Unité", { required: true, default: "unite" }),
      num("seuil_alerte", "Seuil d’alerte", { required: true, min: 0, default: "0" }),
      actif(),
    ],
    seed: [{ reference: "CTG-054-N", designation: "Toner Canon 054 noir", unite: "unite", seuil_alerte: "2", actif: "true" }],
  }),
  ent({
    key: "consumables", label: "Consumables", singular: "un consommable", table: "article_consommable",
    where: { field: "categorie", value: "Cartouche", negate: true },
    titleFields: ["designation"], subtitleFields: ["reference"], badgeField: "actif",
    fields: [
      text("reference", "Référence", { required: true, unique: true }),
      text("designation", "Désignation", { required: true }),
      text("categorie", "Catégorie", { placeholder: "Papier, Pile, Câble…" }),
      text("unite", "Unité", { required: true, default: "unite" }),
      num("seuil_alerte", "Seuil d’alerte", { required: true, min: 0, default: "0" }),
      actif(),
    ],
    validate: (d) =>
      (d.categorie ?? "").trim().toLowerCase() === "cartouche"
        ? { categorie: "Les cartouches se gèrent dans l’onglet Cartridges." } : ({} as Record<string, string>),
    seed: [{ reference: "PAP-A4", designation: "Ramette de papier A4", categorie: "Papier", unite: "ramette", seuil_alerte: "10", actif: "true" }],
  }),
  ent({
    key: "stocks", label: "Stocks", singular: "un stock", table: "stock_consommable",
    titleFields: ["article_id"], subtitleFields: ["service_id"],
    badgeFn: (r, c) => {
      const a = c.find("article_consommable", r.article_id);
      return a && Number(r.quantite) <= Number(a.seuil_alerte) ? "Sous le seuil" : r.quantite;
    },
    fields: [
      ref("article_id", "Article", "article_consommable", { required: true }),
      ref("service_id", "Service", "service", { hint: "Laisser vide pour le stock central." }),
      num("quantite", "Quantité", { required: true, min: 0, default: "0" }),
    ],
    validate: (d, { rows, selfId }) =>
      rows.some((r) => r.id !== selfId && r.article_id === d.article_id && (r.service_id ?? "") === (d.service_id ?? ""))
        ? { article_id: "Un stock existe déjà pour cet article et ce service." } : ({} as Record<string, string>),
  }),
  ent({
    key: "mouvements", label: "Mouvements", singular: "un mouvement", table: "mouvement_consommable",
    titleFields: ["article_id"], subtitleFields: ["type_mouvement", "quantite"],
    fields: [
      ref("article_id", "Article", "article_consommable", { required: true }),
      pick("type_mouvement", "Type de mouvement", MOUVEMENT, { required: true }),
      num("quantite", "Quantité", { required: true, gt: 0 }),
      ref("service_source_id", "Service source", "service"),
      ref("service_destination_id", "Service destination", "service"),
      text("reference_document", "Document de référence"),
      pick("provenance", "Provenance de l’entrée", PROVENANCE),
      area("motif", "Motif", { required: true }),
      ref("effectue_par", "Effectué par", "utilisateur", { required: true }),
      created(),
    ],
  }),
];

const TYPE_LICENCE = optsL({ SANS_LICENCE: "Sans licence", PERPETUELLE: "Perpétuelle", ABONNEMENT: "Abonnement" });

const logiciels: Entity[] = [
  ent({
    key: "software", label: "Software", singular: "un logiciel", table: "logiciel",
    titleFields: ["nom", "version"], subtitleFields: ["editeur"], badgeField: "type_licence",
    fields: [
      text("nom", "Nom", { required: true }),
      text("editeur", "Éditeur"),
      text("version", "Version"),
      pick("type_licence", "Type de licence", TYPE_LICENCE, { required: true, default: "PERPETUELLE" }),
      area("observations", "Observations"),
      created(),
    ],
    validate: (d, { rows, selfId }) =>
      rows.some((r) => r.id !== selfId && (r.nom ?? "").toLowerCase() === (d.nom ?? "").trim().toLowerCase()
        && (r.version ?? "").toLowerCase() === (d.version ?? "").trim().toLowerCase())
        ? { nom: "Ce logiciel existe déjà avec cette version." } : ({} as Record<string, string>),
    seed: [
      { id: "sw1", nom: "Microsoft Office", editeur: "Microsoft", version: "2021", type_licence: "PERPETUELLE" },
      { id: "sw2", nom: "LibreOffice", editeur: "The Document Foundation", version: "24.8", type_licence: "SANS_LICENCE" },
    ],
  }),
  ent({
    key: "licenses", label: "Licenses", singular: "une licence", table: "licence",
    titleFields: ["logiciel_id"], subtitleFields: ["date_expiration"],
    badgeFn: (r) => (r.date_expiration && r.date_expiration < new Date().toISOString().slice(0, 10) ? "Expirée" : "Active"),
    fields: [
      ref("logiciel_id", "Logiciel", "logiciel", { required: true }),
      text("cle_licence", "Clé de licence"),
      num("nombre_postes", "Nombre de postes", { required: true, gt: 0, default: "1" }),
      date("date_expiration", "Date d’expiration"),
      area("observations", "Observations"),
      created(),
    ],
    validate: (d, { ctx }) =>
      ctx.find("logiciel", d.logiciel_id)?.type_licence === "SANS_LICENCE"
        ? { logiciel_id: "Ce logiciel est sans licence : aucune licence à enregistrer." } : ({} as Record<string, string>),
    seed: [{ logiciel_id: "sw1", cle_licence: "XXXXX-XXXXX-XXXXX", nombre_postes: "10" }],
  }),
];

/* ================= ADMINISTRATION ================= */
const organisation: Entity[] = [
  ent({
    key: "directions", label: "Directions", singular: "une direction", table: "direction",
    titleFields: ["nom"], subtitleFields: ["code"], badgeField: "actif",
    fields: [text("code", "Code", { required: true, unique: true }), text("nom", "Nom", { required: true }), actif()],
    seed: [{ id: "d1", code: "DG", nom: "Direction générale", actif: "true" }],
  }),
  ent({
    key: "services", label: "Services", singular: "un service", table: "service",
    titleFields: ["nom"], subtitleFields: ["direction_id"], badgeField: "actif",
    fields: [
      ref("direction_id", "Direction", "direction", { required: true }),
      text("code", "Code", { required: true, unique: true }),
      text("nom", "Nom", { required: true }),
      text("site", "Site"),
      actif(),
    ],
    seed: [{ id: "s1", direction_id: "d1", code: "SI", nom: "Service informatique", site: "Siège", actif: "true" }],
  }),
  ent({
    key: "agents", label: "Agents", singular: "un agent", table: "agent",
    titleFields: ["nom", "prenom"], subtitleFields: ["matricule"], badgeField: "actif",
    fields: [
      text("matricule", "Matricule", { required: true, unique: true }),
      text("nom", "Nom", { required: true }),
      text("prenom", "Prénom", { required: true }),
      text("fonction", "Fonction"),
      email("email", "E-mail"),
      ref("service_id", "Service", "service"),
      actif(),
    ],
    seed: [{ id: "a1", matricule: "M0001", nom: "Rakoto", prenom: "Jean", fonction: "Technicien", service_id: "s1", actif: "true" }],
  }),
];

const acces: Entity[] = [
  ent({
    key: "users", label: "Users", singular: "un utilisateur", table: "utilisateur",
    titleFields: ["nom_utilisateur"], subtitleFields: ["role_id"], badgeField: "actif",
    fields: [
      ref("agent_id", "Agent", "agent"),
      text("nom_utilisateur", "Nom d’utilisateur", { required: true, unique: true }),
      pass("mot_de_passe_hash", "Mot de passe", {
        required: true, placeholder: "Laisser vide pour ne pas le changer",
        hint: "Le serveur stockera uniquement son hash.",
      }),
      ref("role_id", "Rôle", "role", { required: true }),
      actif(),
      date("derniere_connexion", "Dernière connexion", { readonly: true }),
      created(),
    ],
    seed: [{ id: "u1", nom_utilisateur: "admin", mot_de_passe_hash: "••••••••", role_id: "ADMIN", actif: "true" }],
  }),
  ent({
    key: "roles", label: "Roles", singular: "un rôle", table: "role",
    titleFields: ["libelle"], subtitleFields: ["code"],
    fields: [
      text("code", "Code", { required: true, unique: true }),
      text("libelle", "Libellé", { required: true }),
      multiref("permissions", "Permissions", "permission"),
    ],
    seed: [
      { id: "ADMIN", code: "ADMIN", libelle: "Administrateur", permissions: "materiel:lire,materiel:modifier,affectation:creer,stock:gerer,utilisateur:gerer" },
      { id: "GESTIONNAIRE", code: "GESTIONNAIRE", libelle: "Gestionnaire du parc - Affectation seule", permissions: "materiel:lire,affectation:creer" },
      { id: "LECTURE", code: "LECTURE", libelle: "Consultation seule", permissions: "materiel:lire" },
    ],
  }),
  ent({
    key: "permissions", label: "Permissions", singular: "une permission", table: "permission",
    titleFields: ["libelle"], subtitleFields: ["code"],
    fields: [
      text("code", "Code", { required: true, unique: true }),
      text("libelle", "Libellé", { required: true }),
    ],
    seed: [
      { id: "materiel:lire", code: "materiel:lire", libelle: "Consulter le matériel" },
      { id: "materiel:modifier", code: "materiel:modifier", libelle: "Créer et modifier le matériel" },
      { id: "affectation:creer", code: "affectation:creer", libelle: "Affecter et reprendre du matériel" },
      { id: "stock:gerer", code: "stock:gerer", libelle: "Gérer les stocks de consommables" },
      { id: "utilisateur:gerer", code: "utilisateur:gerer", libelle: "Gérer les utilisateurs et les rôles" },
    ],
  }),
];

const dictionnaires: Entity[] = [
  ent({
    key: "categories", label: "Catégories de matériel", singular: "une catégorie", table: "categorie_materiel",
    titleFields: ["libelle"], subtitleFields: ["code"],
    fields: [
      text("code", "Code", { required: true, unique: true }),
      text("libelle", "Libellé", { required: true }),
    ],
    seed: [
      ["ORDINATEUR", "Ordinateur"], ["ECRAN", "Écran"], ["PERIPHERIQUE", "Périphérique"], ["TELEPHONE", "Téléphone"],
      ["IMPRIMANTE", "Imprimante"], ["NON_GERE", "Équipement non géré"], ["RESEAU", "Équipement réseau"],
      ["BAIE", "Baie"], ["CHASSIS", "Châssis"], ["PDU", "PDU"], ["PASSIF", "Équipement passif"],
      ["CABLE", "Câble"], ["SIM", "Carte SIM"],
    ].map(([code, libelle]) => ({ id: code, code, libelle })),
  }),
];

const automatisation: Entity[] = [
  ent({
    key: "rules", label: "Rules", singular: "une règle", local: true,
    titleFields: ["name"], subtitleFields: ["trigger"], badgeField: "active",
    fields: [
      text("name", "Nom", { required: true }),
      pick("trigger", "Déclencheur", ["Création", "Modification", "Import"], { required: true }),
      area("condition", "Condition"), area("action", "Action"),
      pick("active", "Active", YESNO, { required: true }),
    ],
  }),
  ent({
    key: "forms", label: "Forms", singular: "un formulaire", local: true,
    titleFields: ["title"], subtitleFields: ["target"], badgeField: "published",
    fields: [
      text("title", "Titre", { required: true }),
      pick("target", "Cible", ["Ordinateur", "Imprimante", "Téléphone", "Réseau", "Autre"]),
      area("fields", "Champs (un par ligne)"),
      pick("published", "Publié", YESNO, { required: true }),
    ],
  }),
];

const suivi: Entity[] = [
  ent({
    key: "queue", label: "Notification queue", singular: "une notification", local: true,
    titleFields: ["subject"], subtitleFields: ["to"], badgeField: "state",
    fields: [
      text("to", "Destinataire", { required: true }), text("subject", "Sujet", { required: true }),
      pick("channel", "Canal", ["E-mail", "SMS"]), date("scheduled", "Planifiée le"),
      pick("state", "État", ["En attente", "Envoyée", "Échec"], { required: true }),
    ],
  }),
  ent({
    key: "logs", label: "Logs", singular: "une entrée de journal", table: "journal_audit",
    titleFields: ["action"], subtitleFields: ["table_cible", "identifiant_cible"],
    fields: [
      text("action", "Action", { required: true, placeholder: "ex. AFFECTATION_CREEE" }),
      ref("utilisateur_id", "Utilisateur", "utilisateur"),
      text("table_cible", "Table concernée"),
      num("identifiant_cible", "Identifiant concerné", { min: 0 }),
      area("details", "Détails (JSON)", { placeholder: '{"cle": "valeur"}' }),
      text("adresse_ip", "Adresse IP", { placeholder: "10.0.0.5" }),
      created(),
    ],
    validate: (d) => {
      const e: Record<string, string> = {};
      const det = (d.details ?? "").trim();
      if (det) { try { JSON.parse(det); } catch { e.details = "JSON invalide."; } }
      const ip = (d.adresse_ip ?? "").trim();
      const v4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}(\/\d{1,2})?$/;
      const v6 = /^[0-9a-f:]*:[0-9a-f:.]*(\/\d{1,3})?$/i;
      if (ip && !v4.test(ip) && !v6.test(ip)) e.adresse_ip = "Adresse IP invalide.";
      return e;
    },
    seed: [{ action: "CONNEXION", utilisateur_id: "u1", table_cible: "utilisateur", identifiant_cible: "1", adresse_ip: "10.0.0.5", details: '{"succes": true}' }],
  }),
];

const inventory: Entity[] = [
  ent({
    key: "inventory", label: "Inventory", singular: "une source d’inventaire", local: true,
    titleFields: ["name"], subtitleFields: ["kind"], badgeField: "state",
    fields: [
      text("name", "Source", { required: true }),
      pick("kind", "Type", ["Agent", "Import CSV", "Réseau (SNMP)"]),
      date("lastRun", "Dernière exécution"), num("found", "Éléments trouvés"),
      pick("state", "État", ["Terminé", "En cours", "Échec"], { required: true }),
    ],
  }),
];

export const sections: Section[] = [
  {
    slug: "assets",
    label: "Assets",
    groups: [
      { slug: "materiel", label: "Matériel", icon: "monitor", description: "Matériel individualisé par catégorie, et son historique d’affectation aux agents.", entities: materiel },
      { slug: "reseau", label: "Réseau et baies", icon: "network", description: "Équipements réseau, baies, câblage, cartes SIM : même table matériel, une catégorie par onglet.", entities: reseau },
      { slug: "consommables", label: "Consommables et stocks", icon: "printer", description: "Articles, stocks par service et mouvements d’entrée, sortie et transfert.", entities: consommables },
      { slug: "logiciels", label: "Logiciels", icon: "layers", description: "Logiciels installés et licences associées.", entities: logiciels },
      { slug: "global", label: "Global", icon: "globe", kind: "global", description: "Recherche transversale dans tout le matériel.", entities: [] },
    ],
  },
  {
    slug: "administration",
    label: "Administration",
    groups: [
      { slug: "organisation", label: "Organisation", icon: "network", description: "Directions, services et agents.", entities: organisation },
      { slug: "acces", label: "Accès", icon: "users", description: "Comptes utilisateurs, rôles et leurs permissions.", entities: acces },
      { slug: "dictionnaires", label: "Dictionnaires", icon: "layers", description: "Listes de référence utilisées par les formulaires.", entities: dictionnaires },
      { slug: "automatisation", label: "Automatisation", icon: "sliders", description: "Règles et formulaires personnalisés.", entities: automatisation },
      { slug: "suivi", label: "Suivi", icon: "clock", description: "File de notifications et journaux d’activité.", entities: suivi },
      { slug: "inventory", label: "Inventory", icon: "scan", description: "Sources et exécutions d’inventaire automatique.", entities: inventory },
    ],
  },
];

export const allEntities: Entity[] = sections.flatMap((s) => s.groups.flatMap((g) => g.entities));

export const assetEntities: { entity: Entity; groupSlug: string }[] = sections[0].groups.flatMap((g) =>
  g.entities.map((entity) => ({ entity, groupSlug: g.slug })),
);

/** categorie_id -> onglet qui l'affiche (pour les liens de la vue Global). */
export const categoryTab: Record<string, { groupSlug: string; key: string }> = {};
for (const { entity, groupSlug } of assetEntities) {
  if (entity.table === "materiel" && entity.where && !entity.where.negate) {
    categoryTab[entity.where.value] = { groupSlug, key: entity.key };
  }
}

/** Libellé lisible d'une ligne, quand une autre table la référence. */
export const tableLabel: Record<string, (r: Row) => string> = {
  direction: (r) => r.nom,
  service: (r) => r.nom,
  agent: (r) => `${r.nom} ${r.prenom}`.trim(),
  role: (r) => r.libelle,
  permission: (r) => r.libelle,
  utilisateur: (r) => r.nom_utilisateur,
  categorie_materiel: (r) => r.libelle,
  materiel: (r) => (r.code_inventaire ? `${r.designation} (${r.code_inventaire})` : r.designation),
  article_consommable: (r) => `${r.designation} (${r.reference})`,
  logiciel: (r) => (r.version ? `${r.nom} ${r.version}` : r.nom),
};

/* ---------- affichage ---------- */
export function matches(entity: Entity, row: Row): boolean {
  const w = entity.where;
  if (!w) return true;
  return w.negate ? row[w.field] !== w.value : row[w.field] === w.value;
}

export function rowsFor(entity: Entity, rows: Record<string, Row[]>): Row[] {
  return (rows[entity.table] ?? []).filter((r) => matches(entity, r));
}

export function showValue(f: Field, value: string | undefined, ctx: Ctx): string {
  const tr = ctx.t ?? ((s: string) => s);
  if (!value) return "";
  if (f.type === "ref" && f.ref) return ctx.label(f.ref, value) || tr("(supprimé)");
  if (f.type === "select") return tr(f.options?.find((o) => o.v === value)?.l ?? value);
  if (f.type === "multiref" && f.ref) {
    const table = f.ref;
    return value.split(",").filter((id) => id && ctx.find(table, id)).map((id) => ctx.label(table, id)).join(", ");
  }
  if (f.type === "password") return "";
  return value;
}

export function viewOf(
  entity: Entity, row: Row, ctx: Ctx,
): { title: string; sub: string; badge: string; tone: "ok" | "warn" | "bad" | "neutral" } {
  const raw: Ctx = { ...ctx, t: undefined }; // valeurs françaises d'origine, pour la couleur du badge
  const get = (names: string[] | undefined, c: Ctx) =>
    (names ?? [])
      .map((n) => {
        const f = entity.fields.find((x) => x.name === n);
        return f ? showValue(f, row[n], c) : (row[n] ?? "");
      })
      .filter(Boolean)
      .join(" · ");
  const tr = ctx.t ?? ((s: string) => s);
  const badgeRaw = entity.badgeFn ? entity.badgeFn(row, raw) : entity.badgeField ? get([entity.badgeField], raw) : "";
  return {
    title: get(entity.titleFields, ctx) || tr("Sans nom"),
    sub: get(entity.subtitleFields, ctx),
    badge: badgeRaw ? tr(badgeRaw) : "",
    tone: tone(badgeRaw),
  };
}

const OK = ["Attribué", "Oui", "Active", "Envoyée", "Terminé"];
const WARN = ["En maintenance", "En cours", "En attente", "Expirée", "Suspendue"];
const BAD = ["Réformé", "Non", "Échec", "Sous le seuil", "Résiliée"];

export function tone(value: string): "ok" | "warn" | "bad" | "neutral" {
  if (OK.includes(value)) return "ok";
  if (WARN.includes(value)) return "warn";
  if (BAD.includes(value)) return "bad";
  return "neutral";
}
