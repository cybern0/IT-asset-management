import { useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import {
  ACCESSOIRES, agentName, CANAL_LABEL, downloadPdf, ETAPES, ETAT_LABEL, fmtDate, MODE_LABEL, type Attribution,
} from "../lib/detention";
import { useI18n } from "../lib/i18n";
import { tone } from "../lib/schema";
import { useStore } from "../lib/store";

const today = () => new Date().toISOString().slice(0, 10);
const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

type StepState = "done" | "current" | "todo";

// Libelle du bouton qui defait la derniere etape faite, selon l'etape en cours
const UNDO_LABEL: Record<number, string> = { 2: "Annuler la validation", 4: "Changer d’équipement" };

/**
 * Les 6 etapes du processus pour un dossier. La validation, la signature et la remise sont des gestes humains faits
 * hors de l'application : elle enregistre seulement qu'ils ont eu lieu. Trois actions : avancer, reculer, clore.
 */
export function AttributionSteps({ d, onChange }: { d: Attribution; onChange: (f: Attribution) => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const { refresh } = useStore();
  const writable = can("write"); // lecture seule : on voit le dossier mais aucune action n'est proposée
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const [motif, setMotif] = useState("");

  const closed = d.cloture !== null;
  const signed = d.statut === "SIGNEE";
  const attributed = d.affectation_id !== null;
  const validated = d.valide_par !== null;

  async function run(action: () => Promise<Attribution | void>, after?: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      const f = await action();
      if (f) onChange(f);
      if (after) await after();
    } catch (e) {
      setError(e instanceof ApiError ? (e.network ? t("Impossible de joindre l’API.") : e.message) : t("Erreur inattendue."));
    } finally { setBusy(false); setConfirmClose(false); }
  }
  const post = (path: string, body: unknown = {}) =>
    api.create(`attributions/${d.id}/${path}`, body as never) as unknown as Promise<Attribution>;
  const advance = (body: unknown, after?: () => Promise<void>) => run(() => post("avancer", body), after);

  const done: Record<number, boolean> = {
    1: validated, 2: d.materiel_id !== null, 3: d.date_generation !== null, 4: signed, 5: attributed, 6: attributed,
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
                    {st === "current" && writable && <ValidateForm busy={busy} onValidate={(v) => advance(v)} />}
                  </>
                )}

                {s.n === 2 && (
                  <>
                    {d.materiel_id !== null && (
                      <p className="step-sum">
                        <strong>{d.materiel_designation}</strong> · {d.materiel_code}
                        {d.materiel_serie ? ` · ${t("N° de série")} ${d.materiel_serie}` : ""}
                      </p>
                    )}
                    {st === "current" && writable && <EquipmentPicker d={d} busy={busy} onPick={(id) => advance({ materiel_id: id })} />}
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

                {s.n === 4 && d.materiel_id !== null && !closed && writable && (
                  <SignatureControl d={d} busy={busy} onSave={(body) => run(() => post("signature", body))} />
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
                    {st === "current" && writable && <HandOverForm busy={busy} d={d} onSubmit={(body) =>
                      advance(body, () => refresh(["materiel", "affectation", "journal_audit"]))} />}
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

      {!closed && !attributed && writable && (
        <div className="attrib-foot">
          {confirmClose ? (
            <>
              <input value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t("Motif (facultatif)")} aria-label={t("Motif (facultatif)")} />
              <button type="button" className="btn danger" disabled={busy} onClick={() => void run(() => post("clore", { motif }))}>
                {t(validated ? "Confirmer l’annulation" : "Confirmer le refus")}
              </button>
              <button type="button" className="btn ghost" onClick={() => setConfirmClose(false)}>{t("Retour")}</button>
            </>
          ) : (
            <>
              {UNDO_LABEL[d.etape] && (
                <button type="button" className="btn ghost" disabled={busy} onClick={() => void run(() => post("reculer"))}>{t(UNDO_LABEL[d.etape])}</button>
              )}
              <button type="button" className="btn ghost" disabled={busy} onClick={() => setConfirmClose(true)}>
                {t(validated ? "Annuler le dossier" : "Refuser la demande")}
              </button>
            </>
          )}
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

function ValidateForm({ busy, onValidate }: { busy: boolean; onValidate: (v: { valide_par: string; date: string }) => void }) {
  const { t } = useI18n();
  const [par, setPar] = useState("");
  const [date, setDate] = useState(today());
  return (
    <div className="step-form">
      <label>{t("Validée par (manager)")}
        <input value={par} onChange={(e) => setPar(e.target.value)} />
      </label>
      <label>{t("Date de validation")}
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" className="btn primary" disabled={busy || !par.trim()} onClick={() => onValidate({ valide_par: par.trim(), date })}>
          {t("Valider la demande")}
        </button>
      </div>
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

/**
 * Etat de la fiche, fixe a la main (la signature a lieu hors de l'application) : « A signer » ou « Signee ».
 * Modifiable a tout moment une fois la fiche generee, y compris apres la remise.
 */
function SignatureControl({ d, busy, onSave }: { d: Attribution; busy: boolean; onSave: (body: unknown) => void }) {
  const { t, lang } = useI18n();
  const signed = d.statut === "SIGNEE";
  const [signee, setSignee] = useState(signed);
  const [mode, setMode] = useState<string>(d.mode_signature ?? "MANUSCRITE");
  const [par, setPar] = useState(d.signe_par ?? "");
  const [date, setDate] = useState(d.date_signature ?? today());
  const changed = signee !== signed || (signee && (mode !== (d.mode_signature ?? "MANUSCRITE") || par !== (d.signe_par ?? "") || date !== (d.date_signature ?? "")));
  const when = d.signature_modifiee_le ? new Date(d.signature_modifiee_le).toLocaleString(lang === "mg" ? "fr" : lang) : "";

  return (
    <div className="step-form sign-control">
      <fieldset className="checks">
        <legend>{t("État de la fiche")}</legend>
        <label className="check"><input type="radio" name={`sig-${d.id}`} checked={!signee} onChange={() => setSignee(false)} /> {t("À signer")}</label>
        <label className="check"><input type="radio" name={`sig-${d.id}`} checked={signee} onChange={() => setSignee(true)} /> {t("Signée")}</label>
      </fieldset>
      {!signed && !signee && <p className="hint">{t("Imprimez la fiche (Exporter en PDF) et faites-la signer par le détenteur et le responsable. Quand elle est signée, choisissez « Signée » ci-dessus : aucun scan n’est demandé.")}</p>}
      {signee && (
        <>
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
        </>
      )}
      <div className="row">
        <button type="button" className="btn primary" disabled={busy || !changed || (signee && !date)}
          onClick={() => onSave({ signee, ...(signee ? { date, mode_signature: mode, ...(par.trim() ? { signe_par: par.trim() } : {}) } : {}) })}>
          {t("Enregistrer l’état de la fiche")}
        </button>
        {d.signature_modifiee_le && (
          <span className="hint">
            {t("Dernière mise à jour : {d}", { d: when })}{d.signature_modifiee_par ? ` · ${d.signature_modifiee_par}` : ""}
          </span>
        )}
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
      <p className="hint">{t("En confirmant, le matériel passe au statut « Attribué ». Pensez à archiver la fiche signée (papier ou PDF).")}</p>
      <button type="button" className="btn primary" disabled={busy || !date}
        onClick={() => onSubmit({ date, etat_constate: etat, accessoires: acc, accessoires_autre: autre, observations: obs })}>
        {t("Confirmer la remise du matériel")}
      </button>
    </div>
  );
}
