import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { downloadPdf, ficheLabel, fmtDate, openScan, type Detention } from "../lib/detention";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";

const today = () => new Date().toISOString().slice(0, 10);

/** Statut de la fiche + export PDF + signature (date et scan facultatif). */
export function FicheActions({ fiche, onChange }: { fiche: Detention; onChange: (f: Detention) => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const writable = can("write");
  const [signing, setSigning] = useState(false);
  const [date, setDate] = useState(today());
  const [scan, setScan] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try { await action(); }
    catch (e) { setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue.")); }
    finally { setBusy(false); }
  }

  const sign = () => run(async () => {
    const form = new FormData();
    form.append("date_signature", date);
    if (scan) form.append("fichier", scan);
    onChange(await api.upload<Detention>(`/fiches-detention/${fiche.id}/signer`, form));
    setSigning(false);
    setScan(null);
  });

  const unsign = () => run(async () => {
    onChange(await api.post<Detention>(`/fiches-detention/${fiche.id}/annuler-signature`));
  });

  const signed = fiche.statut === "SIGNEE";

  return (
    <div className="fiche">
      <div className="fiche-row">
        <span className="fiche-ref">{fiche.reference}</span>
        <span className="badge" data-tone={tone(ficheLabel(fiche))}>{t(ficheLabel(fiche))}</span>
        {signed && <span className="hint">{t("le {d}", { d: fmtDate(fiche.date_signature) })}</span>}
      </div>
      <div className="fiche-row">
        <button type="button" className="btn primary" disabled={busy} onClick={() => void run(() => downloadPdf(fiche))}>
          {t("Exporter en PDF")}
        </button>
        {writable && !signing && (
          <button type="button" className="btn ghost" disabled={busy} onClick={() => setSigning(true)}>
            {signed ? t("Modifier la signature") : t("Marquer comme signée")}
          </button>
        )}
        {signed && fiche.a_fichier_signe && (
          <button type="button" className="btn ghost" disabled={busy} onClick={() => void run(() => openScan(fiche))}>
            {t("Voir le scan signé")}
          </button>
        )}
        {writable && signed && !signing && (
          <button type="button" className="btn ghost" disabled={busy} onClick={() => void unsign()}>
            {t("Annuler la signature")}
          </button>
        )}
      </div>
      {signing && (
        <div className="fiche-sign">
          <label>
            {t("Date de signature")}
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>
            {t("Scan du document signé (facultatif)")}
            <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp"
              onChange={(e) => setScan(e.target.files?.[0] ?? null)} />
          </label>
          <div className="fiche-row">
            <button type="button" className="btn primary" disabled={busy || !date} onClick={() => void sign()}>
              {t("Enregistrer la signature")}
            </button>
            <button type="button" className="btn ghost" disabled={busy} onClick={() => setSigning(false)}>
              {t("Annuler")}
            </button>
          </div>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
