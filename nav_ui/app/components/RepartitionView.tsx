// Tableau de bord > Répartition : diagramme par services + nombre d'agents et de matériels par catégorie du dictionnaire
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Cat = { nb_materiels: number; nb_agents: number };
type Rep = {
  generated_at: string;
  categories: { code: string; libelle: string; nb_materiels: number; nb_agents: number }[];
  services: { id: number | null; nom: string; nb_agents: number; nb_materiels: number; nb_agents_detenteurs: number; par_categorie: Record<string, Cat> }[];
  total: { nb_materiels: number; nb_agents_detenteurs: number };
};

const COLORS = ["#2f6f4f", "#c9822b", "#3a6ea5", "#a64d79", "#7a8f2e", "#b5483a", "#4b9aa8", "#8a6fb3", "#6b6b6b", "#d1a93a", "#2c4a3e", "#9c5b2e", "#5e7ea8"];

export function RepartitionView() {
  const { t } = useI18n();
  const [rep, setRep] = useState<Rep | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Rep>("/dashboard/repartition").then((r) => setRep(r as unknown as Rep))
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("Erreur inattendue.")));
  }, [t]);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!rep) return <p className="api-loading" role="status">{t("Chargement des données…")}</p>;

  const max = Math.max(1, ...rep.services.map((s) => s.nb_materiels));
  const used = rep.categories.filter((c) => c.nb_materiels > 0);
  const color = (code: string) => COLORS[rep.categories.findIndex((c) => c.code === code) % COLORS.length];
  const ROW = 34, LABEL = 190, W = 640;

  return (
    <div className="dash">
    <div className="dash-body">
      <p className="lede">{t("Matériel actuellement détenu par service : {m} matériels, {a} agents détenteurs.", { m: rep.total.nb_materiels, a: rep.total.nb_agents_detenteurs })}</p>

      <section className="dash-section">
        <h2>{t("Matériels par service")}</h2>
        <div className="dash-card rep-chart">
          <svg viewBox={`0 0 ${LABEL + W + 60} ${rep.services.length * ROW + 10}`} role="img" aria-label={t("Matériels par service")} className="chart-svg">
            {rep.services.map((s, i) => {
              let x = LABEL;
              return (
                <g key={s.id ?? "none"} transform={`translate(0 ${i * ROW + 4})`}>
                  <text x={LABEL - 8} y={19} textAnchor="end" fontSize="13" fill="currentColor">{s.nom}</text>
                  {used.map((c) => {
                    const n = s.par_categorie[c.code]?.nb_materiels ?? 0;
                    const w = (n / max) * W;
                    const rect = n > 0 ? (
                      <rect key={c.code} x={x} y={4} width={w} height={22} fill={color(c.code)}>
                        <title>{`${s.nom} · ${c.libelle} : ${n} ${t("matériels")}, ${s.par_categorie[c.code].nb_agents} ${t("agents")}`}</title>
                      </rect>
                    ) : null;
                    x += w;
                    return rect;
                  })}
                  <text x={x + 6} y={19} fontSize="13" fill="currentColor">{s.nb_materiels}</text>
                </g>
              );
            })}
          </svg>
        </div>
        <ul className="rep-legend">
          {used.map((c) => <li key={c.code}><i style={{ background: color(c.code) }} />{c.libelle}</li>)}
        </ul>
      </section>

      <section className="dash-section">
        <h2>{t("Par catégorie du dictionnaire")}</h2>
        <div className="dash-card table-wrap">
          <table className="table dash-table">
            <thead><tr><th>{t("Catégorie")}</th><th className="num">{t("Matériels")}</th><th className="num">{t("Agents")}</th></tr></thead>
            <tbody>
              {rep.categories.map((c) => (
                <tr key={c.code}><td>{c.libelle}</td><td className="num">{c.nb_materiels}</td><td className="num">{c.nb_agents}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="dash-section">
        <h2>{t("Par service et par catégorie")}</h2>
        <div className="dash-card table-wrap">
          <table className="table dash-table">
            <thead>
              <tr>
                <th>{t("Service")}</th><th className="num">{t("Agents")}</th>
                {used.map((c) => <th key={c.code} className="num">{c.libelle}</th>)}
                <th className="num">{t("Total")}</th>
              </tr>
            </thead>
            <tbody>
              {rep.services.map((s) => (
                <tr key={s.id ?? "none"}>
                  <td>{s.nom}</td><td className="num">{s.nb_agents_detenteurs}/{s.nb_agents}</td>
                  {used.map((c) => <td key={c.code} className="num">{s.par_categorie[c.code]?.nb_materiels || "—"}</td>)}
                  <td className="num"><strong>{s.nb_materiels}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">{t("Agents : détenteurs / total du service. Chaque cellule compte les matériels en cours de détention.")}</p>
      </section>
    </div>
    </div>
  );
}
