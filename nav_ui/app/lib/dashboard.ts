// Tableau de bord : types du rapport renvoyé par l'API, chargement et téléchargement des exports
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";

/** Texte : chaîne simple, ou modèle traduisible {t: "… {n} …", p: {n: 3}} (voir dashboard_service.py). */
export type Txt = string | { t: string; p: Record<string, string | number> };

export type Objective =
  | { op: "between"; min: number; max: number }
  | { op: ">=" | "<="; value: number };

export type Indicator = {
  code: string;
  label: Txt;
  value: number;
  unit: string;
  objective: Objective | null;
  ecart: number | null;
  statut: string;
  tone: "ok" | "bad" | "none";
};

export type Column = { key: string; label: string; align: "left" | "right" };
export type Cell = string | number | null | Txt;
export type DashTable = {
  code: string;
  title: string;
  columns: Column[];
  rows: Record<string, Cell>[];
  total: Record<string, Cell> | null;
  note: Txt | null;
};

export type Alert = { priorite: "Haute" | "Moyenne" | "Basse"; alerte: Txt; action: Txt };

export type Chart = {
  code: string;
  title: string;
  kind: "line" | "bar";
  unit: string;
  note?: string;
  band?: [number, number];
  series: { name: string; values: number[] }[];
};

export type Report = {
  generated_at: string;
  months: number;
  overview: Indicator[];
  tables: DashTable[];
  alerts: Alert[];
  evolution: { labels: string[]; charts: Chart[] };
};

export const PERIODS = [6, 12, 24, 36] as const;

export type DashStatus = "loading" | "ready" | "error";

export function useDashboard(months: number) {
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState<DashStatus>("loading");
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    api.get<Report>(`/dashboard?mois=${months}`)
      .then((r) => { if (!cancelled) { setReport(r); setStatus("ready"); } })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Erreur inattendue.");
        setStatus("error");
      });
    return () => { cancelled = true; };
  }, [months, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { report, status, error, reload };
}

/** Télécharge un export : le jeton passe par l'en-tête (api.blob), puis on déclenche l'enregistrement. */
export async function downloadExport(kind: "pdf" | "xlsx", months: number): Promise<void> {
  const blob = await api.blob(`/dashboard/export.${kind}?mois=${months}`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `tableau-de-bord-parc-${new Date().toISOString().slice(0, 10)}.${kind}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
