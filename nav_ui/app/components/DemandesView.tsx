// Circuit de demande : 1 demande · 2 approbation et choix du matériel · 3 signature de l'agent · 4 signature du chef de
// service · 5 remise · 6 approbation de la réception. Même présentation que « Attributions et affectations » :
// la liste à gauche, le détail en étapes à droite. Les boutons viennent de l'API (champ `actions`) : le RBAC est côté serveur.
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, type Json } from "../lib/api";
import { useAuth } from "../lib/auth";
import { agentName, downloadPdf, fmtDate, type Attribution } from "../lib/detention";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { useStore } from "../lib/store";

type Demande = Attribution & {
  phase: string; role_attendu: string | null; actions: string[]; chef_nom: string | null; ancien_detenteur: string | null;
  motif_refus: string | null; approuve_le: string | null; signature_agent_le: string | null; signature_chef_le: string | null;
  reception_approuvee_le: string | null;
};
type Notif = { id: number; destinataire_nom: string | null; canal: string; adresse: string | null; lien: string | null; sujet: string | null; message: string; statut: string; cree_le: string };
type Mat = { id: number; code_inventaire: string; designation: string; categorie_id: number; detenteur?: string };
type Options = { categories: { id: number; libelle: string }[]; stock: Mat[]; detenus: Mat[] };

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

const PHASE: Record<string, [string, "ok" | "warn" | "bad"]> = {
  A_APPROUVER: ["À approuver", "warn"], A_SIGNER_AGENT: ["Signature de l’agent", "warn"], A_SIGNER_CHEF: ["Signature du chef de service", "warn"],
  A_REMETTRE: ["Remise du matériel", "warn"], A_APPROUVER_RECEPTION: ["Réception à approuver", "warn"], TERMINEE: ["Terminée", "ok"], CLOTUREE: ["Refusée", "bad"],
};
/** Étape en cours selon la phase renvoyée par l'API. */
const PHASE_STEP: Record<string, number> = { A_APPROUVER: 2, A_SIGNER_AGENT: 3, A_SIGNER_CHEF: 4, A_REMETTRE: 5, A_APPROUVER_RECEPTION: 6 };
const STEP_ACTION: Record<number, string> = { 2: "approuver", 3: "signer-agent", 4: "signer-chef", 5: "remettre", 6: "approuver-reception" };
const STEPS: { n: number; title: string; desc: string }[] = [
  { n: 1, title: "Demande de matériel", desc: "Demande d’un matériel : attribution d’un matériel non affecté, ou affectation (transfert) d’un matériel déjà détenu par un autre agent." },
  { n: 2, title: "Approbation et choix du matériel", desc: "Le dépositaire comptable approuve la demande, choisit le matériel et met la base à jour." },
  { n: 3, title: "Signature de l’agent", desc: "L’agent signe la fiche de détention." },
  { n: 4, title: "Signature du chef de service", desc: "Le chef de service de l’agent signe à son tour." },
  { n: 5, title: "Remise du matériel", desc: "Le matériel est remis à l’agent et la détention est enregistrée." },
  { n: 6, title: "Approbation de la réception", desc: "Le chef de service approuve la réception du matériel." },
];
/** Qui est attendu à l'étape en cours (ADMIN peut toutefois agir à la place de l'agent ou du chef). */
const WAIT: Record<string, string> = {
  A_APPROUVER: "Dépositaire comptable", A_REMETTRE: "Dépositaire comptable",
  A_SIGNER_AGENT: "L’agent demandeur", A_SIGNER_CHEF: "Le chef de service", A_APPROUVER_RECEPTION: "Le chef de service",
};
const ACTION: Record<string, string> = {
  approuver: "Approuver", "signer-agent": "Signer", "signer-chef": "Signer (chef de service)",
  remettre: "Enregistrer la remise", "approuver-reception": "Approuver la réception",
};
const CANAL: Record<string, string> = { MAIL: "Mail", SMS: "SMS", WHATSAPP: "WhatsApp" };

