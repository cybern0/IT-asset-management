import { Link } from "react-router";
import { useI18n } from "../lib/i18n";

/** Affichee quand le role de l'utilisateur ne donne pas acces a la page demandee. */
export function Forbidden() {
  const { t } = useI18n();
  return (
    <div className="pane">
      <div className="pane-body">
        <h1>{t("Accès refusé")}</h1>
        <p className="empty">
          {t("Votre rôle ne permet pas d’ouvrir cette page.")} <Link to="/dashboard">{t("Retour au tableau de bord")}</Link>
        </p>
      </div>
    </div>
  );
}
