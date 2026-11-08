import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import {
  ACCESSOIRES, agentName, CANAL_LABEL, downloadPdf, ETAT_LABEL, MODE_LABEL, type Attribution,
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
 *  - ATTRIBUTION : un materiel sans detenteur est donne a un agent (bouton + : nouvelle attribution, saisie en une fois) ;
 *  - AFFECTATION : un materiel deja detenu est retire a son detenteur et donne a un autre agent (bouton + : transfert).
 *  Chaque dossier garde son circuit en 6 etapes puis le retour du materiel. */
export function AttributionsView({ mode }: { mode: Mode }) {
  const { t } = useI18n();
  const { can, has } = useAuth();
  const { rows } = useStore();
  const isAff = mode === "AFFECTATION";
  const title = isAff ? t("Affectations") : t("Attributions");
  const canCreate = isAff ? has("affectation.transferer") : can("write");
  const addLabel = isAff ? t("Nouvelle affectation") : t("Nouvelle attribution");

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
                  : t("Aucune attribution pour l’instant. Utilisez le bouton + pour attribuer un matériel.")}
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
            <NewAttribution
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
                : t("Sélectionnez un dossier dans la liste, ou cliquez sur + pour attribuer un matériel.")}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

type Stock = { id: number; code_inventaire: string; designation: string; categorie_id: number };
type Options = { stock: Stock[] };

/** Nouvelle attribution, en une seule saisie : le depositaire comptable est le seul utilisateur, il n'y a donc plus
 *  6 ecrans a parcourir. Le dossier cree est identique a celui du pas a pas (reference, fiche PDF, parcours). */
