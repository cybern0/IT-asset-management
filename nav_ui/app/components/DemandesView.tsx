// Circuit de demande : 1 l'agent demande · 2 le dépositaire comptable approuve et met la base à jour ·
// 3 l'agent signe, puis son chef de service · remise · le chef de service approuve la réception.
// Les boutons affichés viennent de l'API (champ `actions`) : le RBAC est calculé côté serveur.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Json } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Demande = {
  id: number; reference: string; type_demande: string; phase: string; role_attendu: string | null; actions: string[];
  agent_prenom: string; agent_nom: string; service_nom: string | null; chef_nom: string | null; categorie_id: number | null;
  categorie_demandee: string | null; ancien_detenteur: string | null; besoin: string | null; materiel_code: string | null; materiel_designation: string | null; motif_refus: string | null;
};
type Notif = { id: number; destinataire_nom: string | null; canal: string; adresse: string | null; lien: string | null; sujet: string | null; message: string; statut: string; cree_le: string };
type Mat = { id: number; code_inventaire: string; designation: string; categorie_id: number; detenteur?: string };
type Options = { categories: { id: number; libelle: string }[]; stock: Mat[]; detenus: Mat[] };

const PHASE: Record<string, [string, "ok" | "warn" | "bad" | ""]> = {
  A_APPROUVER: ["À approuver", "warn"], A_SIGNER_AGENT: ["Signature de l’agent", "warn"], A_SIGNER_CHEF: ["Signature du chef de service", "warn"],
  A_REMETTRE: ["Remise du matériel", "warn"], A_APPROUVER_RECEPTION: ["Réception à approuver", "warn"], TERMINEE: ["Terminée", "ok"], CLOTUREE: ["Refusée", "bad"],
};
const WAIT: Record<string, string> = { ADMIN: "Dépositaire comptable", LECTURE: "L’agent demandeur", GESTIONNAIRE: "Le chef de service" };
const ACTION: Record<string, string> = {
  approuver: "Approuver", refuser: "Refuser", "signer-agent": "Signer", "signer-chef": "Signer (chef de service)",
  remettre: "Enregistrer la remise", "approuver-reception": "Approuver la réception",
};
const CANAL: Record<string, string> = { MAIL: "Mail", SMS: "SMS", WHATSAPP: "WhatsApp" };

