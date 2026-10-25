import { useI18n } from "../lib/i18n";

/** Tableau de bord : page vide pour l'instant. */
export default function Dashboard() {
  const { t } = useI18n();
  return (
    <header className="page-head">
      <h1>{t("Tableau de bord")}</h1>
    </header>
  );
}
