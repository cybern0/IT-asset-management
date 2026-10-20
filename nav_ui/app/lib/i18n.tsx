import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { dict } from "./dict";

export type Lang = "fr" | "en" | "mg";
export const LANGS: { code: Lang; name: string }[] = [
  { code: "fr", name: "Français" },
  { code: "en", name: "English" },
  { code: "mg", name: "Malagasy" },
];

type Vars = Record<string, string | number>;
type I18n = { lang: Lang; setLang: (l: Lang) => void; t: (s: string, vars?: Vars) => string };

const Ctx = createContext<I18n | null>(null);
const KEY = "parc-lang";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("fr");

  // la langue choisie est relue côté navigateur (le rendu serveur reste en français)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "fr" || saved === "en" || saved === "mg") setLang(saved);
    } catch { /* stockage indisponible */ }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "mg" ? "mg" : lang;
    try { localStorage.setItem(KEY, lang); } catch { /* stockage indisponible */ }
  }, [lang]);

  const t = useCallback(
    (s: string, vars?: Vars) => {
      let out = dict[lang][s] ?? s;
      if (vars) for (const k of Object.keys(vars)) out = out.split(`{${k}}`).join(String(vars[k]));
      return out;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n doit être utilisé sous <I18nProvider>");
  return v;
}
