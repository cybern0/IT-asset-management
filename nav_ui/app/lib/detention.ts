// Dossier d'attribution (fiche de detention) : types de l'API, etapes du processus, telechargements
import { api } from "./api";

export type Attribution = {
  id: number; reference: string; etape: number; etat: "EN_COURS" | "ATTRIBUEE" | "RENDUE" | "REFUSEE" | "ANNULEE";
  cree_le: string;
  categorie_id: number | null; categorie_demandee: string | null; besoin: string | null;
  canal: "MAIL" | "TICKET" | "FORMULAIRE"; reference_canal: string | null; demandeur: string | null;
  date_demande: string; valide_par: string | null; date_validation: string | null;
  date_generation: string | null;
  statut: "NON_SIGNEE" | "SIGNEE"; date_signature: string | null; mode_signature: "MANUSCRITE" | "ELECTRONIQUE" | null;
  signe_par: string | null; a_fichier_signe: boolean;
  date_remise: string | null; etat_constate: string | null; accessoires: string[];
  accessoires_autre: string | null; observations_remise: string | null;
  affectation_id: number | null; date_retour: string | null; etat_retour: string | null;
  observations: string | null; saisi_par: string | null; cloture: "REFUSEE" | "ANNULEE" | null; motif_cloture: string | null;
  materiel_id: number | null; materiel_code: string | null; materiel_designation: string | null;
  materiel_categorie: string | null; materiel_marque: string | null; materiel_modele: string | null;
  materiel_serie: string | null; materiel_caracteristiques: string | null; materiel_etat: string | null;
  materiel_statut: string | null; materiel_localisation: string | null; materiel_a_image: boolean;
  agent_id: number; agent_matricule: string; agent_nom: string; agent_prenom: string;
  agent_fonction: string | null; agent_email: string | null;
  service_nom: string | null; service_site: string | null; direction_nom: string | null;
};

/** Les 6 etapes du processus d'attribution (libelles = cles de traduction). */
export const ETAPES: { n: number; title: string; desc: string }[] = [
  { n: 1, title: "Demande d’équipement",
    desc: "Le collaborateur ou son responsable hiérarchique formule une demande (mail, ticket ou formulaire). La demande est validée par le manager." },
  { n: 2, title: "Sélection de l’équipement",
    desc: "Le service informatique sélectionne un équipement disponible en stock, correspondant au besoin (type, configuration)." },
  { n: 3, title: "Génération de la fiche de détention",
    desc: "La fiche de détention est générée automatiquement à partir des données de l’équipement et du détenteur." },
  { n: 4, title: "Signature de la fiche",
    desc: "Le détenteur et le responsable informatique (ou hiérarchique) signent la fiche. La signature peut être manuscrite ou électronique." },
  { n: 5, title: "Remise physique du matériel",
    desc: "L’équipement et ses accessoires sont remis au détenteur. Un contrôle visuel de l’état est effectué." },
  { n: 6, title: "Mise à jour du statut",
    desc: "Le statut de l’équipement passe à « Attribué » dans la base de gestion. La fiche signée est archivée (PDF + papier si besoin)." },
];

export const ETAT_LABEL: Record<Attribution["etat"], string> = {
  EN_COURS: "En cours", ATTRIBUEE: "Attribué", RENDUE: "Rendu", REFUSEE: "Refusée", ANNULEE: "Annulée",
};
export const CANAL_LABEL: Record<Attribution["canal"], string> = { MAIL: "Mail", TICKET: "Ticket", FORMULAIRE: "Formulaire" };
export const ACCESSOIRES = ["Chargeur", "Sacoche", "Docking", "Souris", "Clavier"] as const;

export const ficheLabel = (f: Pick<Attribution, "statut">) => (f.statut === "SIGNEE" ? "Signée" : "Non signée");

export const fmtDate = (iso: string | null | undefined): string =>
  iso ? iso.slice(0, 10).split("-").reverse().join("/") : "";

export const agentName = (f: Pick<Attribution, "agent_nom" | "agent_prenom">) => `${f.agent_nom} ${f.agent_prenom}`.trim();

/** Enregistre un fichier recu de l'API sous le nom donne. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export const downloadPdf = async (f: Pick<Attribution, "id" | "reference">) =>
  saveBlob(await api.blob(`/attributions/${f.id}/pdf`), `${f.reference}.pdf`);

/** Ouvre le scan de la fiche signee dans un nouvel onglet (image ou PDF). */
export async function openScan(f: Pick<Attribution, "id">): Promise<void> {
  const blob = await api.blob(`/attributions/${f.id}/fichier-signe`);
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
