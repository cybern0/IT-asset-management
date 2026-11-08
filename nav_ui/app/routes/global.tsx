import { Navigate, useParams } from "react-router";
import { GlobalView } from "../components/GlobalView";
import { useI18n } from "../lib/i18n";
import NotFound from "./notfound";

/** Racine « Global » : le materiel et son parcours, puis la liste croisee materiel x agent detenteur. */
export default function Global() {
  const { tab } = useParams();
  const { t } = useI18n();
  if (tab === "tracabilite") return <Navigate to="/global" replace />; // ancien onglet : fusionne dans « Matériel »
  if (tab && tab !== "detentions") return <NotFound />;
  return (
    <>
      <header className="page-head">
        <h1>{t("Global")}</h1>
        <p className="lede">{t("Tout le matériel avec son parcours (acquisition, demandes, signatures, remises, retours) et la liste croisée matériel × agent détenteur.")}</p>
      </header>
      <GlobalView tab={tab} />
    </>
  );
}
