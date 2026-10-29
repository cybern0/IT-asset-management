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
  /** Modifie son propre nom d'utilisateur et/ou mot de passe (le mot de passe actuel est exige). Leve ApiError. */
  updateProfile: (input: ProfileInput) => Promise<void>;
  can: (permission: Permission) => boolean;
  canView: (area: Area) => boolean;
};

export type ProfileInput = { currentPassword: string; username?: string; newPassword?: string };

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

  const updateProfile = useCallback(async (input: ProfileInput) => {
    const updated = await api.patch<AuthUser>("/auth/me", {
      mot_de_passe_actuel: input.currentPassword,
      nom_utilisateur: input.username || undefined,
      nouveau_mot_de_passe: input.newPassword || undefined,
    });
    setUser(updated); // le menu affiche tout de suite le nouveau nom
  }, []);

  const value = useMemo<Auth>(() => {
    const role = isRoleCode(user?.role_code) ? user.role_code : null;
    return {
      status, user, role, login, logout, updateProfile,
      can: (p) => role !== null && PERMISSIONS[role].includes(p),
      canView: (a) => role !== null && AREA_ROLES[a].includes(role),
    };
  }, [status, user, login, logout, updateProfile]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Auth {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth doit être utilisé sous <AuthProvider>");
  return v;
}
