import { NavLink } from "react-router";
import { useAuth } from "../../lib/auth";
import { useI18n } from "../../lib/i18n";

/** Sous-routes du tableau de bord : vue d'ensemble (depositaire comptable) et repartition par services (tous). */
export function DashTabs() {
  const { t } = useI18n();
  const { has } = useAuth();
  if (!(has("dashboard.voir") && has("dashboard.repartition"))) return null;
  return (
    <nav className="dash-tabs" aria-label={t("Tableau de bord")}>
      <NavLink to="/dashboard" end>{t("Vue d’ensemble")}</NavLink>
      <NavLink to="/dashboard/repartition">{t("Répartition")}</NavLink>
    </nav>
  );
}
