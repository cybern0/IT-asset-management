import { RepartitionView } from "../components/RepartitionView";
import { useI18n } from "../lib/i18n";
import { DashTabs } from "../components/dashboard/DashTabs";

/** Sous-route du tableau de bord : la même vue est aussi dans le menu « Circuit d’attribution ». */
export default function Repartition() {
  const { t } = useI18n();
  return (
    <>
      <DashTabs />
      <header className="page-head"><h1>{t("Répartition du matériel")}</h1></header>
      <RepartitionView />
    </>
  );
}
