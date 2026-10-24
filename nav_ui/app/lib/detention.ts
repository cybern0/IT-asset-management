// Fiches de detention : types de l'API et petits utilitaires de telechargement
import { api } from "./api";

export type Detention = {
  id: number; reference: string; statut: "NON_SIGNEE" | "SIGNEE";
  date_signature: string | null; a_fichier_signe: boolean;
  affectation_id: number; date_remise: string; date_retour: string | null; en_cours: boolean;
  etat_remise: string | null; etat_retour: string | null; observations: string | null; saisi_par: string | null;
  materiel_id: number; materiel_code: string; materiel_designation: string; materiel_categorie: string;
  materiel_marque: string | null; materiel_modele: string | null; materiel_serie: string | null;
  materiel_caracteristiques: string | null; materiel_etat: string; materiel_statut: string;
  materiel_localisation: string | null; materiel_a_image: boolean;
  agent_id: number; agent_matricule: string; agent_nom: string; agent_prenom: string;
  agent_fonction: string | null; agent_email: string | null;
  service_nom: string | null; service_site: string | null; direction_nom: string | null;
};

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

export const downloadPdf = async (f: Pick<Detention, "id" | "reference">) =>
  saveBlob(await api.blob(`/fiches-detention/${f.id}/pdf`), `${f.reference}.pdf`);

/** Ouvre le scan de la fiche signee dans un nouvel onglet (image ou PDF). */
export async function openScan(f: Pick<Detention, "id">): Promise<void> {
  const blob = await api.blob(`/fiches-detention/${f.id}/fichier-signe`);
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const ficheLabel = (f: Pick<Detention, "statut">) => (f.statut === "SIGNEE" ? "Signée" : "Non signée");

export const fmtDate = (iso: string | null | undefined): string =>
  iso ? iso.slice(0, 10).split("-").reverse().join("/") : "";
