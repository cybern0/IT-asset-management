import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { assetEntities, categoryTab, showValue, viewOf } from "../lib/schema";
import { useStore } from "../lib/store";

const entity = assetEntities.find((a) => a.entity.table === "materiel")!.entity;

export function GlobalView() {
  const { rows, ctx } = useStore();
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const items = (rows.materiel ?? [])
    .map((r) => {
      const v = viewOf(entity, r, ctx);
      const tab = categoryTab[r.categorie_id];
      return {
        id: r.id,
        type: ctx.label("categorie_materiel", r.categorie_id) || t("Sans catégorie"),
        to: tab ? `/assets/${tab.groupSlug}/${tab.key}` : null,
        ...v,
        haystack: entity.fields.map((f) => showValue(f, r[f.name], ctx)).join(" ").toLowerCase(),
      };
    })
    .filter((i) => !q || i.haystack.includes(q));

  return (
    <section className="pane global">
      <label className="search">
        <Icon name="search" size={16} />
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder={t("Rechercher dans tout le matériel")} aria-label={t("Rechercher dans tout le matériel")} />
      </label>
      <div className="pane-body">
        {items.length === 0 ? (
          <p className="empty">{t("Aucun matériel ne correspond.")}</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("Catégorie")}</th><th>{t("Désignation")}</th>
                <th>{t("Code d’inventaire")}</th><th>{t("Statut")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td>{i.to ? <Link to={i.to}>{i.type}</Link> : i.type}</td>
                  <td>{i.title}</td>
                  <td>{i.sub}</td>
                  <td>{i.badge && <span className="badge" data-tone={i.tone}>{i.badge}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
