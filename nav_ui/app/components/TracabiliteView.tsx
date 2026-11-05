// Menu « Traçabilité des matériels » : page volontairement vide pour l'instant (le contenu viendra dans une prochaine étape).
import { useI18n } from "../lib/i18n";

export function TracabiliteView() {
  const { t } = useI18n();
  return (
    <div className="dash">
      <div className="dash-body">
        <p className="empty">{t("Cette rubrique sera complétée prochainement.")}</p>
      </div>
    </div>
  );
}
