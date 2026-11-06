import { Navigate, NavLink, useLocation, useParams } from "react-router";
import { AttributionsView } from "../components/AttributionsView";
import { CrudPanel } from "../components/CrudPanel";
import { DemandesView } from "../components/DemandesView";
import { GlobalView } from "../components/GlobalView";
import { RepartitionView } from "../components/RepartitionView";
import { TracabiliteView } from "../components/TracabiliteView";
import { useI18n } from "../lib/i18n";
import { useMenu } from "../lib/menu";
import { rowsFor, sections } from "../lib/schema";
import { useStore } from "../lib/store";
import NotFound from "./notfound";

export default function Module() {
  const { group, tab } = useParams();
  const { pathname } = useLocation();
  const { rows } = useStore();
  const { t } = useI18n();
  const { ready, entitiesOf } = useMenu();

  // les categories (qui decident des onglets affiches) viennent de la base : on attend leur chargement
  if (!ready) return <p className="api-loading" role="status">{t("Chargement…")}</p>;

  const section = sections.find((s) => pathname.startsWith(`/${s.slug}/`));
  const g = section?.groups.find((x) => x.slug === group);
  if (!section || !g) return <NotFound />;

  // seuls les onglets du dictionnaire dont la categorie est affichee en base ont une route
  const visible = entitiesOf(g);
  const entity = visible.find((e) => e.key === tab);
  if (g.kind !== "global" && !entity) {
    if (visible.length === 0) return <NotFound />;
    return <Navigate to={`/${section.slug}/${g.slug}/${visible[0].key}`} replace />;
  }

  return (
    <>
      <header className="page-head">
        <p className="crumb">{t(section.label)}</p>
        <h1>{t(g.label)}</h1>
        <p className="lede">{t(g.description)}</p>
      </header>

      {g.kind === "global" ? (
        <GlobalView tab={tab} />
      ) : (
        <>
          {visible.length > 1 && (
            <nav className="tabs" aria-label={t("Rubriques de {x}", { x: t(g.label) })}>
              {visible.map((e) => (
                <NavLink key={e.key} to={`/${section.slug}/${g.slug}/${e.key}`} className="tab">
                  {t(e.label)}
                  {!e.custom && <span className="count">{rowsFor(e, rows).length}</span>}
                </NavLink>
              ))}
            </nav>
          )}
          {entity?.local && (
            <p className="local-note">
              {t("Cette rubrique n’existe pas encore dans parc.sql : les champs sont provisoires.")}
            </p>
          )}
          {entity?.custom === "attributions" && <AttributionsView />}
          {entity?.custom === "demandes" && <DemandesView />}
          {entity?.custom === "repartition" && <RepartitionView />}
          {entity?.custom === "tracabilite" && <TracabiliteView />}
          {entity && !entity.custom && <CrudPanel key={entity.key} entity={entity} />}
        </>
      )}
    </>
  );
}
