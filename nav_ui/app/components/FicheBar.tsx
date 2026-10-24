import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Detention } from "../lib/detention";
import { useI18n } from "../lib/i18n";
import { FicheActions } from "./FicheActions";

/** Fiche de detention d'une affectation (affichee dans le formulaire de l'onglet Affectations). */
export function FicheBar({ affectationId, version }: { affectationId: string; version: string }) {
  const { t } = useI18n();
  const [fiche, setFiche] = useState<Detention | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setFiche(null);
    setError("");
    api.get<Detention>(`/affectations/${affectationId}/fiche`)
      .then((f) => { if (!cancelled) setFiche(f); })
      .catch((e) => { if (!cancelled) setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); });
    return () => { cancelled = true; };
  }, [affectationId, version, t]);

  return (
    <section className="fiche-card" aria-label={t("Fiche de détention")}>
      <h3>{t("Fiche de détention")}</h3>
      {error ? <p className="error" role="alert">{error}</p>
        : fiche ? <FicheActions fiche={fiche} onChange={setFiche} />
        : <p className="hint">{t("Chargement…")}</p>}
    </section>
  );
}