export function DemandesView() {
  const { t } = useI18n();
  const { has } = useAuth();
  const { refresh } = useStore();
  const [rows, setRows] = useState<Demande[]>([]);
  const [opts, setOpts] = useState<Options>({ categories: [], stock: [], detenus: [] });
  const [inbox, setInbox] = useState<Notif[]>([]);
  const [alert, setAlert] = useState<{ ref: string; items: Notif[] } | null>(null);
  const [agents, setAgents] = useState<Json[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState("");
  const [selected, setSelected] = useState<number | "new" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.get<Demande[]>("/demandes"));
      setInbox(await api.get<Notif[]>("/notifications/mes"));
      setError("");
    } catch (e) { setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue.")); }
    finally { setLoading(false); }
  }, [t]);

  useEffect(() => {
    void load();
    api.get<Options>("/demandes/options").then(setOpts).catch(() => undefined);
    if (has("demande.voir_toutes")) api.list("agents").then(setAgents).catch(() => undefined);
  }, [load, has]);

  /** Lien prêt à ouvrir pour prévenir la personne suivante (aucun serveur de messagerie). */
  async function notify(d: Demande) {
    const items = await api.get<Notif[]>(`/demandes/${d.id}/notifications`);
    setAlert(items.length ? { ref: d.reference, items } : null);
  }
  const replace = (d: Demande) => setRows((l) => (l.some((x) => x.id === d.id) ? l.map((x) => (x.id === d.id ? d : x)) : [d, ...l]));
  const markSent = (n: Notif) => { void api.post(`/notifications/${n.id}/envoyee`).then(() => setAlert((a) => a && { ...a, items: a.items.filter((x) => x.id !== n.id) })); };
  const unread = inbox.filter((n) => n.statut !== "LUE");

  const visible = useMemo(() => {
    const q = norm(query.trim());
    return rows.filter((d) => {
      if (phase && d.phase !== phase) return false;
      if (!q) return true;
      return norm(`${d.reference} ${agentName(d)} ${d.agent_matricule} ${d.materiel_designation ?? ""} ${d.materiel_code ?? ""} ${d.categorie_demandee ?? ""}`).includes(q);
    });
  }, [rows, query, phase]);

  const current = typeof selected === "number" ? rows.find((d) => d.id === selected) ?? null : null;

  return (
    <>
      {alert && (
        <div className="notice-box" role="status">
          <strong>{t("Prévenir la personne suivante ({ref})", { ref: alert.ref })}</strong>
          <p>{t("Ouvrez un lien : votre messagerie, vos SMS ou WhatsApp s’ouvre avec le message prêt à envoyer.")}</p>
          <ul className="rq-links">
            {alert.items.map((n) => (
              <li key={n.id}>
                <span>{n.destinataire_nom}</span>
                <a className="btn ghost" href={n.lien ?? "#"} target="_blank" rel="noopener noreferrer" onClick={() => markSent(n)}>{t(CANAL[n.canal] ?? n.canal)}</a>
              </li>
            ))}
          </ul>
          <button type="button" className="btn ghost" onClick={() => setAlert(null)}>{t("Fermer")}</button>
        </div>
      )}

      {unread.length > 0 && (
        <section className="dash-section">
          <h2>{t("Mes notifications")} ({unread.length})</h2>
          <ul className="rq-links">
            {unread.slice(0, 5).map((n) => (
              <li key={n.id}><span><strong>{n.sujet}</strong> — {n.message.split("\n")[0]}</span>
                <button type="button" className="btn ghost" onClick={() => void api.post(`/notifications/${n.id}/lue`).then(load)}>{t("Marquer comme lue")}</button></li>
            ))}
          </ul>
        </section>
      )}

      <div className="crud">
        <section className="pane" aria-label={t("Liste : {x}", { x: t("Demandes de matériel") })}>
          <div className="pane-head">
            <h2>{t("Demandes de matériel")} <span className="count">{visible.length}</span></h2>
            {has("demande.creer") && (
              <button type="button" className="add-btn" onClick={() => setSelected("new")}
                aria-label={t("Nouvelle demande")} title={t("Nouvelle demande")}>
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
            <select value={phase} onChange={(e) => setPhase(e.target.value)} aria-label={t("Étape")}>
              <option value="">{t("Toutes les étapes")}</option>
              {Object.entries(PHASE).map(([v, [l]]) => <option key={v} value={v}>{t(l)}</option>)}
            </select>
            <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>{t("Actualiser")}</button>
          </div>
          <div className="pane-body">
            {error ? <p className="error pad" role="alert">{error}</p>
              : loading && rows.length === 0 ? <p className="empty">{t("Chargement…")}</p>
              : visible.length === 0 ? (
                <p className="empty">{rows.length > 0 ? t("Aucun résultat pour ce filtre.") : t("Aucune demande.")}</p>
              ) : (
                <ul className="items">
                  {visible.map((d) => {
                    const [label, tone] = PHASE[d.phase] ?? [d.phase, "warn" as const];
                    return (
                      <li key={d.id}>
                        <button type="button" className="item" aria-current={selected === d.id} onClick={() => setSelected(d.id)}>
                          <span className="item-main">
                            <span className="item-title">{agentName(d)}</span>
                            <span className="item-sub">{d.reference} · {d.materiel_designation ?? d.categorie_demandee ?? t("Équipement à choisir")}</span>
                          </span>
                          <span className="badges">
                            {d.type_demande === "AFFECTATION" && <span className="badge" data-tone="neutral">{t("Transfert")}</span>}
                            <span className="badge" data-tone={tone}>{t(label)}</span>
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
            <NewDemande
              opts={opts} agents={agents} onCancel={() => setSelected(null)}
              onCreated={(d) => { replace(d); setSelected(d.id); void notify(d).catch(() => undefined); }}
            />
          ) : current ? (
            <div className="form" key={current.id}>
              <div className="pane-head">
                <h2>{current.reference}</h2>
                <span className="head-actions">
                  {current.materiel_id !== null && has("parc.lire") && (
                    <button type="button" className="btn ghost" onClick={() => void downloadPdf(current).catch((e) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")))}>
                      {t("Exporter en PDF")}
                    </button>
                  )}
                  <button type="button" className="btn ghost" onClick={() => setSelected(null)}>{t("Fermer")}</button>
                </span>
              </div>
              <div className="pane-body">
                <DemandeSteps
                  d={current} opts={opts}
                  onChange={(d) => { replace(d); void notify(d).catch(() => undefined); void refresh(["materiel", "affectation"]); }}
                />
              </div>
            </div>
          ) : (
            <div className="pane-body">
              <p className="empty">{t("Sélectionnez une demande dans la liste, ou cliquez sur + pour en faire une.")}</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

/** Les 6 étapes d'une demande : l'étape en cours porte le bouton de l'action permise par l'API. */
function DemandeSteps({ d, opts, onChange }: { d: Demande; opts: Options; onChange: (d: Demande) => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pick, setPick] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const [motif, setMotif] = useState("");

  const closed = d.phase === "CLOTUREE";
  const signed = d.statut === "SIGNEE";
  const step = PHASE_STEP[d.phase] ?? 0;
  const done: Record<number, boolean> = {
    1: true,
    2: (!!d.approuve_le || d.valide_par !== null) && d.materiel_id !== null,
    3: !!d.signature_agent_le || signed,
    4: !!d.signature_chef_le || signed,
    5: d.date_remise !== null || d.affectation_id !== null,
    6: !!d.reception_approuvee_le,
  };
  const [label, tone] = PHASE[d.phase] ?? [d.phase, "warn" as const];
  const source = d.type_demande === "AFFECTATION" ? opts.detenus : opts.stock; // transfert : matériels détenus ; attribution : matériels en stock
  const choices = source.filter((m) => !d.categorie_id || m.categorie_id === d.categorie_id);

  async function act(action: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      onChange(await api.post<Demande>(`/demandes/${d.id}/${action}`, body));
      setConfirmClose(false);
    } catch (e) {
      setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue."));
    } finally { setBusy(false); }
  }
  const confirmed = (action: string) => { if (window.confirm(t("Confirmer cette étape ?"))) void act(action); };

  /** Bouton de l'étape en cours (ou mention d'attente quand le compte n'a pas le droit de la faire). */
  function control(n: number) {
    const action = STEP_ACTION[n];
    if (closed || step !== n) return null;
    if (!d.actions.includes(action)) {
      return WAIT[d.phase] ? <p className="hint">{t("En attente de")} : {t(WAIT[d.phase])}</p> : null;
    }
    if (action === "approuver") {
      return (
        <div className="step-form">
          <label>{t("Matériel à attribuer")}
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">{t(d.type_demande === "AFFECTATION" ? "Matériel à retirer à son détenteur…" : "Matériel en stock…")}</option>
              {choices.map((m) => <option key={m.id} value={m.id}>{m.code_inventaire} — {m.designation}{m.detenteur ? ` (${t("détenu par")} ${m.detenteur})` : ""}</option>)}
            </select>
          </label>
          <div className="row">
            <button type="button" className="btn primary" disabled={busy || !pick} onClick={() => void act("approuver", { materiel_id: Number(pick) })}>{t(ACTION[action])}</button>
          </div>
        </div>
      );
    }
    return (
      <div className="step-form">
        <div className="row">
          <button type="button" className="btn primary" disabled={busy}
            onClick={() => (action === "remettre" ? void act(action, {}) : confirmed(action))}>{t(ACTION[action])}</button>
        </div>
      </div>
    );
  }

  const summary = (n: number): string | null => {
    if (!done[n]) return null;
    if (n === 2) return `${d.materiel_designation ?? ""} · ${d.materiel_code ?? ""} — ${t("Approuvée le {d}", { d: fmtDate(d.approuve_le ?? d.date_validation) })}`;
    if (n === 3) return t("Signée le {d}", { d: fmtDate(d.signature_agent_le ?? d.date_signature) });
    if (n === 4) return `${t("Signée le {d}", { d: fmtDate(d.signature_chef_le ?? d.date_signature) })}${d.signe_par ? ` · ${d.signe_par}` : ""}`;
    if (n === 5) return t("Remis le {d}", { d: fmtDate(d.date_remise) });
    if (n === 6) return t("Approuvée le {d}", { d: fmtDate(d.reception_approuvee_le) });
    return null;
  };

  return (
    <div className="attrib">
      <div className="attrib-head">
        <span className="badge" data-tone={tone}>{t(label)}</span>
        {d.type_demande === "AFFECTATION" && <span className="badge" data-tone="neutral">{t("Affectation (transfert)")}</span>}
        <span className="hint">{agentName(d)} · {d.agent_matricule}</span>
      </div>

      {closed && (
        <p className="notice-box" role="status">
          {t("Demande refusée.")}{d.motif_refus ? ` ${d.motif_refus}` : ""}
        </p>
      )}

      <ol className="steps">
        {STEPS.map((s) => {
          const state = done[s.n] ? "done" : !closed && step === s.n ? "current" : "todo";
          const sum = summary(s.n);
          return (
            <li key={s.n} className="step" data-state={closed && state !== "done" ? "closed" : state}>
              <span className="step-n" aria-hidden="true">{done[s.n] ? "✓" : s.n}</span>
              <div className="step-main">
                <h3>{t(s.title)}</h3>
                <p className="hint">{t(s.desc)}</p>
                {s.n === 1 && (
                  <dl className="mini">
                    <dt>{t("Agent concerné")}</dt><dd>{agentName(d)} ({d.agent_matricule}){d.service_nom ? ` · ${d.service_nom}` : ""}{d.chef_nom ? ` · ${t("chef")} : ${d.chef_nom}` : ""}</dd>
                    <dt>{t("Type de demande")}</dt><dd>{t(d.type_demande === "AFFECTATION" ? "Affectation (transfert)" : "Attribution")}</dd>
                    <dt>{t("Catégorie de matériel")}</dt><dd>{d.categorie_demandee ?? "—"}</dd>
                    <dt>{t("Besoin")}</dt><dd>{d.besoin ?? "—"}</dd>
                    <dt>{t("Date de la demande")}</dt><dd>{fmtDate(d.date_demande)}</dd>
                    {d.ancien_detenteur && <><dt>{t("Retiré à")}</dt><dd>{d.ancien_detenteur}</dd></>}
                  </dl>
                )}
                {sum && <p className="step-sum">{sum}</p>}
                {control(s.n)}
              </div>
            </li>
          );
        })}
      </ol>

      {d.actions.includes("refuser") && (
        <div className="attrib-foot">
          {confirmClose ? (
            <>
              <input value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t("Motif (facultatif)")} aria-label={t("Motif (facultatif)")} />
              <button type="button" className="btn danger" disabled={busy} onClick={() => void act("refuser", { motif: motif.trim() || null })}>{t("Confirmer le refus")}</button>
              <button type="button" className="btn ghost" onClick={() => setConfirmClose(false)}>{t("Retour")}</button>
            </>
          ) : (
            <button type="button" className="btn ghost" disabled={busy} onClick={() => setConfirmClose(true)}>{t("Refuser la demande")}</button>
          )}
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

/** Nouvelle demande : attribution (matériel non affecté) ou affectation (transfert d'un matériel détenu). */
function NewDemande({ opts, agents, onCancel, onCreated }: { opts: Options; agents: Json[]; onCancel: () => void; onCreated: (d: Demande) => void }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ type: "ATTRIBUTION", cat: "", besoin: "", agent: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (agents.length > 0 && !form.agent) { setError(t("Choisissez l’agent concerné.")); return; }
    setBusy(true);
    setError("");
    try {
      onCreated(await api.post<Demande>("/demandes", {
        type_demande: form.type, categorie_id: form.cat ? Number(form.cat) : null, besoin: form.besoin || null,
        agent_id: form.agent ? Number(form.agent) : null,
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Erreur inattendue."));
    } finally { setBusy(false); }
  }

  return (
    <form className="form" onSubmit={(e) => void submit(e)} noValidate>
      <div className="pane-head">
        <h2>{t("Nouvelle demande")}</h2>
        <button type="button" className="btn ghost" onClick={onCancel}>{t("Fermer")}</button>
      </div>
      <div className="pane-body">
        <p className="hint pad">
          {form.type === "AFFECTATION"
            ? t("Affectation : le dépositaire comptable retire le matériel à son détenteur actuel et vous l’affecte.")
            : t("Attribution : un matériel non affecté (en stock) est attribué à l’agent.")}
        </p>
        <fieldset className="fieldset" disabled={busy}>
          <div className="grid">
            <div className="field">
              <label htmlFor="d-type">{t("Type de demande")}</label>
              <select id="d-type" value={form.type} onChange={set("type")}>
                <option value="ATTRIBUTION">{t("Attribution : matériel non affecté")}</option>
                <option value="AFFECTATION">{t("Affectation : reprendre un matériel détenu par un autre agent")}</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="d-cat">{t("Catégorie de matériel")}</label>
              <select id="d-cat" value={form.cat} onChange={set("cat")}>
                <option value="">—</option>
                {opts.categories.map((c) => <option key={c.id} value={c.id}>{c.libelle}</option>)}
              </select>
            </div>
            {agents.length > 0 && (
              <div className="field wide">
                <label htmlFor="d-agent">{t("Agent concerné")} *</label>
                <select id="d-agent" value={form.agent} onChange={set("agent")}>
                  <option value="">—</option>
                  {agents.map((a) => <option key={String(a.id)} value={String(a.id)}>{String(a.nom)} {String(a.prenom)}</option>)}
                </select>
              </div>
            )}
            <div className="field wide">
              <label htmlFor="d-besoin">{t("Besoin")}</label>
              <textarea id="d-besoin" rows={3} value={form.besoin} onChange={set("besoin")} />
            </div>
          </div>
        </fieldset>
      </div>
      <div className="form-foot">
        <button type="submit" className="btn primary" disabled={busy}>{busy ? t("Envoi…") : t("Envoyer la demande")}</button>
        {error && <p className="error foot-error" role="alert">{error}</p>}
      </div>
    </form>
  );
}
