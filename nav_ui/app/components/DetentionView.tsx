import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import {
  agentName, CANAL_LABEL, downloadPdf, ETAT_LABEL, ETAT_MATERIEL_LABEL, ficheLabel, fmtDate, MODE_LABEL,
  PROVENANCE_LABEL, suivi, type Attribution as Detention,
} from "../lib/detention";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";
import { Lightbox } from "./Lightbox";
import { Modal } from "./Modal";

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

/** Liste croisee materiel x agent detenteur, avec filtres, detail et export PDF. */
export function DetentionView() {
  const { t } = useI18n();
  const [items, setItems] = useState<Detention[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [qAgent, setQAgent] = useState("");
  const [qMat, setQMat] = useState("");
  const [fiche, setFiche] = useState("");
  const [etat, setEtat] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setItems(await api.get<Detention[]>("/attributions?limit=5000")); }
    catch (e) { setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue.")); }
    finally { setLoading(false); }
  }, [t]);

  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => {
    const a = norm(qAgent.trim());
    const m = norm(qMat.trim());
    return items.filter((d) => {
      if (d.materiel_id === null || d.cloture) return false;
      if (a && !norm(`${d.agent_nom} ${d.agent_prenom} ${d.agent_prenom} ${d.agent_nom} ${d.agent_matricule}`).includes(a)) return false;
      if (m && !norm(`${d.materiel_designation} ${d.materiel_code} ${d.materiel_marque ?? ""} ${d.materiel_modele ?? ""} ${d.materiel_serie ?? ""}`).includes(m)) return false;
      if (fiche && d.statut !== fiche) return false;
      if (etat && d.etat !== etat) return false;
      return true;
    });
  }, [items, qAgent, qMat, fiche, etat]);

  const current = items.find((d) => d.id === openId) ?? null;

  return (
    <section className="pane global">
      <div className="filters">
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={qAgent} onChange={(e) => setQAgent(e.target.value)}
            placeholder={t("Nom de l’agent")} aria-label={t("Filtrer par nom d’agent")} />
        </label>
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={qMat} onChange={(e) => setQMat(e.target.value)}
            placeholder={t("Nom du matériel")} aria-label={t("Filtrer par nom de matériel")} />
        </label>
        <select value={etat} onChange={(e) => setEtat(e.target.value)} aria-label={t("Détention")}>
          <option value="">{t("Toutes les détentions")}</option>
          <option value="ATTRIBUEE">{t("Attribué")}</option>
          <option value="EN_COURS">{t("En cours")}</option>
          <option value="RENDUE">{t("Rendu")}</option>
        </select>
        <select value={fiche} onChange={(e) => setFiche(e.target.value)} aria-label={t("Fiche de détention")}>
          <option value="">{t("Toutes les fiches")}</option>
          <option value="SIGNEE">{t("Signée")}</option>
          <option value="NON_SIGNEE">{t("Non signée")}</option>
        </select>
        <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>{t("Actualiser")}</button>
      </div>

      <div className="pane-body">
        {error ? (
          <p className="error pad" role="alert">{error}</p>
        ) : loading && items.length === 0 ? (
          <p className="empty">{t("Chargement…")}</p>
        ) : visible.length === 0 ? (
          <p className="empty">{items.length === 0 ? t("Aucune affectation pour l’instant.") : t("Aucune détention ne correspond.")}</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("Matériel")}</th><th>{t("Agent détenteur")}</th><th>{t("Service")}</th>
                <th>{t("Remise")}</th><th>{t("Détention")}</th><th>{t("Fiche")}</th><th />
              </tr>
            </thead>
            <tbody>
              {visible.map((d) => (
                <tr key={d.id}>
                  <td><strong>{d.materiel_designation}</strong><br /><span className="hint">{d.materiel_code}</span></td>
                  <td>{agentName(d)}<br /><span className="hint">{d.agent_matricule}</span></td>
                  <td>{d.service_nom ?? "—"}</td>
                  <td>{fmtDate(d.date_remise) || "—"}</td>
                  <td><span className="badge" data-tone={d.etat === "EN_COURS" ? "warn" : tone(ETAT_LABEL[d.etat])}>{d.etat === "EN_COURS" ? `${t("Étape")} ${d.etape}/6` : t(ETAT_LABEL[d.etat])}</span></td>
                  <td><span className="badge" data-tone={tone(ficheLabel(d))}>{t(ficheLabel(d))}</span></td>
                  <td><button type="button" className="btn ghost" onClick={() => setOpenId(d.id)}>{t("Voir")}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {current && (
        <Modal title={`${t("Fiche de détention")} ${current.reference}`} wide onClose={() => setOpenId(null)}>
          <DetentionDetail d={current} />
        </Modal>
      )}
    </section>
  );
}

function DetentionDetail({ d }: { d: Detention }) {
  const { t } = useI18n();
  const [src, setSrc] = useState<string | null>(null);
  const [zoom, setZoom] = useState(false);

  useEffect(() => {
    if (!d.materiel_a_image) { setSrc(null); return; }
    let url: string | null = null;
    let cancelled = false;
    api.blob(`/materiels/${d.materiel_id}/image`)
      .then((b) => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } })
      .catch(() => { /* l'image est facultative */ });
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [d.materiel_id, d.materiel_a_image]);

  const row = (label: string, value: string | null | undefined) => (
    <>
      <dt>{t(label)}</dt>
      <dd>{value || "—"}</dd>
    </>
  );
  const lab = (map: Record<string, string>, key: string | null) => (key ? t(map[key] ?? key) : "");
  const origine = [lab(PROVENANCE_LABEL, d.materiel_provenance), d.materiel_provenance_detail].filter(Boolean).join(" – ");
  const canal = [t(CANAL_LABEL[d.canal]), d.reference_canal].filter(Boolean).join(" – ");
  const accessoires = [...d.accessoires.map((a) => t(a)), d.accessoires_autre].filter(Boolean).join(", ");

  return (
    <>
      <div className="fiche-row">
        <span className="badge" data-tone={tone(ficheLabel(d))}>{t(ficheLabel(d))}</span>
        {d.statut === "SIGNEE" && <span className="hint">{t("le {d}", { d: fmtDate(d.date_signature) })}</span>}
        <span className="badge" data-tone={d.etat === "EN_COURS" ? "warn" : tone(ETAT_LABEL[d.etat])}>
          {d.etat === "EN_COURS" ? `${t("Étape")} ${d.etape}/6` : t(ETAT_LABEL[d.etat])}
        </span>
        <button type="button" className="btn primary" onClick={() => void downloadPdf(d)}>{t("Exporter en PDF")}</button>
      </div>

      <section className="suivi" aria-label={t("Suivi du dossier")}>
        <h3>{t("Suivi du dossier")}</h3>
        <ol className="mini-steps">
          {suivi(d).map((s) => (
            <li key={s.n} data-done={s.done}>
              <span className="dot" aria-hidden="true">{s.done ? "✓" : s.n}</span>
              <span className="mini-title">{t(s.title)}</span>
              <span className="hint">{s.done ? fmtDate(s.date) : d.cloture ? t("Interrompu") : t("À faire")}</span>
            </li>
          ))}
        </ol>
        {d.cloture && <p className="error">{t(d.cloture === "REFUSEE" ? "Demande refusée" : "Dossier annulé")}{d.motif_cloture ? ` : ${d.motif_cloture}` : ""}</p>}
      </section>

      <div className="detail-grid">
        <section>
          <h3>{t("Matériel")}</h3>
          {src && (
            <button type="button" className="thumb-btn" onClick={() => setZoom(true)} title={t("Cliquer pour agrandir")} aria-label={t("Cliquer pour agrandir")}>
              <img className="thumb" src={src} alt={d.materiel_designation ?? ""} />
            </button>
          )}
          {zoom && src && (
            <Lightbox src={src} alt={d.materiel_designation ?? ""} newTabHref={`/image/${d.materiel_id}`} onClose={() => setZoom(false)} />
          )}
          <dl>
            {row("Désignation", d.materiel_designation)}
            {row("Code d’inventaire", d.materiel_code)}
            {row("Catégorie", d.materiel_categorie)}
            {row("Marque", d.materiel_marque)}
            {row("Modèle", d.materiel_modele)}
            {row("N° de série", d.materiel_serie)}
            {row("Caractéristiques", d.materiel_caracteristiques)}
            {row("Origine du matériel", origine)}
            {row("Date d’acquisition", fmtDate(d.materiel_date_acquisition))}
            {row("Localisation", d.materiel_localisation)}
          </dl>
          <h3>{t("Demande")}</h3>
          <dl>
            {row("Date de la demande", fmtDate(d.date_demande))}
            {row("Canal de la demande", canal)}
            {row("Demandeur", d.demandeur)}
            {row("Type d’équipement demandé", d.categorie_demandee)}
            {row("Besoin exprimé", d.besoin)}
            {row("Validée par", d.valide_par)}
            {row("Date de validation", fmtDate(d.date_validation))}
          </dl>
        </section>
        <section>
          <h3>{t("Agent détenteur")}</h3>
          <dl>
            {row("Nom et prénom", agentName(d))}
            {row("Matricule", d.agent_matricule)}
            {row("Fonction", d.agent_fonction)}
            {row("Service", d.service_nom)}
            {row("Direction", d.direction_nom)}
            {row("Site", d.service_site)}
            {row("Email", d.agent_email)}
            {row("Téléphone", d.agent_telephone)}
            {row("WhatsApp", d.agent_whatsapp)}
            {row("Adresse exacte du domicile", d.agent_adresse_domicile_exacte)}
          </dl>
          <h3>{t("Signature et remise")}</h3>
          <dl>
            {row("Date de signature", fmtDate(d.date_signature))}
            {row("Mode de signature", lab(MODE_LABEL, d.mode_signature))}
            {row("Signée par", d.signe_par)}
            {row("Date de remise", fmtDate(d.date_remise))}
            {row("État constaté à la remise", lab(ETAT_MATERIEL_LABEL, d.etat_constate))}
            {row("Accessoires remis", accessoires)}
            {row("Observations à la remise", d.observations_remise)}
            {row("Enregistrée par", d.saisi_par)}
          </dl>
          <h3>{t("Restitution")}</h3>
          <dl>
            {row("Date de retour", fmtDate(d.date_retour))}
            {row("État au retour", lab(ETAT_MATERIEL_LABEL, d.etat_retour))}
            {row("Observations", d.observations)}
          </dl>
        </section>
      </div>
    </>
  );
}
