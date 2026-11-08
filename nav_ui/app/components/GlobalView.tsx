import { NavLink } from "react-router";
import { DetentionView } from "./DetentionView";
import { TracabiliteView } from "./TracabiliteView";
import { useI18n } from "../lib/i18n";

/** Racine Global : deux rubriques. « Matériel » = liste de tout le materiel + parcours du materiel choisi
 *  (ancienne Tracabilite) ; « Detentions » = liste croisee materiel x agent detenteur avec fiches. */
export function GlobalView({ tab }: { tab?: string }) {
  const { t } = useI18n();
  return (
    <>
      <nav className="tabs" aria-label={t("Global")}>
        <NavLink to="/global" end className="tab">{t("Matériel")}</NavLink>
        <NavLink to="/global/detentions" className="tab">{t("Détentions")}</NavLink>
      </nav>
      {tab === "detentions" ? <DetentionView /> : <TracabiliteView />}
    </>
  );
}
