// Affectation directe : le depositaire comptable RETIRE un materiel a son detenteur et l'AFFECTE a un autre agent.
// (Une ATTRIBUTION, elle, donne a un agent un materiel qui n'a pas de detenteur : voir l'onglet Attributions.)
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useStore } from "../lib/store";
import { Modal } from "./Modal";

type Detenu = { id: number; code_inventaire: string; designation: string; detenteur_id: number; detenteur: string };
type Options = { detenus: Detenu[] };

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const today = () => new Date().toISOString().slice(0, 10);
const EMPTY = { materiel: "", agent: "", date: today(), etat: "", observations: "" };

export function AffectationTransfer() {
  const { t } = useI18n();
  const { rows, refresh } = useStore();
  const [open, setOpen] = useState(false);
  const [detenus, setDetenus] = useState<Detenu[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  // materiels actuellement detenus : recharges a chaque ouverture du formulaire
  useEffect(() => {
    if (!open) return;
    api.get<Options>("/demandes/options").then((o) => setDetenus(o.detenus))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")));
  }, [open, t]);

  const chosen = detenus.find((d) => String(d.id) === form.materiel);
  const agents = useMemo(
    () => rows.agent.filter((a) => a.actif !== "false" && String(a.id) !== String(chosen?.detenteur_id ?? "")),
    [rows.agent, chosen],
  );
  const shown = useMemo(() => {
    const q = norm(query.trim());
    return detenus.filter((d) => !q || norm(`${d.code_inventaire} ${d.designation} ${d.detenteur}`).includes(q));
  }, [detenus, query]);

  const close = () => { setOpen(false); setForm(EMPTY); setQuery(""); setError(""); };

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.materiel || !form.agent) { setError(t("Choisissez le matériel et le nouvel agent.")); return; }
    setBusy(true);
    setError("");
    try {
      await api.post("/transferts", {
        materiel_id: Number(form.materiel), agent_id: Number(form.agent), date: form.date || null,
        etat: form.etat || null, observations: form.observations || null,
      });
      await refresh(["affectation", "materiel"]);
      setDone(t("Affectation enregistrée : {m} est maintenant détenu par le nouvel agent.", { m: chosen?.code_inventaire ?? "" }));
      close();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Erreur inattendue."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="dash-section">
      <button type="button" className="btn primary" onClick={() => { setDone(""); setOpen(true); }}>{t("Nouvelle affectation")}</button>
      <p className="hint">{t("Retirer un matériel à son détenteur actuel et l’affecter à un autre agent. Pour donner un matériel qui n’a pas de détenteur, utilisez Attributions.")}</p>
      {done && <p className="lede" role="status">{done}</p>}
      {open && (
        <Modal title={t("Nouvelle affectation")} onClose={close}>
          <form onSubmit={(e) => void submit(e)} className="rq-form">
            <div className="field"><label htmlFor="aff-q">{t("Matériel à retirer à son détenteur")}</label>
              <input id="aff-q" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("Filtrer la liste")} />
              <select value={form.materiel} onChange={(e) => setForm({ ...form, materiel: e.target.value, agent: "" })} aria-label={t("Matériel à retirer à son détenteur")} size={6}>
                {shown.map((d) => <option key={d.id} value={d.id}>{d.code_inventaire} — {d.designation} ({t("détenu par")} {d.detenteur})</option>)}
              </select>
              {detenus.length === 0 && <small>{t("Aucun matériel n’est détenu pour l’instant.")}</small>}
            </div>
            <div className="field"><label htmlFor="aff-agent">{t("Nouvel agent détenteur")}</label>
              <select id="aff-agent" value={form.agent} onChange={(e) => setForm({ ...form, agent: e.target.value })} disabled={!chosen}>
                <option value="">—</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom}</option>)}
              </select></div>
            <div className="field"><label htmlFor="aff-date">{t("Date")}</label>
              <input id="aff-date" type="date" value={form.date} max={today()} onChange={(e) => setForm({ ...form, date: e.target.value })} /></div>
            <div className="field"><label htmlFor="aff-etat">{t("État constaté")}</label>
              <select id="aff-etat" value={form.etat} onChange={(e) => setForm({ ...form, etat: e.target.value })}>
                <option value="">{t("Inchangé")}</option>
                <option value="NEUF">{t("Neuf")}</option><option value="BON">{t("Bon")}</option><option value="A_REPARER">{t("À réparer")}</option>
              </select></div>
            <div className="field"><label htmlFor="aff-obs">{t("Observations")}</label>
              <textarea id="aff-obs" rows={2} value={form.observations} onChange={(e) => setForm({ ...form, observations: e.target.value })} /></div>
            {error && <p className="error" role="alert">{error}</p>}
            <div className="rq-actions">
              <button type="submit" className="btn primary" disabled={busy}>{t("Affecter")}</button>
              <button type="button" className="btn ghost" onClick={close}>{t("Annuler")}</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
