import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../lib/api";
import { downloadPdf, ETAT_LABEL, ficheLabel, fmtDate, type Attribution } from "../lib/detention";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";

/** Dossier d'attribution lie a une affectation (lecture + export PDF) ; le circuit complet est dans Attributions. */
export function FicheBar({ affectationId, version }: { affectationId: string; version: string }) {
  const { t } = useI18n();
  const [fiche, setFiche] = useState<Attribution | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setFiche(null);
    setError("");
    api.get<Attribution>(`/affectations/${affectationId}/attribution`)
      .then((f) => { if (!cancelled) setFiche(f); })
      .catch((e) => { if (!cancelled) setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); });
    return () => { cancelled = true; };
  }, [affectationId, version, t]);

  const run = async (action: () => Promise<void>) => {
    setError("");
    try { await action(); } catch (e) { setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); }
  };

  return (
    <section className="fiche-card" aria-label={t("Fiche de détention")}>
      <h3>{t("Fiche de détention")}</h3>
      {error ? <p className="error" role="alert">{error}</p>
        : !fiche ? <p className="hint">{t("Chargement…")}</p>
        : (
          <div className="fiche">
            <div className="fiche-row">
              <span className="fiche-ref">{fiche.reference}</span>
              <span className="badge" data-tone={tone(ficheLabel(fiche))}>{t(ficheLabel(fiche))}</span>
              <span className="badge" data-tone={tone(ETAT_LABEL[fiche.etat])}>{t(ETAT_LABEL[fiche.etat])}</span>
              {fiche.statut === "SIGNEE" && <span className="hint">{t("le {d}", { d: fmtDate(fiche.date_signature) })}</span>}
            </div>
            <div className="fiche-row">
              <button type="button" className="btn primary" onClick={() => void run(() => downloadPdf(fiche))}>{t("Exporter en PDF")}</button>
              <Link className="btn ghost" to="/assets/materiel/attributions">{t("Ouvrir dans Attributions")}</Link>
            </div>
          </div>
        )}
    </section>
  );
}