export function DemandesView() {
  const { t } = useI18n();
  const { has } = useAuth();
  const [rows, setRows] = useState<Demande[]>([]);
  const [opts, setOpts] = useState<Options>({ categories: [], stock: [], detenus: [] });
  const [inbox, setInbox] = useState<Notif[]>([]);
  const [alert, setAlert] = useState<{ ref: string; items: Notif[] } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<{ type: string; cat: string; besoin: string; agent: string } | null>(null);
  const [agents, setAgents] = useState<Json[]>([]);
  const [pick, setPick] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      setRows(await api.get<Demande[]>("/demandes"));
      setInbox(await api.get<Notif[]>("/notifications/mes"));
      setError("");
    } catch (e) { setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); }
  }, [t]);

  useEffect(() => {
    void load();
    api.get<Options>("/demandes/options").then(setOpts).catch(() => undefined);
    if (has("demande.voir_toutes")) api.list("agents").then(setAgents).catch(() => undefined);
  }, [load, has]);

  async function run(fn: () => Promise<Demande | null>) {
    setBusy(true); setError("");
    try {
      const d = await fn();
      await load();
      if (d) {
        // lien pret a ouvrir pour prevenir la personne suivante (aucun serveur de messagerie)
        const items = await api.get<Notif[]>(`/demandes/${d.id}/notifications`);
        setAlert(items.length ? { ref: d.reference, items } : null);
      }
    } catch (e) { setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")); } finally { setBusy(false); }
  }

  const act = (d: Demande, a: string) => run(async () => {
    const base = `/demandes/${d.id}/${a}`;
    if (a === "approuver") {
      if (!pick[d.id]) throw new ApiError(422, t("Choisissez le matériel à attribuer."));
      return api.post<Demande>(base, { materiel_id: Number(pick[d.id]) });
    }
    if (a === "refuser") return api.post<Demande>(base, { motif: window.prompt(t("Motif du refus (facultatif)")) || null });
    if (a === "remettre") return api.post<Demande>(base, {});
    if (!window.confirm(t("Confirmer cette étape ?"))) return null;
    return api.post<Demande>(base);
  });

  const submit = () => run(async () => {
    if (!form) return null;
    const d = await api.post<Demande>("/demandes", {
      type_demande: form.type, categorie_id: form.cat ? Number(form.cat) : null, besoin: form.besoin || null,
      agent_id: form.agent ? Number(form.agent) : null,
    });
    setForm(null);
    return d;
  });

  const markSent = (n: Notif) => { void api.post(`/notifications/${n.id}/envoyee`).then(() => setAlert((a) => a && { ...a, items: a.items.filter((x) => x.id !== n.id) })); };
  const unread = inbox.filter((n) => n.statut !== "LUE");

  return (
    <div className="dash">
    <div className="rq-body">
      {error && <p className="error" role="alert">{error}</p>}

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

      {has("demande.creer") && (
        <section className="dash-section">
          {!form ? (
            <button type="button" className="btn primary" onClick={() => setForm({ type: "ATTRIBUTION", cat: "", besoin: "", agent: "" })}>{t("Nouvelle demande")}</button>
          ) : (
            <div className="rq-form">
              <div className="field"><label>{t("Type de demande")}</label>
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  <option value="ATTRIBUTION">{t("Attribution : matériel non affecté")}</option><option value="AFFECTATION">{t("Affectation : reprendre un matériel détenu par un autre agent")}</option>
                </select></div>
              <div className="field"><label>{t("Catégorie de matériel")}</label>
                <select value={form.cat} onChange={(e) => setForm({ ...form, cat: e.target.value })}>
                  <option value="">—</option>{opts.categories.map((c) => <option key={c.id} value={c.id}>{c.libelle}</option>)}
                </select></div>
              {agents.length > 0 && (
                <div className="field"><label>{t("Agent concerné")}</label>
                  <select value={form.agent} onChange={(e) => setForm({ ...form, agent: e.target.value })}>
                    <option value="">—</option>{agents.map((a) => <option key={String(a.id)} value={String(a.id)}>{String(a.nom)} {String(a.prenom)}</option>)}
                  </select></div>
              )}
              <p className="hint">{form.type === "AFFECTATION" ? t("Affectation : le dépositaire comptable retire le matériel à son détenteur actuel et vous l’affecte.") : t("Attribution : un matériel non affecté (en stock) vous est donné.")}</p>
              <div className="field"><label>{t("Besoin")}</label><textarea rows={3} value={form.besoin} onChange={(e) => setForm({ ...form, besoin: e.target.value })} /></div>
              <div className="rq-actions">
                <button type="button" className="btn primary" disabled={busy} onClick={() => void submit()}>{t("Envoyer la demande")}</button>
                <button type="button" className="btn ghost" onClick={() => setForm(null)}>{t("Annuler")}</button>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="dash-section">
        <div className="dash-card table-wrap">
          <table className="table dash-table rq-table">
            <thead><tr><th>{t("Référence")}</th><th>{t("Agent")}</th><th>{t("Type")}</th><th>{t("Matériel")}</th><th>{t("Étape")}</th><th>{t("Action")}</th></tr></thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={6}>{t("Aucune demande.")}</td></tr>}
              {rows.map((d) => {
                const [label, tone] = PHASE[d.phase] ?? [d.phase, ""];
                const source = d.type_demande === "AFFECTATION" ? opts.detenus : opts.stock; // affectation : matériels détenus ; attribution : matériels en stock
                const stock = source.filter((m) => !d.categorie_id || m.categorie_id === d.categorie_id);
                return (
                  <tr key={d.id}>
                    <td>{d.reference}</td>
                    <td>{d.agent_prenom} {d.agent_nom}<br /><small>{d.service_nom}{d.chef_nom ? ` · ${t("chef")} : ${d.chef_nom}` : ""}</small></td>
                    <td>{t(d.type_demande === "AFFECTATION" ? "Affectation (transfert)" : "Attribution")}</td>
                    <td>{d.materiel_code ? `${d.materiel_code} — ${d.materiel_designation}` : (d.categorie_demandee ?? "—")}{d.ancien_detenteur && <><br /><small>{t("Retiré à")} : {d.ancien_detenteur}</small></>}</td>
                    <td><span className="badge" data-tone={tone}>{t(label)}</span>
                      {d.role_attendu && <><br /><small>{t("En attente de")} : {t(WAIT[d.role_attendu])}</small></>}
                      {d.motif_refus && <><br /><small>{d.motif_refus}</small></>}</td>
                    <td><div className="rq-actions">
                      {d.actions.includes("approuver") && (
                        <select value={pick[d.id] ?? ""} onChange={(e) => setPick({ ...pick, [d.id]: e.target.value })} aria-label={t("Matériel à attribuer")}>
                          <option value="">{t(d.type_demande === "AFFECTATION" ? "Matériel à retirer à son détenteur…" : "Matériel en stock…")}</option>
                          {stock.map((m) => <option key={m.id} value={m.id}>{m.code_inventaire} — {m.designation}{m.detenteur ? ` (${t("détenu par")} ${m.detenteur})` : ""}</option>)}
                        </select>
                      )}
                      {d.actions.map((a) => (
                        <button key={a} type="button" className={`btn ${a === "refuser" ? "ghost" : "primary"}`} disabled={busy} onClick={() => void act(d, a)}>{t(ACTION[a] ?? a)}</button>
                      ))}
                      {d.actions.length === 0 && "—"}
                    </div></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
    </div>
  );
}
