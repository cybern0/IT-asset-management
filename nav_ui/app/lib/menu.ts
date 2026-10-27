// Menu dynamique : filtre les onglets (routes) du dictionnaire selon categorie_materiel.afficher_menu
import { useMemo } from "react";
import { isCategoryShown, isEntityVisible, type Entity, type Group, type Section } from "./schema";
import { useStore } from "./store";

export function useMenu() {
  const { rows, status } = useStore();
  const list = rows.categorie_materiel;

  return useMemo(() => {
    // API en erreur et aucune categorie chargee : on n'efface pas tout le menu
    const categories = status === "error" && list.length === 0 ? null : list;
    const entitiesOf = (g: Group): Entity[] => g.entities.filter((e) => isEntityVisible(e, categories));
    return {
      /** false tant que les categories ne sont pas chargees (evite un menu qui clignote). */
      ready: status !== "loading",
      entitiesOf,
      groupsOf: (s: Section): Group[] => s.groups.filter((g) => g.kind === "global" || entitiesOf(g).length > 0),
      categoryShown: (code: string) => isCategoryShown(code, categories),
    };
  }, [list, status]);
}
