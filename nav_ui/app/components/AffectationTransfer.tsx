// Affectation directe : le depositaire comptable RETIRE un materiel a son detenteur et l'AFFECTE a un autre agent.
// (Une ATTRIBUTION, elle, donne a un agent un materiel qui n'a pas de detenteur : onglet Attributions.)
// Meme presentation que le formulaire de nouvelle demande des Attributions : il s'ouvre dans le panneau de detail.
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { useStore } from "../lib/store";

type Detenu = { id: number; code_inventaire: string; designation: string; detenteur_id: number; detenteur: string };
type Options = { detenus: Detenu[] };

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const today = () => new Date().toISOString().slice(0, 10);
const EMPTY = { materiel: "", agent: "", date: today(), etat: "", observations: "" };

export function NewTransfer({ onCancel, onDone }: { onCancel: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const { rows, refresh } = useStore();
  const [detenus, setDetenus] = useState<Detenu[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // materiels actuellement detenus : recharges a l'ouverture du formulaire
  useEffect(() => {
    api.get<Options>("/circuit/options").then((o) => setDetenus(o.detenus))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")));
  }, [t]);

  const chosen = detenus.find((d) => String(d.id) === form.materiel);
  const agents = useMemo(
    () => rows.agent.filter((a) => a.actif !== "false" && String(a.id) !== String(chosen?.detenteur_id ?? "")),
    [rows.agent, chosen],
  );
  const shown = useMemo(() => {
    const q = norm(query.trim());
    return detenus.filter((d) => !q || norm(`${d.code_inventaire} ${d.designation} ${d.detenteur}`).includes(q));
  }, [detenus, query]);
  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm((x) => ({ ...x, [k]: e.target.value }));

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
      onDone(); // la liste recharge : le transfert a cree un dossier de regularisation
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Erreur inattendue."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form" onSubmit={(e) => void submit(e)} noValidate>
      <div className="pane-head">
        <h2>{t("Nouvelle affectation")}</h2>
        <button type="button" className="btn ghost" onClick={onCancel}>{t("Fermer")}</button>
      </div>
      <div className="pane-body">
        <p className="hint pad">{t("Retirer un matériel à son détenteur actuel et l’affecter à un autre agent. Pour donner un matériel qui n’a pas de détenteur, utilisez l’onglet Attributions.")}</p>
        <fieldset className="fieldset" disabled={busy}>
          <div className="grid">
            <div className="field wide">
              <label htmlFor="aff-q">{t("Matériel à retirer à son détenteur")} *</label>
              <input id="aff-q" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("Filtrer la liste")} />
              <select value={form.materiel} onChange={(e) => setForm((x) => ({ ...x, materiel: e.target.value, agent: "" }))}
                aria-label={t("Matériel à retirer à son détenteur")} size={6}>
                {shown.map((d) => <option key={d.id} value={d.id}>{d.code_inventaire} — {d.designation} ({t("détenu par")} {d.detenteur})</option>)}
              </select>
              {detenus.length === 0 && <small>{t("Aucun matériel n’est détenu pour l’instant.")}</small>}
            </div>
            <div className="field">
              <label htmlFor="aff-agent">{t("Nouvel agent détenteur")} *</label>
              <select id="aff-agent" value={form.agent} onChange={set("agent")} disabled={!chosen}>
                <option value="">—</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.nom} {a.prenom} ({a.matricule})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="aff-date">{t("Date")}</label>
              <input id="aff-date" type="date" value={form.date} max={today()} onChange={set("date")} />
            </div>
            <div className="field">
              <label htmlFor="aff-etat">{t("État constaté")}</label>
              <select id="aff-etat" value={form.etat} onChange={set("etat")}>
                <option value="">{t("Inchangé")}</option>
                <option value="NEUF">{t("Neuf")}</option><option value="BON">{t("Bon")}</option><option value="A_REPARER">{t("À réparer")}</option>
              </select>
            </div>
            <div className="field wide">
              <label htmlFor="aff-obs">{t("Observations")}</label>
              <textarea id="aff-obs" rows={3} value={form.observations} onChange={set("observations")} />
            </div>
          </div>
        </fieldset>
      </div>
      <div className="form-foot">
        <button type="submit" className="btn primary" disabled={busy}>{busy ? t("Envoi…") : t("Affecter")}</button>
        {error && <p className="error foot-error" role="alert">{error}</p>}
      </div>
    </form>
  );
}
