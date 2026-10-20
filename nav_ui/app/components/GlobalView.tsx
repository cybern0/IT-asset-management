import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../lib/icons";
import { assetEntities, categoryTab, showValue, tone, viewOf } from "../lib/schema";
import { useStore } from "../lib/store";

const entity = assetEntities.find((a) => a.entity.table === "materiel")!.entity;

export function GlobalView() {
  const { rows, ctx } = useStore();
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const items = (rows.materiel ?? [])
    .map((r) => {
      const v = viewOf(entity, r, ctx);
      const tab = categoryTab[r.categorie_id];
      return {
        id: r.id,
        type: ctx.label("categorie_materiel", r.categorie_id) || "Sans catégorie",
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
          placeholder="Rechercher dans tout le matériel" aria-label="Rechercher dans tout le matériel" />
      </label>
      <div className="pane-body">
        {items.length === 0 ? (
          <p className="empty">Aucun matériel ne correspond.</p>
        ) : (
          <table className="table">
            <thead><tr><th>Catégorie</th><th>Désignation</th><th>Code d’inventaire</th><th>Statut</th></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td>{i.to ? <Link to={i.to}>{i.type}</Link> : i.type}</td>
                  <td>{i.title}</td>
                  <td>{i.sub}</td>
                  <td>{i.badge && <span className="badge" data-tone={tone(i.badge)}>{i.badge}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
