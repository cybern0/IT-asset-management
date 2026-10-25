import { useI18n } from "../../lib/i18n";
import type { Chart } from "../../lib/dashboard";

const W = 640, H = 250;
const M = { top: 12, right: 14, bottom: 30, left: 46 };
const PW = W - M.left - M.right;
const PH = H - M.top - M.bottom;

/** Plus petit « beau » maximum (1, 2, 2,5, 5 × 10^n) supérieur ou égal à la valeur. */
function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(v));
  const f = v / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
}

/** Graphique d'évolution (courbes ou barres groupées). Réservé aux données temporelles. */
export function TimeChart({ chart, labels }: { chart: Chart; labels: string[] }) {
  const { t, lang } = useI18n();
  const locale = lang === "mg" ? "fr" : lang;
  const num = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const month = (iso: string, long = false) => {
    const [y, m] = iso.split("-").map(Number);
    return new Date(y, m - 1, 1).toLocaleDateString(locale, { month: "short", year: long ? "numeric" : "2-digit" });
  };

  const n = labels.length;
  const all = chart.series.flatMap((s) => s.values);
  const top = chart.unit === "%" ? 100 : niceMax(Math.max(0, ...all, chart.band?.[1] ?? 0));
  const y = (v: number) => M.top + PH - (v / top) * PH;
  const ticks = [0, 1, 2, 3, 4].map((i) => (top * i) / 4);
  const labelStep = Math.max(1, Math.ceil(n / 8));
  const slot = PW / n;
  const x = (i: number) => (chart.kind === "bar" ? M.left + slot * (i + 0.5) : M.left + (n === 1 ? PW / 2 : (PW * i) / (n - 1)));
  const barW = (slot * 0.76) / chart.series.length;
  const dots = n <= 18;
  const unit = chart.unit ? ` ${chart.unit}` : "";

  return (
    <figure className="chart">
      <figcaption>
        <h3>{t(chart.title)}</h3>
        <ul className="legend" aria-label={t("Légende")}>
          {chart.series.map((s, i) => (
            <li key={s.name}><span className={`swatch s${i}`} aria-hidden="true" />{t(s.name)}</li>
          ))}
          {chart.band && (
            <li><span className="swatch band" aria-hidden="true" />{t("Objectif")}</li>
          )}
        </ul>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t(chart.title)} className="chart-svg">
        {chart.band && (
          <rect className="chart-band" x={M.left} width={PW} y={y(chart.band[1])} height={y(chart.band[0]) - y(chart.band[1])} />
        )}
        {ticks.map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} />
            <text className="chart-tick" x={M.left - 6} y={y(v) + 4} textAnchor="end">{num.format(v)}</text>
          </g>
        ))}
        {labels.map((lab, i) =>
          i % labelStep === 0 ? (
            <text key={lab} className="chart-tick" x={x(i)} y={H - 10} textAnchor="middle">{month(lab)}</text>
          ) : null,
        )}

        {chart.kind === "bar"
          ? chart.series.map((s, si) =>
              s.values.map((v, i) => (
                <rect
                  key={`${s.name}-${i}`} className={`bar s${si}`}
                  x={x(i) - (barW * chart.series.length) / 2 + si * barW} width={Math.max(1, barW - 1)}
                  y={y(v)} height={Math.max(0, y(0) - y(v))}
                >
                  <title>{`${t(s.name)} · ${month(labels[i], true)} : ${num.format(v)}${unit}`}</title>
                </rect>
              )),
            )
          : chart.series.map((s, si) => (
              <g key={s.name} className={`line s${si}`}>
                <polyline points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
                {dots && s.values.map((v, i) => (
                  <circle key={i} cx={x(i)} cy={y(v)} r={3.2}>
                    <title>{`${t(s.name)} · ${month(labels[i], true)} : ${num.format(v)}${unit}`}</title>
                  </circle>
                ))}
              </g>
            ))}
      </svg>
      {chart.note && <p className="chart-note">{t(chart.note)}</p>}
    </figure>
  );
}
