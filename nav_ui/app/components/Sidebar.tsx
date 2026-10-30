import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import { ROLE_LABEL } from "../lib/access";
import { useAuth } from "../lib/auth";
import { Icon } from "../lib/icons";
import { LANGS, useI18n } from "../lib/i18n";
import { useMenu } from "../lib/menu";
import { sections } from "../lib/schema";

export function Sidebar() {
  const { t, lang, setLang } = useI18n();
  const { user, role, canView, has, logout } = useAuth();
  const { groupsOf } = useMenu();
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
        {has("dashboard.voir") && (
          <div className="nav-section">
            <ul>
              <li>
                <NavLink to="/dashboard" end className="nav-link" title={t("Tableau de bord")}>
                  <Icon name="dashboard" />
                  <span className="label">{t("Tableau de bord")}</span>
                </NavLink>
              </li>
            </ul>
          </div>
        )}
        {/* seules les sections autorisées pour le rôle apparaissent (voir lib/access.ts) */}
        {sections.filter((s) => canView(s.slug)).map((section) => {
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
                  {groupsOf(section).map((g) => (
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

      <div className="sidebar-user">
        <NavLink to="/profil" className="user-link" title={t("Mon profil")} aria-label={t("Mon profil")}>
          <Icon name="user" />
          <span className="user-info label">
            <strong>{user?.nom_utilisateur}</strong>
            <small>{role ? t(ROLE_LABEL[role]) : t("Rôle inconnu")}</small>
          </span>
        </NavLink>
        <button
          type="button" className="icon-btn" onClick={logout}
          aria-label={t("Se déconnecter")} title={t("Se déconnecter")}
        >
          <Icon name="logout" />
        </button>
      </div>

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
