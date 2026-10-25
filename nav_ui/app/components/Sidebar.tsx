import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import { Icon } from "../lib/icons";
import { LANGS, useI18n } from "../lib/i18n";
import { sections } from "../lib/schema";

export function Sidebar() {
  const { t, lang, setLang } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const [closed, setClosed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (window.matchMedia("(max-width: 860px)").matches) setCollapsed(true);
  }, []);

  const toggleLabel = t(collapsed ? "Déplier le menu" : "Replier le menu");

  return (
    <aside className={`sidebar${collapsed ? " is-collapsed" : ""}`}>
      <div className="sidebar-head">
        <span className="brand-mark" aria-hidden="true">PI</span>
        <span className="brand-name label">{t("Parc informatique")}</span>
        <button
          type="button" className="icon-btn" onClick={() => setCollapsed((c) => !c)}
          aria-label={toggleLabel} aria-expanded={!collapsed} title={toggleLabel}
        >
          <Icon name="panel" />
        </button>
      </div>

      <nav className="sidebar-nav" aria-label={t("Navigation principale")}>
        <div className="nav-section">
          <ul>
            <li>
              <NavLink to="/dashboard" className="nav-link" title={t("Tableau de bord")}>
                <Icon name="dashboard" />
                <span className="label">{t("Tableau de bord")}</span>
              </NavLink>
            </li>
          </ul>
        </div>
        {sections.map((section) => {
          const isOpen = collapsed || !closed[section.slug];
          return (
            <div className="nav-section" key={section.slug}>
              <button
                type="button" className="nav-section-title" aria-expanded={isOpen}
                onClick={() => setClosed((c) => ({ ...c, [section.slug]: !c[section.slug] }))}
              >
                <span className="label">{t(section.label)}</span>
                <span className={`chev${isOpen ? " is-open" : ""}`}><Icon name="chevron" size={16} /></span>
              </button>
              {isOpen && (
                <ul>
                  {section.groups.map((g) => (
                    <li key={g.slug}>
                      <NavLink to={`/${section.slug}/${g.slug}`} className="nav-link" title={t(g.label)}>
                        <Icon name={g.icon} />
                        <span className="label">{t(g.label)}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-foot" role="group" aria-label={t("Langue")}>
        {LANGS.map((l) => (
          <button
            key={l.code} type="button" className="lang-btn" aria-pressed={lang === l.code}
            title={l.name} aria-label={l.name} lang={l.code} onClick={() => setLang(l.code)}
          >
            {l.code.toUpperCase()}
          </button>
        ))}
      </div>
    </aside>
  );
}
