// Menu dynamique : les onglets (sous-menus) des categories sont generes depuis categorie_materiel.category_menu.
// Creer ou modifier une categorie suffit : son onglet apparait (ou change de menu) sans toucher au code.
import { useMemo } from "react";
import { categoryEntities, categoryTabOf, type Entity, type Group, type Section } from "./schema";
import { useStore } from "./store";

export function useMenu() {
  const { rows, status } = useStore();
  const categories = rows.categorie_materiel;

  return useMemo(() => {
    /** Onglets d'un menu : onglets fixes + onglets generes depuis les categories du menu. */
    const entitiesOf = (g: Group): Entity[] => {
      const generated = categoryEntities(categories, g);
      return g.categoriesFirst ? [...generated, ...g.entities] : [...g.entities, ...generated];
    };
    return {
      /** false tant que les categories ne sont pas chargees (evite un menu qui clignote). */
      ready: status !== "loading",
      entitiesOf,
      groupsOf: (s: Section): Group[] => s.groups.filter((g) => g.kind === "global" || entitiesOf(g).length > 0),
      /** Onglet qui affiche une categorie (liens de la vue Global), null si elle n'a pas de menu. */
      tabOf: (code: string) => categoryTabOf(code, categories),
    };
  }, [categories, status]);
}
