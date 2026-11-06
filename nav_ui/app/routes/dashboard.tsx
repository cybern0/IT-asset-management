import { useState } from "react";
import { Navigate } from "react-router";
import { DashTabs } from "../components/dashboard/DashTabs";
import { useAuth } from "../lib/auth";
import { OverviewChart } from "../components/dashboard/OverviewChart";
import { TimeChart } from "../components/dashboard/TimeChart";
import {
  DEFAULT_PERIOD, downloadExport, PERIODS, periodKey, useDashboard,
  type Cell, type DashTable, type Period, type Txt,
} from "../lib/dashboard";
import { ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const DECIMALS3 = new Set(["stock", "seuil", "manque"]);
/** Petits tableaux affichés côte à côte ; les autres occupent toute la largeur (5 colonnes ou plus). */
const PAIRED = new Set(["etats", "ages"]);

/** Formatage des nombres, dates et textes traduisibles du rapport (langue de l'interface). */
function useFormat() {
  const { t, lang } = useI18n();
  const locale = lang === "mg" ? "fr" : lang;
  const nf = (max: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: max });
  const txt = (v: Txt): string => (typeof v === "string" ? t(v) : t(v.t, v.p));
  const cell = (key: string, v: Cell): string => {
    if (v === null || v === undefined) return "—";
    if (typeof v === "number") return nf(DECIMALS3.has(key) ? 3 : 1).format(v);
    if (typeof v === "object") return txt(v);
    if (ISO_DATE.test(v)) return new Date(`${v}T00:00:00`).toLocaleDateString(locale);
    return t(v);
  };
  return { t, txt, cell, date: (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(locale) };
}

type Fmt = ReturnType<typeof useFormat>;

/** L'administrateur voit la vue d'ensemble ; un compte sans le droit dashboard.voir arrive directement sur la repartition. */
export default function Dashboard() {
  const { has } = useAuth();
  return has("dashboard.voir") ? <Overview /> : <Navigate to="/circuit/repartition/repartition" replace />;
}

function Overview() {
  const { t } = useI18n();
  const f = useFormat();
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD);
  const { report, status, error, reload } = useDashboard(period);
  const [busy, setBusy] = useState<"pdf" | "xlsx" | null>(null);
  const [exportError, setExportError] = useState("");

  async function exportAs(kind: "pdf" | "xlsx") {
    setBusy(kind);
    setExportError("");
    try {
      await downloadExport(kind, period);
    } catch (e) {
      setExportError(e instanceof ApiError ? e.message : t("L’export a échoué."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <DashTabs />
      <header className="page-head dash-head">
        <div>
          <h1>{t("Tableau de bord")}</h1>
          {report && <p className="lede">{t("Données au {date}.", { date: f.date(report.generated_at) })}</p>}
        </div>
        <div className="dash-tools">
          <label className="dash-period">
            <span>{t("Évolution sur")}</span>
            <select
              value={periodKey(period)}
              onChange={(e) => setPeriod(PERIODS.find((p) => periodKey(p) === e.target.value) ?? DEFAULT_PERIOD)}
            >
              {PERIODS.map((p) => <option key={periodKey(p)} value={periodKey(p)}>{periodLabel(p, t)}</option>)}
            </select>
          </label>
          <button type="button" className="btn ghost" onClick={reload} disabled={status === "loading"}>{t("Actualiser")}</button>
          <button type="button" className="btn ghost" onClick={() => void exportAs("xlsx")} disabled={!report || busy !== null}>
            {busy === "xlsx" ? t("Export en cours…") : t("Exporter en Excel")}
          </button>
          <button type="button" className="btn primary" onClick={() => void exportAs("pdf")} disabled={!report || busy !== null}>
            {busy === "pdf" ? t("Export en cours…") : t("Exporter en PDF")}
          </button>
        </div>
      </header>

      {exportError && <p className="error" role="alert">{exportError}</p>}

      <div className="dash">
        {status === "error" && !report && (
          <div className="api-banner" role="alert">
            <span><strong>{t("Le tableau de bord n’a pas pu être chargé.")}</strong> {t(error)}</span>
            <button type="button" className="btn ghost" onClick={reload}>{t("Réessayer")}</button>
          </div>
        )}
        {status === "loading" && !report && <p className="api-loading" role="status">{t("Chargement des données…")}</p>}

        {report && (
          <div className={status === "loading" ? "dash-body is-stale" : "dash-body"} aria-busy={status === "loading"}>
            <Section title="Vue d’ensemble du parc">
              <OverviewChart rows={report.overview} label={f.txt} />
            </Section>

            <Section title="Répartition du parc">
              <div className="dash-grid">
                {pick(report.tables, ["categories", "etats", "ages", "provenances"]).map((tb) => (
                  <Card key={tb.code} wide={!PAIRED.has(tb.code)}><DataTable table={tb} f={f} /></Card>
                ))}
              </div>
            </Section>

            <Section title="Détention et dossiers d’attribution">
              <div className="dash-grid">
                {pick(report.tables, ["services", "dossiers", "detentions"]).map((tb) => (
                  <Card key={tb.code} wide={!PAIRED.has(tb.code)}><DataTable table={tb} f={f} /></Card>
                ))}
              </div>
            </Section>

            <Section title="Consommables et licences">
              <div className="dash-grid">
                {pick(report.tables, ["consommables", "licences", "licences_echeance"]).map((tb) => (
                  <Card key={tb.code} wide={!PAIRED.has(tb.code)}><DataTable table={tb} f={f} /></Card>
                ))}
              </div>
            </Section>

            <Section title="Évolution dans le temps">
              <div className="dash-grid">
                {report.evolution.charts.map((c) => (
                  <Card key={c.code}><TimeChart chart={c} labels={report.evolution.labels} /></Card>
                ))}
              </div>
            </Section>
          </div>
        )}
      </div>
    </>
  );
}

/** Libellé d'une période : « 1 semaine », « 1 mois », « 6 mois »… */
function periodLabel(p: Period, t: (s: string, v?: Record<string, string | number>) => string): string {
  if (p.unit === "days") return p.n === 7 ? t("1 semaine") : t("1 mois");
  return t("{n} mois", { n: p.n });
}

const pick = (tables: DashTable[], codes: string[]) =>
  codes.map((c) => tables.find((x) => x.code === c)).filter((x): x is DashTable => !!x);

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <section className="dash-section">
      <h2>{t(title)}</h2>
      {children}
    </section>
  );
}

function Card({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return <div className={`dash-card${wide ? " wide" : ""}`}>{children}</div>;
}

function DataTable({ table, f }: { table: DashTable; f: Fmt }) {
  const { t } = f;
  const total = table.total;
  return (
    <>
      <h3 className="dash-card-title">{t(table.title)}</h3>
      {table.rows.length === 0 ? (
        <p className="empty">{t("Aucune donnée à afficher.")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table dash-table">
            <thead>
              <tr>{table.columns.map((c) => <th key={c.key} className={c.align === "right" ? "num" : undefined}>{t(c.label)}</th>)}</tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {table.columns.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "num" : undefined}>{f.cell(c.key, r[c.key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
            {total && (
              <tfoot>
                <tr>
                  {table.columns.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "num" : undefined}>
                      {total[c.key] === null || total[c.key] === "" ? "" : f.cell(c.key, total[c.key])}
                    </td>
                  ))}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
      {table.note && <p className="chart-note">{f.txt(table.note)}</p>}
    </>
  );
}