function NewAttribution({ onCancel, onCreated }: { onCancel: () => void; onCreated: (f: Attribution) => void }) {
  const { t } = useI18n();
  const { rows, refresh } = useStore();
  const agents = (rows.agent ?? []).filter((a) => a.actif !== "false");
  const [stock, setStock] = useState<Stock[]>([]);
  const [query, setQuery] = useState("");
  const [acc, setAcc] = useState<string[]>([]);
  const [v, setV] = useState({
    agent_id: "", materiel_id: "", date_remise: today(), etat_constate: "", accessoires_autre: "", observations: "",
    signee: false, date_signature: "", mode_signature: "MANUSCRITE", signe_par: "",
    canal: "FORMULAIRE", reference_canal: "", demandeur: "", date_demande: "", valide_par: "", besoin: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((x) => ({ ...x, [k]: e.target.value }));

  useEffect(() => {
    api.get<Options>("/circuit/options").then((o) => setStock(o.stock))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")));
  }, [t]);

  const shown = useMemo(() => {
    const q = norm(query.trim());
    return stock.filter((m) => !q || norm(`${m.code_inventaire} ${m.designation}`).includes(q));
  }, [stock, query]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!v.agent_id || !v.materiel_id) { setError(t("Choisissez l’agent et le matériel à attribuer.")); return; }
    setBusy(true);
    setError("");
    try {
      const blank = (x: string) => x.trim() || null;
      const body = {
        agent_id: Number(v.agent_id), materiel_id: Number(v.materiel_id), date_remise: v.date_remise || null,
        etat_constate: v.etat_constate || null, accessoires: acc, accessoires_autre: blank(v.accessoires_autre),
        observations: blank(v.observations), signee: v.signee,
        date_signature: v.signee ? v.date_signature || null : null,
        mode_signature: v.signee ? v.mode_signature : null, signe_par: v.signee ? blank(v.signe_par) : null,
        canal: v.canal, reference_canal: blank(v.reference_canal), demandeur: blank(v.demandeur),
        date_demande: v.date_demande || null, valide_par: blank(v.valide_par), besoin: blank(v.besoin),
      };
      const f = await api.post<Attribution>("/attributions/directe", body);
      await refresh(["affectation", "materiel"]); // le materiel passe a « Attribue »
      onCreated(f);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Erreur inattendue."));
    } finally { setBusy(false); }
  }

  return (
    <form className="form" onSubmit={(e) => void submit(e)} noValidate>
      <div className="pane-head">
        <h2>{t("Nouvelle attribution")}</h2>
        <button type="button" className="btn ghost" onClick={onCancel}>{t("Fermer")}</button>
      </div>
      <div className="pane-body">
        <p className="hint pad">{t("Donner à un agent un matériel qui n’a pas de détenteur : la fiche est générée, la signature et la remise sont enregistrées en une fois. Pour un matériel déjà détenu, utilisez l’onglet Affectations.")}</p>
        <fieldset className="fieldset" disabled={busy}>
          <div className="grid">
            <div className="field wide">
              <label htmlFor="na-q">{t("Matériel en stock")} *</label>
              <input id="na-q" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("Filtrer la liste")} />
              <select value={v.materiel_id} onChange={set("materiel_id")} aria-label={t("Matériel en stock")} size={6}>
                {shown.map((m) => <option key={m.id} value={m.id}>{m.code_inventaire} — {m.designation}</option>)}
              </select>
              {stock.length === 0 && <small>{t("Aucun matériel n’est disponible en stock.")}</small>}
            </div>
            <div className="field">
              <label htmlFor="na-agent">{t("Futur détenteur")} *</label>
              <select id="na-agent" value={v.agent_id} onChange={set("agent_id")}>
                <option value="">—</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} ({a.matricule})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="na-date">{t("Date de remise")}</label>
              <input id="na-date" type="date" value={v.date_remise} max={today()} onChange={set("date_remise")} />
            </div>
            <div className="field">
              <label htmlFor="na-etat">{t("État constaté")}</label>
              <select id="na-etat" value={v.etat_constate} onChange={set("etat_constate")}>
                <option value="">{t("Inchangé")}</option>
                <option value="NEUF">{t("Neuf")}</option><option value="BON">{t("Bon")}</option><option value="A_REPARER">{t("À réparer")}</option>
              </select>
            </div>
            <fieldset className="checks field wide">
              <legend>{t("Accessoires remis")}</legend>
              {ACCESSOIRES.map((a) => (
                <label key={a} className="check">
                  <input type="checkbox" checked={acc.includes(a)}
                    onChange={() => setAcc((l) => (l.includes(a) ? l.filter((x) => x !== a) : [...l, a]))} /> {t(a)}
                </label>
              ))}
            </fieldset>
            <div className="field wide">
              <label htmlFor="na-autre">{t("Autre accessoire")}</label>
              <input id="na-autre" value={v.accessoires_autre} onChange={set("accessoires_autre")} />
            </div>
            <div className="field wide">
              <label htmlFor="na-obs">{t("Observations")}</label>
              <textarea id="na-obs" rows={2} value={v.observations} onChange={set("observations")} />
            </div>

            <div className="field wide">
              <label className="check">
                <input type="checkbox" checked={v.signee} onChange={(e) => setV((x) => ({ ...x, signee: e.target.checked }))} /> {t("La fiche de détention est déjà signée")}
              </label>
              <small>{t("Sinon elle reste « à signer » : vous pourrez noter la signature plus tard.")}</small>
            </div>
            {v.signee && (
              <>
                <div className="field">
                  <label htmlFor="na-sd">{t("Date de signature")}</label>
                  <input id="na-sd" type="date" value={v.date_signature} max={today()} onChange={set("date_signature")} />
                </div>
                <div className="field">
                  <label htmlFor="na-sm">{t("Mode de signature")}</label>
                  <select id="na-sm" value={v.mode_signature} onChange={set("mode_signature")}>
                    {Object.entries(MODE_LABEL).map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
                  </select>
                </div>
                <div className="field wide">
                  <label htmlFor="na-sp">{t("Signé par")}</label>
                  <input id="na-sp" value={v.signe_par} onChange={set("signe_par")} />
                </div>
              </>
            )}

            <details className="field wide">
              <summary>{t("Trace de la demande (facultatif)")}</summary>
              <div className="grid">
                <div className="field">
                  <label htmlFor="na-canal">{t("Canal de la demande")}</label>
                  <select id="na-canal" value={v.canal} onChange={set("canal")}>
                    {Object.entries(CANAL_LABEL).map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="na-refc">{t("N° de ticket / objet du mail")}</label>
                  <input id="na-refc" value={v.reference_canal} onChange={set("reference_canal")} />
                </div>
                <div className="field">
                  <label htmlFor="na-dem">{t("Demandeur")}</label>
                  <input id="na-dem" value={v.demandeur} onChange={set("demandeur")} />
                </div>
                <div className="field">
                  <label htmlFor="na-dd">{t("Date de la demande")}</label>
                  <input id="na-dd" type="date" value={v.date_demande} max={today()} onChange={set("date_demande")} />
                </div>
                <div className="field wide">
                  <label htmlFor="na-val">{t("Validée par (manager)")}</label>
                  <input id="na-val" value={v.valide_par} onChange={set("valide_par")} placeholder={t("Par défaut : le compte connecté")} />
                </div>
                <div className="field wide">
                  <label htmlFor="na-besoin">{t("Besoin (type, configuration)")}</label>
                  <textarea id="na-besoin" rows={2} value={v.besoin} onChange={set("besoin")} />
                </div>
              </div>
            </details>
          </div>
        </fieldset>
      </div>
      <div className="form-foot">
        <button type="submit" className="btn primary" disabled={busy}>{busy ? t("Envoi…") : t("Attribuer")}</button>
        {error && <p className="error foot-error" role="alert">{error}</p>}
      </div>
    </form>
  );
}
