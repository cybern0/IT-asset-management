import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import {
  agentName, CANAL_LABEL, downloadPdf, ETAT_LABEL, type Attribution,
} from "../lib/detention";
import { Icon } from "../lib/icons";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";
import { useStore } from "../lib/store";
import { NewTransfer } from "./AffectationTransfer";
import { AttributionSteps } from "./AttributionSteps";

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const today = () => new Date().toISOString().slice(0, 10);

export type Mode = "ATTRIBUTION" | "AFFECTATION";

/** Fiche generee (equipement choisi), pas encore signee, dossier non clos. */
const needsSignature = (d: Attribution) => d.cloture === null && d.materiel_id !== null && d.statut !== "SIGNEE";

/** Liste + detail d'une rubrique du circuit. Meme mise en page pour les deux :
 *  - ATTRIBUTION : un materiel sans detenteur est donne a un agent (bouton + : nouvelle demande d'equipement) ;
 *  - AFFECTATION : un materiel deja detenu est retire a son detenteur et donne a un autre agent (bouton + : transfert).
 *  Chaque dossier garde son circuit en 6 etapes puis le retour du materiel. */
export function AttributionsView({ mode }: { mode: Mode }) {
  const { t } = useI18n();
  const { can, has } = useAuth();
  const { rows } = useStore();
  const isAff = mode === "AFFECTATION";
  const title = isAff ? t("Affectations") : t("Attributions");
  const canCreate = isAff ? has("affectation.transferer") : can("write");
  const addLabel = isAff ? t("Nouvelle affectation") : t("Nouvelle demande d’équipement");

  const [items, setItems] = useState<Attribution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [etat, setEtat] = useState("");
  const [sig, setSig] = useState("");
  const [selected, setSelected] = useState<number | "new" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setItems(await api.get<Attribution[]>("/attributions?limit=5000")); }
    catch (e) { setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue.")); }
    finally { setLoading(false); }
  }, [t]);

  useEffect(() => { void load(); }, [load]);
  // changer de rubrique repart d'une liste propre
  useEffect(() => { setSelected(null); setQuery(""); setEtat(""); setSig(""); }, [mode]);

  const agentById = useMemo(() => new Map((rows.agent ?? []).map((a) => [Number(a.id), `${a.nom} ${a.prenom}`.trim()])), [rows.agent]);
  const ancien = (d: Attribution) => (d.ancien_agent_id ? agentById.get(d.ancien_agent_id) ?? "" : "");

  const ofMode = useMemo(() => items.filter((d) => (d.type_demande ?? "ATTRIBUTION") === mode), [items, mode]);

  const visible = useMemo(() => {
    const q = norm(query.trim());
    return ofMode.filter((d) => {
      if (etat && d.etat !== etat) return false;
      if (sig === "A_SIGNER" && !needsSignature(d)) return false;
      if (sig === "SIGNEE" && d.statut !== "SIGNEE") return false;
      if (!q) return true;
      return norm(`${d.reference} ${agentName(d)} ${d.agent_matricule} ${ancien(d)} ${d.materiel_designation ?? ""} ${d.materiel_code ?? ""}`).includes(q);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ofMode, query, etat, sig, agentById]);

  const current = typeof selected === "number" ? ofMode.find((d) => d.id === selected) ?? null : null;
  const replace = (f: Attribution) => setItems((list) => list.map((d) => (d.id === f.id ? f : d)));
  const filtered = Boolean(query || etat || sig);

  return (
    <div className="crud">
      <section className="pane" aria-label={t("Liste : {x}", { x: title })}>
        <div className="pane-head">
          <h2>{title} <span className="count">{visible.length}</span></h2>
          {canCreate && (
            <button type="button" className="add-btn" onClick={() => setSelected("new")} aria-label={addLabel} title={addLabel}>
              <Icon name="plus" />
            </button>
          )}
        </div>
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Filtrer la liste")} aria-label={t("Filtrer la liste")} />
        </label>
        <div className="filters tight">
          <select value={etat} onChange={(e) => setEtat(e.target.value)} aria-label={t("État du dossier")}>
            <option value="">{t("Tous les dossiers")}</option>
            {Object.entries(ETAT_LABEL).map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
          </select>
          <select value={sig} onChange={(e) => setSig(e.target.value)} aria-label={t("État de la fiche")}>
            <option value="">{t("Toutes les fiches")}</option>
            <option value="A_SIGNER">{t("À signer")}</option>
            <option value="SIGNEE">{t("Signée")}</option>
          </select>
          <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>{t("Actualiser")}</button>
        </div>
        <div className="pane-body">
          {error ? <p className="error pad" role="alert">{error}</p>
            : loading && items.length === 0 ? <p className="empty">{t("Chargement…")}</p>
            : visible.length === 0 ? (
              <p className="empty">
                {filtered && ofMode.length > 0 ? t("Aucun résultat pour ce filtre.")
                  : isAff ? t("Aucune affectation pour l’instant. Utilisez le bouton + pour affecter un matériel déjà détenu à un autre agent.")
                  : t("Aucune attribution pour l’instant. Utilisez le bouton + pour enregistrer une demande.")}
              </p>
            ) : (
              <ul className="items">
                {visible.map((d) => {
                  const label = d.etat === "EN_COURS" ? `${t("Étape")} ${d.etape}/6` : t(ETAT_LABEL[d.etat]);
                  const from = isAff ? ancien(d) : "";
                  return (
                    <li key={d.id}>
                      <button type="button" className="item" aria-current={selected === d.id} onClick={() => setSelected(d.id)}>
                        <span className="item-main">
                          <span className="item-title">{agentName(d)}</span>
                          <span className="item-sub">
                            {d.reference} · {d.materiel_designation ?? d.categorie_demandee ?? t("Équipement à choisir")}
                            {from && ` · ${t("de")} ${from}`}
                          </span>
                        </span>
                        <span className="badges">
                          {needsSignature(d) && <span className="badge" data-tone="warn">{t("À signer")}</span>}
                          <span className="badge" data-tone={d.etat === "EN_COURS" ? "warn" : tone(ETAT_LABEL[d.etat])}>{label}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
        </div>
      </section>

      <section className="pane" aria-label={t("Détail")}>
        {selected === "new" ? (
          isAff ? (
            <NewTransfer
              onCancel={() => setSelected(null)}
              onDone={() => { setSelected(null); void load(); }}
            />
          ) : (
            <NewRequest
              onCancel={() => setSelected(null)}
              onCreated={(f) => { setItems((l) => [f, ...l]); setSelected(f.id); }}
            />
          )
        ) : current ? (
          <div className="form" key={current.id}>
            <div className="pane-head">
              <h2>{current.reference}</h2>
              <span className="head-actions">
                {current.materiel_id !== null && (
                  <button type="button" className="btn ghost" onClick={() => void downloadPdf(current).catch((e) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")))}>
                    {t("Exporter en PDF")}
                  </button>
                )}
                <button type="button" className="btn ghost" onClick={() => setSelected(null)}>{t("Fermer")}</button>
              </span>
            </div>
            <div className="pane-body">
              <AttributionSteps d={current} onChange={replace} />
            </div>
          </div>
        ) : (
          <div className="pane-body">
            <p className="empty">
              {isAff ? t("Sélectionnez une affectation dans la liste, ou cliquez sur + pour affecter un matériel à un autre agent.")
                : t("Sélectionnez un dossier dans la liste, ou cliquez sur + pour enregistrer une demande.")}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

/** Etape 1 : enregistrement d'une demande d'equipement. */
function NewRequest({ onCancel, onCreated }: { onCancel: () => void; onCreated: (f: Attribution) => void }) {
  const { t } = useI18n();
  const { rows } = useStore();
  const agents = (rows.agent ?? []).filter((a) => a.actif !== "false");
  const categories = rows.categorie_materiel ?? [];
  const [v, setV] = useState({
    agent_id: "", categorie_id: "", besoin: "", canal: "FORMULAIRE", reference_canal: "",
    demandeur: "", date_demande: today(), valide_par: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((x) => ({ ...x, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!v.agent_id) { setError(t("Choisissez l’agent futur détenteur.")); return; }
    setBusy(true);
    setError("");
    try {
      const body = {
        agent_id: Number(v.agent_id), categorie_id: v.categorie_id ? Number(v.categorie_id) : null,
        besoin: v.besoin, canal: v.canal, reference_canal: v.reference_canal, demandeur: v.demandeur,
        date_demande: v.date_demande, valide_par: v.valide_par,
      };
      onCreated(await api.create("attributions", body) as unknown as Attribution);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Erreur inattendue."));
    } finally { setBusy(false); }
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <div className="pane-head">
        <h2>{t("Nouvelle demande d’équipement")}</h2>
        <button type="button" className="btn ghost" onClick={onCancel}>{t("Fermer")}</button>
      </div>
      <div className="pane-body">
        <p className="hint pad">{t("Étape 1 : le collaborateur ou son responsable formule la demande ; elle doit être validée par le manager.")}</p>
        <fieldset className="fieldset" disabled={busy}>
          <div className="grid">
            <div className="field">
              <label htmlFor="n-agent">{t("Futur détenteur")} *</label>
              <select id="n-agent" value={v.agent_id} onChange={set("agent_id")}>
                <option value="">—</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} ({a.matricule})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="n-cat">{t("Type d’équipement souhaité")}</label>
              <select id="n-cat" value={v.categorie_id} onChange={set("categorie_id")}>
                <option value="">—</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.libelle}</option>)}
              </select>
            </div>
            <div className="field wide">
              <label htmlFor="n-besoin">{t("Besoin (type, configuration)")}</label>
              <textarea id="n-besoin" rows={3} value={v.besoin} onChange={set("besoin")} />
            </div>
            <div className="field">
              <label htmlFor="n-canal">{t("Canal de la demande")}</label>
              <select id="n-canal" value={v.canal} onChange={set("canal")}>
                {Object.entries(CANAL_LABEL).map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="n-refc">{t("N° de ticket / objet du mail")}</label>
              <input id="n-refc" value={v.reference_canal} onChange={set("reference_canal")} />
            </div>
            <div className="field">
              <label htmlFor="n-dem">{t("Demandeur")}</label>
              <input id="n-dem" value={v.demandeur} onChange={set("demandeur")} placeholder={t("Collaborateur ou responsable")} />
            </div>
            <div className="field">
              <label htmlFor="n-date">{t("Date de la demande")}</label>
              <input id="n-date" type="date" value={v.date_demande} onChange={set("date_demande")} />
            </div>
            <div className="field wide">
              <label htmlFor="n-val">{t("Déjà validée par (manager)")}</label>
              <input id="n-val" value={v.valide_par} onChange={set("valide_par")} placeholder={t("Laisser vide si la validation est à venir")} />
            </div>
          </div>
        </fieldset>
      </div>
      <div className="form-foot">
        <button type="submit" className="btn primary" disabled={busy}>{busy ? t("Envoi…") : t("Enregistrer la demande")}</button>
        {error && <p className="error foot-error" role="alert">{error}</p>}
      </div>
    </form>
  );
}
