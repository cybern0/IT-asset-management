import { API_URL } from "../lib/env";
import { useI18n } from "../lib/i18n";
import { useStore } from "../lib/store";

/** Bandeau d'etat du chargement des donnees (n'apparait que si besoin). */
export function ApiStatus() {
  const { status, reload } = useStore();
  const { t } = useI18n();

  if (status === "loading") {
    return <p className="api-loading" role="status">{t("Chargement des données…")}</p>;
  }
  if (status === "error") {
    return (
      <div className="api-banner" role="alert">
        <span>
          <strong>{t("Certaines données n’ont pas pu être chargées.")}</strong>{" "}
          {t("Vérifiez que l’API répond sur {url}.", { url: API_URL })}
        </span>
        <button type="button" className="btn ghost" onClick={() => void reload()}>{t("Réessayer")}</button>
      </div>
    );
  }
  return null;
}
