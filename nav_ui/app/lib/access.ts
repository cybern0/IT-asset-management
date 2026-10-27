// Droits d'acces : UN SEUL endroit a modifier pour changer qui voit / fait quoi.
// Les codes de role sont ceux de la table `role` (parc_4.sql). Cote serveur, les memes regles
// sont appliquees dans crud_api/routers/__init__.py : ce fichier ne sert qu'a adapter l'interface.

export type RoleCode = "ADMIN" | "GESTIONNAIRE" | "LECTURE";
export type Permission = "read" | "write" | "delete";
export type Area = "dashboard" | "assets" | "administration";

export const ROLE_LABEL: Record<RoleCode, string> = {
  ADMIN: "Administrateur",
  GESTIONNAIRE: "Gestionnaire",
  LECTURE: "Standard (lecture seule)",
};

/** Ce que chaque role a le droit de faire. */
export const PERMISSIONS: Record<RoleCode, Permission[]> = {
  ADMIN: ["read", "write", "delete"],
  GESTIONNAIRE: ["read", "write"],
  LECTURE: ["read"], // standard : lecture seule
};

/** Roles qui voient chaque zone du menu (et peuvent ouvrir ses pages). */
export const AREA_ROLES: Record<Area, RoleCode[]> = {
  dashboard: ["ADMIN", "GESTIONNAIRE", "LECTURE"],
  assets: ["ADMIN", "GESTIONNAIRE", "LECTURE"],
  administration: ["ADMIN"],
};

/** Tables que seul l'administrateur peut meme lire (comptes, droits, journal). */
const ADMIN_ONLY_TABLES = new Set(["utilisateur", "role", "permission", "journal_audit"]);

export const isRoleCode = (v: unknown): v is RoleCode => typeof v === "string" && v in PERMISSIONS;

export const canReadTable = (role: RoleCode, table: string): boolean =>
  role === "ADMIN" || !ADMIN_ONLY_TABLES.has(table);

/** Zone du menu correspondant a une URL (null pour /, /login...). */
export function areaOf(pathname: string): Area | null {
  const first = pathname.split("/")[1] ?? "";
  return (Object.keys(AREA_ROLES) as Area[]).find((a) => a === first) ?? null;
}
