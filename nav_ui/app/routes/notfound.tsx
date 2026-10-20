import { Link } from "react-router";
import { useI18n } from "../lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="pane">
      <div className="pane-body">
        <p className="empty">
          {t("Cette page n’existe pas.")} <Link to="/assets/materiel/computers">{t("Retour au matériel")}</Link>
        </p>
      </div>
    </div>
  );
}
