import { useMemo } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { ApiStatus } from "../components/ApiStatus";
import { Forbidden } from "../components/Forbidden";
import { Sidebar } from "../components/Sidebar";
import { areaOf } from "../lib/access";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { StoreProvider } from "../lib/store";

/** Coquille de toutes les pages protegees : authentification d'abord, puis autorisation par zone. */
export default function Shell() {
  const { status, canView } = useAuth();
  const { t } = useI18n();
  const { pathname, search } = useLocation();
  // IMPORTANT : `state` doit garder la meme identite d'un rendu a l'autre. <Navigate> relance sa navigation a chaque
  // changement de `state` : avec un objet litteral recree a chaque rendu, la deconnexion bouclait a l'infini
  // (navigateur fige, puis « la page ne repond pas »).
  const loginState = useMemo(() => ({ from: pathname + search }), [pathname, search]);

  // 1) Authentification
  if (status === "loading") return <p className="api-loading" role="status">{t("Chargement…")}</p>;
  if (status === "anon") return <Navigate to="/login" state={loginState} replace />;

  // 2) Autorisation : le role doit avoir acces a la zone (voir lib/access.ts)
  const area = areaOf(pathname);
  const allowed = area === null || canView(area);

  return (
    <StoreProvider>
      <div className="app">
        <Sidebar />
        <main className="content">
          <ApiStatus />
          {allowed ? <Outlet /> : <Forbidden />}
        </main>
      </div>
    </StoreProvider>
  );
}
