import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import { Icon } from "../lib/icons";
import { sections } from "../lib/schema";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [closed, setClosed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (window.matchMedia("(max-width: 860px)").matches) setCollapsed(true);
  }, []);

  return (
    <aside className={`sidebar${collapsed ? " is-collapsed" : ""}`}>
      <div className="sidebar-head">
        <span className="brand-mark" aria-hidden="true">PI</span>
        <span className="brand-name label">Parc informatique</span>
        <button
          type="button" className="icon-btn" onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Déplier le menu" : "Replier le menu"} aria-expanded={!collapsed}
          title={collapsed ? "Déplier le menu" : "Replier le menu"}
        >
          <Icon name="panel" />
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Navigation principale">
        {sections.map((section) => {
          const isOpen = collapsed || !closed[section.slug];
          return (
            <div className="nav-section" key={section.slug}>
              <button
                type="button" className="nav-section-title" aria-expanded={isOpen}
                onClick={() => setClosed((c) => ({ ...c, [section.slug]: !c[section.slug] }))}
              >
                <span className="label">{section.label}</span>
                <span className={`chev${isOpen ? " is-open" : ""}`}><Icon name="chevron" size={16} /></span>
              </button>
              {isOpen && (
                <ul>
                  {section.groups.map((g) => (
                    <li key={g.slug}>
                      <NavLink to={`/${section.slug}/${g.slug}`} className="nav-link" title={g.label}>
                        <Icon name={g.icon} />
                        <span className="label">{g.label}</span>
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
