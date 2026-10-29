import { useI18n } from "../../lib/i18n";
import type { Indicator, Txt } from "../../lib/dashboard";

/** Plus petit « beau » maximum (1, 2, 2,5, 5 × 10^n) supérieur ou égal à la valeur. */
function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(v));
  const f = v / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
}

/** Échelle propre à chaque indicateur : les indicateurs n'ont ni la même unité ni le même ordre de grandeur,
 *  donc chaque barre est projetée sur son propre axe (0 → max). Un pourcentage va toujours de 0 à 100. */
export function scaleOf(i: Indicator): number {
  return i.unit === "%" ? 100 : niceMax(i.value * 1.2);
}

/** Vue d'ensemble : un graphique à barres horizontales, une échelle par indicateur. */
export function OverviewChart({ rows, label }: { rows: Indicator[]; label: (t: Txt) => string }) {
  const { t, lang } = useI18n();
  const locale = lang === "mg" ? "fr" : lang;
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const unit = (i: Indicator) => (i.unit === "%" ? " %" : "");

  return (
    <div className="dash-card">
      <ol className="hbars" aria-label={t("Vue d’ensemble du parc")}>
        {rows.map((r) => {
          const top = scaleOf(r);
          const pct = Math.max(0, Math.min(100, (r.value / top) * 100));
          return (
            <li key={r.code} className="hbar">
              <span className="hbar-label">{label(r.label)}</span>
              <span
                className="hbar-track" role="meter" aria-label={label(r.label)}
                aria-valuemin={0} aria-valuemax={top} aria-valuenow={r.value}
                aria-valuetext={nf.format(r.value) + unit(r)}
              >
                <span className="hbar-fill" style={{ width: `${pct}%` }} />
              </span>
              <strong className="hbar-value">{nf.format(r.value) + unit(r)}</strong>
              <span className="hbar-scale">{t("échelle 0 – {max}", { max: nf.format(top) + unit(r) })}</span>
            </li>
          );
        })}
      </ol>
      <p className="chart-note">{t("Chaque indicateur est tracé sur sa propre échelle (colonne de droite) : la longueur des barres ne se compare pas d’un indicateur à l’autre.")}</p>
    </div>
  );
}
