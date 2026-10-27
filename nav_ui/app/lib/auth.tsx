// Authentification (jeton JWT de l'API) et autorisation (role -> droits, voir access.ts)
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode,
} from "react";
import { api, getToken, setToken, setUnauthorizedHandler, type AuthUser } from "./api";
import { AREA_ROLES, isRoleCode, PERMISSIONS, type Area, type Permission, type RoleCode } from "./access";

// loading : verification du jeton en cours (toujours l'etat initial : le rendu serveur n'a pas acces au jeton)
export type AuthStatus = "loading" | "anon" | "authed";

type Auth = {
  status: AuthStatus;
  user: AuthUser | null;
  role: RoleCode | null; // null si non connecte ou role inconnu (aucun droit)
  login: (username: string, password: string) => Promise<void>; // leve ApiError si refuse
  logout: () => void;
  can: (permission: Permission) => boolean;
  canView: (area: Area) => boolean;
};

const AuthCtx = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  // au chargement : un jeton est-il deja memorise et encore valide ?
  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setStatus("anon");
      return;
    }
    api.get<AuthUser>("/auth/me")
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus("authed");
      })
      .catch(() => {
        if (!cancelled) setStatus("anon"); // jeton expire (efface par api.ts) ou API injoignable
      });
    return () => { cancelled = true; };
  }, []);

  // jeton expire ou refuse en cours de route : retour a l'ecran de connexion
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setStatus("anon");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    setToken(res.access_token);
    setUser(res.user);
    setStatus("authed");
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus("anon");
  }, []);

  const value = useMemo<Auth>(() => {
    const role = isRoleCode(user?.role_code) ? user.role_code : null;
    return {
      status, user, role, login, logout,
      can: (p) => role !== null && PERMISSIONS[role].includes(p),
      canView: (a) => role !== null && AREA_ROLES[a].includes(role),
    };
  }, [status, user, login, logout]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Auth {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth doit être utilisé sous <AuthProvider>");
  return v;
}
