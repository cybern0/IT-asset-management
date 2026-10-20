import { Navigate, NavLink, useLocation, useParams } from "react-router";
import { CrudPanel } from "../components/CrudPanel";
import { GlobalView } from "../components/GlobalView";
import { useI18n } from "../lib/i18n";
import { rowsFor, sections } from "../lib/schema";
import { useStore } from "../lib/store";
import NotFound from "./notfound";

export default function Module() {
  const { group, tab } = useParams();
  const { pathname } = useLocation();
  const { rows } = useStore();
  const { t } = useI18n();

  const section = sections.find((s) => pathname.startsWith(`/${s.slug}/`));
  const g = section?.groups.find((x) => x.slug === group);
  if (!section || !g) return <NotFound />;

  const entity = g.entities.find((e) => e.key === tab);
  if (g.kind !== "global" && !entity) {
    return <Navigate to={`/${section.slug}/${g.slug}/${g.entities[0].key}`} replace />;
  }

  return (
    <>
      <header className="page-head">
        <p className="crumb">{t(section.label)}</p>
        <h1>{t(g.label)}</h1>
        <p className="lede">{t(g.description)}</p>
      </header>

      {g.kind === "global" ? (
        <GlobalView />
      ) : (
        <>
          {g.entities.length > 1 && (
            <nav className="tabs" aria-label={t("Rubriques de {x}", { x: t(g.label) })}>
              {g.entities.map((e) => (
                <NavLink key={e.key} to={`/${section.slug}/${g.slug}/${e.key}`} className="tab">
                  {t(e.label)}
                  <span className="count">{rowsFor(e, rows).length}</span>
                </NavLink>
              ))}
            </nav>
          )}
          {entity?.local && (
            <p className="local-note">
              {t("Cette rubrique n’existe pas encore dans parc.sql : les champs sont provisoires.")}
            </p>
          )}
          {entity && <CrudPanel key={entity.key} entity={entity} />}
        </>
      )}
    </>
  );
}
