// Anciennes adresses (avant la fusion en deux racines : Tableau de bord et Global) -> nouvelles adresses.
const MAP: Record<string, string> = {
  "/assets/global": "/global",
  "/assets/global/detentions": "/global/detentions",
  "/assets/global/tracabilite": "/global",
  "/circuit/tracabilite": "/global",
  "/circuit/tracabilite/tracabilite": "/global",
  "/circuit/repartition": "/dashboard/repartition",
  "/circuit/repartition/repartition": "/dashboard/repartition",
};

export const legacyTarget = (pathname: string): string | null => MAP[pathname.replace(/\/+$/, "")] ?? null;
