import { useState, type FormEvent } from "react";
import type { MetaFunction } from "react-router";
import { ROLE_LABEL } from "../lib/access";
import { ApiError } from "../lib/api";
import { useAuth, type ProfileInput } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export const meta: MetaFunction = () => [{ title: "Mon profil · Parc informatique" }];

const MIN_PASSWORD = 8;

/** Page profil : l'utilisateur connecté change son nom d'utilisateur et son mot de passe (mot de passe actuel exigé). */
export default function Profile() {
  const { t, lang } = useI18n();
  const { user, role } = useAuth();
  const locale = lang === "mg" ? "fr" : lang;
  const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(locale) : "—");

  return (
    <>
      <header className="page-head">
        <h1>{t("Mon profil")}</h1>
        <p className="lede">{t("Modifiez votre nom d’utilisateur et votre mot de passe.")}</p>
      </header>

      <div className="profile">
        <section className="profile-card" aria-label={t("Informations du compte")}>
          <h2>{t("Informations du compte")}</h2>
          <dl className="profile-facts">
            <dt>{t("Nom d’utilisateur")}</dt><dd>{user?.nom_utilisateur}</dd>
            <dt>{t("Rôle")}</dt><dd>{role ? t(ROLE_LABEL[role]) : t("Rôle inconnu")}</dd>
            <dt>{t("Dernière connexion")}</dt><dd>{when(user?.derniere_connexion)}</dd>
            <dt>{t("Créé le")}</dt><dd>{when(user?.cree_le)}</dd>
          </dl>
        </section>

        <UsernameForm />
        <PasswordForm />
      </div>
    </>
  );
}

/** Erreur d'un champ renvoyée par l'API, sinon message général. */
function useSubmit(run: (input: ProfileInput) => Promise<void>) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [done, setDone] = useState("");

  async function submit(input: ProfileInput, success: string): Promise<boolean> {
    if (busy) return false;
    setBusy(true);
    setError("");
    setFields({});
    setDone("");
    try {
      await run(input);
      setDone(t(success));
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.network) setError(t("Impossible de joindre l’API."));
      else if (err instanceof ApiError && err.fieldErrors.length > 0) {
        setFields(Object.fromEntries(err.fieldErrors.map((f) => [f.field, t(f.message)])));
      } else setError(err instanceof ApiError ? t(err.message) : t("Erreur inattendue."));
      return false;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, fields, done, setError, setFields, setDone, submit };
}

function UsernameForm() {
  const { t } = useI18n();
  const { user, updateProfile } = useAuth();
  const [username, setUsername] = useState(user?.nom_utilisateur ?? "");
  const [password, setPassword] = useState("");
  const s = useSubmit(updateProfile);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const name = username.trim();
    if (!name) return s.setFields({ nom_utilisateur: t("Ce champ est obligatoire.") });
    if (name === user?.nom_utilisateur) return s.setFields({ nom_utilisateur: t("Aucune modification à enregistrer.") });
    if (!password) return s.setFields({ mot_de_passe_actuel: t("Saisissez votre mot de passe actuel.") });
    if (await s.submit({ currentPassword: password, username: name }, "Nom d’utilisateur mis à jour.")) setPassword("");
  }

  return (
    <section className="profile-card" aria-label={t("Changer le nom d’utilisateur")}>
      <h2>{t("Changer le nom d’utilisateur")}</h2>
      <form onSubmit={onSubmit} noValidate>
        <fieldset className="fieldset" disabled={s.busy}>
          <div className="field">
            <label htmlFor="pf-user">{t("Nom d’utilisateur")}</label>
            <input
              id="pf-user" autoComplete="username" maxLength={80} value={username}
              aria-invalid={!!s.fields.nom_utilisateur} onChange={(e) => setUsername(e.target.value)}
            />
            {s.fields.nom_utilisateur && <span className="error" role="alert">{s.fields.nom_utilisateur}</span>}
          </div>
          <div className="field">
            <label htmlFor="pf-user-pass">{t("Mot de passe actuel")}</label>
            <input
              id="pf-user-pass" type="password" autoComplete="current-password" value={password}
              aria-invalid={!!s.fields.mot_de_passe_actuel} onChange={(e) => setPassword(e.target.value)}
            />
            {s.fields.mot_de_passe_actuel && <span className="error" role="alert">{s.fields.mot_de_passe_actuel}</span>}
          </div>
        </fieldset>
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={s.busy}>
            {s.busy ? t("Enregistrement…") : t("Enregistrer")}
          </button>
          {s.done && <span className="notice" role="status">{s.done}</span>}
          {s.error && <span className="error" role="alert">{s.error}</span>}
        </div>
      </form>
    </section>
  );
}

function PasswordForm() {
  const { t } = useI18n();
  const { updateProfile } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const s = useSubmit(updateProfile);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!current) return s.setFields({ mot_de_passe_actuel: t("Saisissez votre mot de passe actuel.") });
    if (next.length < MIN_PASSWORD) return s.setFields({ nouveau_mot_de_passe: t("Au moins {n} caractères.", { n: MIN_PASSWORD }) });
    if (next !== confirm) return s.setFields({ confirmation: t("Les deux mots de passe ne correspondent pas.") });
    if (await s.submit({ currentPassword: current, newPassword: next }, "Mot de passe mis à jour.")) {
      setCurrent(""); setNext(""); setConfirm("");
    }
  }

  return (
    <section className="profile-card" aria-label={t("Changer le mot de passe")}>
      <h2>{t("Changer le mot de passe")}</h2>
      <form onSubmit={onSubmit} noValidate>
        <fieldset className="fieldset" disabled={s.busy}>
          <div className="field">
            <label htmlFor="pf-cur">{t("Mot de passe actuel")}</label>
            <input
              id="pf-cur" type="password" autoComplete="current-password" value={current}
              aria-invalid={!!s.fields.mot_de_passe_actuel} onChange={(e) => setCurrent(e.target.value)}
            />
            {s.fields.mot_de_passe_actuel && <span className="error" role="alert">{s.fields.mot_de_passe_actuel}</span>}
          </div>
          <div className="field">
            <label htmlFor="pf-new">{t("Nouveau mot de passe")}</label>
            <input
              id="pf-new" type="password" autoComplete="new-password" maxLength={128} value={next}
              aria-invalid={!!s.fields.nouveau_mot_de_passe} onChange={(e) => setNext(e.target.value)}
            />
            {s.fields.nouveau_mot_de_passe
              ? <span className="error" role="alert">{s.fields.nouveau_mot_de_passe}</span>
              : <span className="hint">{t("Au moins {n} caractères.", { n: MIN_PASSWORD })}</span>}
          </div>
          <div className="field">
            <label htmlFor="pf-conf">{t("Confirmer le nouveau mot de passe")}</label>
            <input
              id="pf-conf" type="password" autoComplete="new-password" maxLength={128} value={confirm}
              aria-invalid={!!s.fields.confirmation} onChange={(e) => setConfirm(e.target.value)}
            />
            {s.fields.confirmation && <span className="error" role="alert">{s.fields.confirmation}</span>}
          </div>
        </fieldset>
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={s.busy}>
            {s.busy ? t("Enregistrement…") : t("Changer le mot de passe")}
          </button>
          {s.done && <span className="notice" role="status">{s.done}</span>}
          {s.error && <span className="error" role="alert">{s.error}</span>}
        </div>
      </form>
    </section>
  );
}
