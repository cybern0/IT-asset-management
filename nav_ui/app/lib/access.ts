// Droits d'acces (RBAC modulaire) : l'API renvoie la liste des PERMISSIONS du role (/auth/login, /auth/me, table
// role_permission de parc_10.sql). L'interface se contente de les lire : changer les droits d'un role = modifier
// la base, pas ce fichier. Cote serveur, les memes permissions sont verifiees route par route.

/** Un seul role existe : ADMIN (parc_13.sql, parc_14.sql). */
export type RoleCode = "ADMIN";
/** Raccourcis historiques des composants (CrudPanel...) : lecture / ecriture / suppression du parc. */
export type Permission = "read" | "write" | "delete";
export type Area = "dashboard" | "global" | "circuit" | "assets" | "administration";

export const ROLE_LABEL: Record<RoleCode, string> = {
  ADMIN: "Dépositaire comptable (administrateur)",
};

export const LEGACY_PERMISSION: Record<Permission, string> = {
  read: "parc.lire", write: "parc.ecrire", delete: "parc.supprimer",
};

/** Permissions dont UNE SEULE suffit pour voir chaque zone du menu. */
export const AREA_PERMISSIONS: Record<Area, string[]> = {
  dashboard: ["dashboard.voir", "dashboard.repartition"],
  circuit: ["demande.creer", "demande.voir_propres", "demande.voir_service", "demande.voir_toutes"],
  global: ["parc.lire"],
  assets: ["parc.lire"],
  administration: ["acces.gerer"],
};

const ADMIN_ONLY_TABLES = new Set(["utilisateur"]);

export const isRoleCode = (v: unknown): v is RoleCode => v === "ADMIN";

export const canReadTable = (permissions: readonly string[], table: string): boolean =>
  ADMIN_ONLY_TABLES.has(table) ? permissions.includes("acces.gerer") : permissions.includes("parc.lire");

/** Zone du menu correspondant a une URL (null pour /, /login...). */
export function areaOf(pathname: string): Area | null {
  const first = pathname.split("/")[1] ?? "";
  return (Object.keys(AREA_PERMISSIONS) as Area[]).find((a) => a === first) ?? null;
}
