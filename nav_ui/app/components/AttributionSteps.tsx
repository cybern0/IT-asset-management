import { useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import {
  ACCESSOIRES, agentName, CANAL_LABEL, downloadPdf, ETAPES, ETAT_LABEL, fmtDate, openScan, type Attribution,
} from "../lib/detention";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";
import { useStore } from "../lib/store";

const today = () => new Date().toISOString().slice(0, 10);
const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

type StepState = "done" | "current" | "todo";

/** Les 6 etapes du processus pour un dossier : resume des etapes faites + action de l'etape en cours. */
export function AttributionSteps({ d, onChange }: { d: Attribution; onChange: (f: Attribution) => void }) {
  const { t } = useI18n();
  const { refresh } = useStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [changing, setChanging] = useState(false); // etape 2 rouverte (changer d'equipement)
  const [resign, setResign] = useState(false); // etape 4 rouverte (modifier la signature)
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [motif, setMotif] = useState("");

  const closed = d.cloture !== null;
  const signed = d.statut === "SIGNEE";
  const attributed = d.affectation_id !== null;

  async function run(action: () => Promise<Attribution | void>, after?: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      const f = await action();
      if (f) onChange(f);
      if (after) await after();
    } catch (e) {
      setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue."));
    } finally { setBusy(false); setConfirmCancel(false); }
  }
  const post = (path: string, body: unknown = {}) =>
    api.create(`attributions/${d.id}/${path}`, body as never) as unknown as Promise<Attribution>;

  const done: Record<number, boolean> = {
    1: d.valide_par !== null, 2: d.materiel_id !== null, 3: d.date_generation !== null,
    4: signed, 5: attributed, 6: attributed,
  };
  const stateOf = (n: number): StepState => (done[n] ? "done" : !closed && n === d.etape ? "current" : "todo");

  return (
    <div className="attrib">
      <div className="attrib-head">
        <span className="badge" data-tone={d.etat === "EN_COURS" ? "warn" : tone(ETAT_LABEL[d.etat])}>
          {d.etat === "EN_COURS" ? `${t("Étape")} ${d.etape}/6` : t(ETAT_LABEL[d.etat])}
        </span>
        <span className="badge" data-tone={signed ? "ok" : "warn"}>{t(signed ? "Signée" : "Non signée")}</span>
        <span className="hint">{agentName(d)} · {d.agent_matricule}</span>
      </div>

      {closed && (
        <p className="notice-box" role="status">
          {t(d.cloture === "REFUSEE" ? "Demande refusée." : "Dossier annulé.")}{d.motif_cloture ? ` ${d.motif_cloture}` : ""}
        </p>
      )}

      <ol className="steps">
        {ETAPES.map((s) => {
          const st = stateOf(s.n);
          return (
            <li key={s.n} className="step" data-state={closed && st !== "done" ? "closed" : st}>
              <span className="step-n" aria-hidden="true">{done[s.n] ? "✓" : s.n}</span>
              <div className="step-main">
                <h3>{t(s.title)}</h3>
                <p className="hint">{t(s.desc)}</p>

                {s.n === 1 && (
                  <>
                    <dl className="mini">
                      <dt>{t("Futur détenteur")}</dt><dd>{agentName(d)} ({d.agent_matricule}){d.service_nom ? ` · ${d.service_nom}` : ""}</dd>
                      <dt>{t("Type d’équipement souhaité")}</dt><dd>{d.categorie_demandee ?? "—"}</dd>
                      <dt>{t("Besoin (type, configuration)")}</dt><dd>{d.besoin ?? "—"}</dd>
                      <dt>{t("Canal de la demande")}</dt>
                      <dd>{t(CANAL_LABEL[d.canal])}{d.reference_canal ? ` · ${d.reference_canal}` : ""}{d.demandeur ? ` · ${d.demandeur}` : ""} · {fmtDate(d.date_demande)}</dd>
                      {d.valide_par && <><dt>{t("Validée par")}</dt><dd>{d.valide_par} · {fmtDate(d.date_validation)}</dd></>}
                    </dl>
                    {st === "current" && <ValidateForm busy={busy} onValidate={(v) => run(() => post("valider", v))}
                      onRefuse={(m) => run(() => post("refuser", { motif: m }))} />}
                  </>
                )}

                {s.n === 2 && (
                  <>
                    {d.materiel_id !== null && (
                      <p className="step-sum">
                        <strong>{d.materiel_designation}</strong> · {d.materiel_code}
                        {d.materiel_serie ? ` · ${t("N° de série")} ${d.materiel_serie}` : ""}
                        {!attributed && !signed && !closed && !changing && (
                          <button type="button" className="btn ghost small" disabled={busy} onClick={() => setChanging(true)}>{t("Changer d’équipement")}</button>
                        )}
                      </p>
                    )}
                    {((st === "current") || changing) && !closed && (
                      <EquipmentPicker
                        d={d} busy={busy}
                        onPick={(id) => run(() => post("selectionner", { materiel_id: id }), async () => setChanging(false))}
                      />
                    )}
                  </>
                )}

                {s.n === 3 && d.date_generation && (
                  <p className="step-sum">
                    {t("Fiche {r} générée le {d}.", { r: d.reference, d: fmtDate(d.date_generation) })}
                    <button type="button" className="btn ghost small" disabled={busy} onClick={() => void run(() => downloadPdf(d))}>
                      {t("Exporter en PDF")}
                    </button>
                  </p>
                )}

                {s.n === 4 && (
                  <>
                    {signed && !resign && (
                      <p className="step-sum">
                        {t("Signée le {d}", { d: fmtDate(d.date_signature) })}
                        {d.mode_signature ? ` · ${t(d.mode_signature === "MANUSCRITE" ? "Manuscrite" : "Électronique")}` : ""}
                        {d.signe_par ? ` · ${d.signe_par}` : ""}
                        {d.a_fichier_signe && (
                          <button type="button" className="btn ghost small" disabled={busy} onClick={() => void run(() => openScan(d))}>{t("Voir le scan signé")}</button>
                        )}
                        {!closed && <button type="button" className="btn ghost small" disabled={busy} onClick={() => setResign(true)}>{t("Modifier la signature")}</button>}
                        {!closed && !attributed && (
                          <button type="button" className="btn ghost small" disabled={busy} onClick={() => void run(() => post("annuler-signature"))}>{t("Annuler la signature")}</button>
                        )}
                      </p>
                    )}
                    {!closed && d.materiel_id !== null && (!signed || resign) && (st === "current" || attributed || resign) && (
                      <SignForm busy={busy} onCancel={resign ? () => setResign(false) : undefined}
                        onSign={(form) => run(() => api.upload<Attribution>(`/attributions/${d.id}/signer`, form), async () => setResign(false))} />
                    )}
                  </>
                )}

                {s.n === 5 && (
                  <>
                    {attributed && (
                      <p className="step-sum">
                        {t("Remis le {d}", { d: fmtDate(d.date_remise) })}
                        {d.etat_constate ? ` · ${t("État constaté")} : ${t(d.etat_constate === "NEUF" ? "Neuf" : d.etat_constate === "BON" ? "Bon" : "À réparer")}` : ""}
                        {d.accessoires.length || d.accessoires_autre ? ` · ${[...d.accessoires, d.accessoires_autre].filter(Boolean).join(", ")}` : ""}
                      </p>
                    )}
                    {st === "current" && <HandOverForm busy={busy} d={d} onSubmit={(body) =>
                      run(() => post("remettre", body), () => refresh(["materiel", "affectation", "journal_audit"]))} />}
                  </>
                )}

                {s.n === 6 && attributed && (
                  <p className="step-sum">
                    {t("Matériel au statut « Attribué » (affectation n° {n}). La fiche signée est archivée.", { n: d.affectation_id ?? "" })}
                    {d.date_retour && ` ${t("Rendu le {d}.", { d: fmtDate(d.date_retour) })}`}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {!closed && !attributed && (
        <div className="attrib-foot">
          {confirmCancel ? (
            <>
              <input value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t("Motif (facultatif)")} aria-label={t("Motif (facultatif)")} />
              <button type="button" className="btn danger" disabled={busy} onClick={() => void run(() => post("annuler", { motif }))}>{t("Confirmer l’annulation")}</button>
              <button type="button" className="btn ghost" onClick={() => setConfirmCancel(false)}>{t("Retour")}</button>
            </>
          ) : (
            <button type="button" className="btn ghost" disabled={busy} onClick={() => setConfirmCancel(true)}>{t("Annuler le dossier")}</button>
          )}
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

function ValidateForm({ busy, onValidate, onRefuse }: {
  busy: boolean; onValidate: (v: { valide_par: string; date_validation: string }) => void; onRefuse: (motif: string) => void;
}) {
  const { t } = useI18n();
  const [par, setPar] = useState("");
  const [date, setDate] = useState(today());
  const [refusing, setRefusing] = useState(false);
  const [motif, setMotif] = useState("");
  return (
    <div className="step-form">
      <label>{t("Validée par (manager)")}
        <input value={par} onChange={(e) => setPar(e.target.value)} />
      </label>
      <label>{t("Date de validation")}
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" className="btn primary" disabled={busy || !par.trim()} onClick={() => onValidate({ valide_par: par.trim(), date_validation: date })}>
          {t("Valider la demande")}
        </button>
        {!refusing && <button type="button" className="btn ghost" disabled={busy} onClick={() => setRefusing(true)}>{t("Refuser la demande")}</button>}
      </div>
      {refusing && (
        <div className="row">
          <input value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t("Motif du refus")} aria-label={t("Motif du refus")} />
          <button type="button" className="btn danger" disabled={busy} onClick={() => onRefuse(motif)}>{t("Confirmer le refus")}</button>
        </div>
      )}
    </div>
  );
}

function EquipmentPicker({ d, busy, onPick }: { d: Attribution; busy: boolean; onPick: (id: number) => void }) {
  const { t } = useI18n();
  const { rows } = useStore();
  const [cat, setCat] = useState(d.categorie_id ? String(d.categorie_id) : "");
  const [q, setQ] = useState("");
  const [choice, setChoice] = useState("");
  const categories = rows.categorie_materiel ?? [];

  const stock = useMemo(() => {
    const needle = norm(q.trim());
    return (rows.materiel ?? []).filter((m) =>
      m.statut === "EN_STOCK" && (!cat || m.categorie_id === cat) &&
      (!needle || norm(`${m.designation} ${m.code_inventaire} ${m.marque ?? ""} ${m.modele ?? ""} ${m.caracteristiques ?? ""}`).includes(needle)));
  }, [rows.materiel, cat, q]);

  return (
    <div className="step-form">
      <div className="row">
        <select value={cat} onChange={(e) => { setCat(e.target.value); setChoice(""); }} aria-label={t("Catégorie")}>
          <option value="">{t("Toutes les catégories")}</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.libelle}</option>)}
        </select>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("Filtrer la liste")} aria-label={t("Filtrer la liste")} />
      </div>
      {stock.length === 0 ? (
        <p className="empty">{t("Aucun équipement disponible en stock pour ce critère.")}</p>
      ) : (
        <ul className="pick" role="radiogroup" aria-label={t("Équipements en stock")}>
          {stock.map((m) => (
            <li key={m.id}>
              <label className="pick-item">
                <input type="radio" name={`pick-${d.id}`} checked={choice === m.id} onChange={() => setChoice(m.id)} />
                <span><strong>{m.designation}</strong> · {m.code_inventaire}
                  {m.caracteristiques && <span className="hint block">{m.caracteristiques}</span>}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="btn primary" disabled={busy || !choice} onClick={() => onPick(Number(choice))}>
        {t("Sélectionner cet équipement")}
      </button>
    </div>
  );
}

function SignForm({ busy, onSign, onCancel }: { busy: boolean; onSign: (f: FormData) => void; onCancel?: () => void }) {
  const { t } = useI18n();
  const [mode, setMode] = useState("MANUSCRITE");
  const [par, setPar] = useState("");
  const [date, setDate] = useState(today());
  const [scan, setScan] = useState<File | null>(null);

  function submit() {
    const f = new FormData();
    f.append("mode_signature", mode);
    f.append("date_signature", date);
    if (par.trim()) f.append("signe_par", par.trim());
    if (scan) f.append("fichier", scan);
    onSign(f);
  }

  return (
    <div className="step-form">
      <p className="hint">{t("Imprimez la fiche (Exporter en PDF), faites-la signer par le détenteur et le responsable, puis enregistrez la signature.")}</p>
      <div className="row">
        <label>{t("Mode de signature")}
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="MANUSCRITE">{t("Manuscrite")}</option>
            <option value="ELECTRONIQUE">{t("Électronique")}</option>
          </select>
        </label>
        <label>{t("Date de signature")}
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>
      <label>{t("Responsable signataire (informatique ou hiérarchique)")}
        <input value={par} onChange={(e) => setPar(e.target.value)} />
      </label>
      <label>{t("Scan du document signé (facultatif)")}
        <input type="file" accept="application/pdf,image/jpeg,image/png,image/webp" onChange={(e) => setScan(e.target.files?.[0] ?? null)} />
      </label>
      <div className="row">
        <button type="button" className="btn primary" disabled={busy || !date} onClick={submit}>{t("Enregistrer la signature")}</button>
        {onCancel && <button type="button" className="btn ghost" onClick={onCancel}>{t("Annuler")}</button>}
      </div>
    </div>
  );
}

function HandOverForm({ busy, d, onSubmit }: { busy: boolean; d: Attribution; onSubmit: (body: unknown) => void }) {
  const { t } = useI18n();
  const [date, setDate] = useState(today());
  const [etat, setEtat] = useState(d.materiel_etat === "NEUF" ? "NEUF" : "BON");
  const [acc, setAcc] = useState<string[]>([]);
  const [autre, setAutre] = useState("");
  const [obs, setObs] = useState("");
  const toggle = (a: string) => setAcc((l) => (l.includes(a) ? l.filter((x) => x !== a) : [...l, a]));

  return (
    <div className="step-form">
      <div className="row">
        <label>{t("Date de remise")}
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>{t("État constaté (contrôle visuel)")}
          <select value={etat} onChange={(e) => setEtat(e.target.value)}>
            <option value="NEUF">{t("Neuf")}</option>
            <option value="BON">{t("Bon")}</option>
            <option value="A_REPARER">{t("À réparer")}</option>
          </select>
        </label>
      </div>
      <fieldset className="checks">
        <legend>{t("Accessoires remis")}</legend>
        {ACCESSOIRES.map((a) => (
          <label key={a} className="check"><input type="checkbox" checked={acc.includes(a)} onChange={() => toggle(a)} /> {t(a)}</label>
        ))}
      </fieldset>
      <label>{t("Autre accessoire")}
        <input value={autre} onChange={(e) => setAutre(e.target.value)} />
      </label>
      <label>{t("Observations")}
        <textarea rows={2} value={obs} onChange={(e) => setObs(e.target.value)} />
      </label>
      <p className="hint">{t("En confirmant, le matériel passe au statut « Attribué » et la fiche signée est archivée.")}</p>
      <button type="button" className="btn primary" disabled={busy || !date}
        onClick={() => onSubmit({ date_remise: date, etat_constate: etat, accessoires: acc, accessoires_autre: autre, observations: obs })}>
        {t("Confirmer la remise du matériel")}
      </button>
    </div>
  );
}
