import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router";
import type { MetaFunction } from "react-router";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export const meta: MetaFunction = () => [{ title: "Connexion · Parc informatique" }];

export default function Login() {
  const { t } = useI18n();
  const { status, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // deja connecte (ou connexion reussie) : on va vers la page demandee
  if (status === "authed") return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!username.trim() || !password) {
      setError(t("Saisissez votre nom d’utilisateur et votre mot de passe."));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.network ? t("Impossible de joindre l’API.") : err.status === 401 ? t("Identifiants invalides.") : err.message
          : t("Erreur inattendue."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit} noValidate>
        <div className="login-brand">
          <span className="brand-mark" aria-hidden="true">PI</span>
          <h1>{t("Parc informatique")}</h1>
        </div>
        <h2>{t("Connexion")}</h2>
        <fieldset className="fieldset" disabled={busy}>
          <div className="field">
            <label htmlFor="login-user">{t("Nom d’utilisateur")}</label>
            <input
              id="login-user" autoComplete="username" autoFocus value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="login-pass">{t("Mot de passe")}</label>
            <input
              id="login-pass" type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
        </fieldset>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? t("Connexion…") : t("Se connecter")}
        </button>
      </form>
    </main>
  );
}
