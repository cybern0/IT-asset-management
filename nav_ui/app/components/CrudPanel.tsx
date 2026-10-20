import { useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { matches, showValue, viewOf, type Entity, type Field, type Row } from "../lib/schema";
import { useStore } from "../lib/store";

const MASK = "••••••••";
const today = () => new Date().toISOString().slice(0, 10);

export function CrudPanel({ entity }: { entity: Entity }) {
  const { rows, save, remove, ctx } = useStore();
  const { t } = useI18n();
  const addLabel = t("Ajouter {x}", { x: t(entity.singular) });
  const tableRows = rows[entity.table] ?? [];
  const list = tableRows.filter((r) => matches(entity, r));
  // le champ filtré par l'onglet (ex. categorie_id) est pré-rempli et masqué
  const hiddenName = entity.where && !entity.where.negate ? entity.where.field : null;
  const shown = entity.fields.filter((f) => f.name !== hiddenName);

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null); // id | "new" | null
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState("");
  const [deleteError, setDeleteError] = useState("");

  const q = query.trim().toLowerCase();
  const visible = q
    ? list.filter((r) =>
        shown.some((f) => showValue(f, r[f.name], ctx).toLowerCase().includes(q)))
    : list;

  function blank(): Record<string, string> {
    const v: Record<string, string> = {};
    for (const f of entity.fields) {
      let d = f.default ?? "";
      if (d === "today" || f.auto === "today") d = today();
      if (!d && f.type === "select" && f.required && f.options) d = f.options[0].v;
      v[f.name] = d;
    }
    if (entity.where && !entity.where.negate) v[entity.where.field] = entity.where.value;
    return v;
  }

  function draftFrom(row: Row): Record<string, string> {
    const v: Record<string, string> = { ...row };
    for (const f of entity.fields) if (f.type === "password") v[f.name] = "";
    return v;
  }

  function reset(next: string | null, values: Record<string, string>, message = "") {
    setSelected(next);
    setDraft(values);
    setErrors({});
    setConfirming(false);
    setDeleteError("");
    setNotice(message);
  }

  const open = (row: Row) => reset(row.id, draftFrom(row));
  const startNew = () => reset("new", blank());

  function submit(e: FormEvent) {
    e.preventDefault();
    const creating = selected === "new";
    const selfId = creating ? null : selected;
    const errs: Record<string, string> = {};

    for (const f of shown) {
      if (f.readonly) continue;
      const v = (draft[f.name] ?? "").trim();
      if (f.required && !v && !(f.type === "password" && !creating)) errs[f.name] = t("Ce champ est obligatoire.");
      if (v && f.unique && tableRows.some((r) => r.id !== selfId && (r[f.name] ?? "").toLowerCase() === v.toLowerCase()))
        errs[f.name] = t("Cette valeur existe déjà.");
      if (v && f.type === "number") {
        const n = Number(v);
        if (Number.isNaN(n)) errs[f.name] = t("Nombre invalide.");
        else if (f.min !== undefined && n < f.min) errs[f.name] = t("Doit être au moins {n}.", { n: f.min });
        else if (f.gt !== undefined && n <= f.gt) errs[f.name] = t("Doit être supérieur à {n}.", { n: f.gt });
      }
    }
    const extra = entity.validate?.(draft, { rows: tableRows, selfId, ctx }) ?? {};
    for (const k of Object.keys(extra)) if (!errs[k]) errs[k] = extra[k];
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const values: Record<string, string> = { ...draft };
    for (const f of entity.fields) {
      if (f.type !== "password") continue;
      const typed = (draft[f.name] ?? "").trim();
      values[f.name] = typed ? MASK : creating ? "" : (tableRows.find((r) => r.id === selfId)?.[f.name] ?? "");
    }
    const row = save(entity.table, values, creating ? undefined : (selfId ?? undefined));
    reset(row.id, draftFrom(row), creating ? "Élément créé." : "Modifications enregistrées.");
  }

  function destroy() {
    if (!confirming) return setConfirming(true);
    if (!selected || selected === "new") return;
    const err = remove(entity.table, selected);
    if (err) {
      setConfirming(false);
      setDeleteError(err);
      return;
    }
    reset(null, {});
  }

  const isNew = selected === "new";
  const heading = isNew ? t("Nouvel élément") : viewOf(entity, { ...draft, id: selected ?? "" }, ctx).title;

  function control(f: Field, i: number): ReactNode {
    const id = `${entity.key}-${f.name}`;
    const value = draft[f.name] ?? "";
    const set = (val: string) => setDraft((d) => ({ ...d, [f.name]: val }));
    const aria = {
      "aria-invalid": !!errors[f.name],
      "aria-describedby": errors[f.name] ? `${id}-err` : undefined,
    };

    if (f.readonly) {
      return <input id={id} type="text" value={value} placeholder={t("Automatique")} readOnly />;
    }
    if (f.type === "multiref" && f.ref) {
      const table = f.ref;
      const refRows = ctx.rows(table);
      const chosen = new Set(value.split(",").filter((x) => x && ctx.find(table, x)));
      return (
        <div className="checks" role="group" aria-labelledby={`${id}-lbl`}>
          {refRows.length === 0 ? (
            <p className="hint">{t("Aucune entrée disponible. Créez-en d’abord dans l’onglet correspondant.")}</p>
          ) : (
            refRows.map((r) => (
              <label key={r.id}>
                <input
                  type="checkbox" checked={chosen.has(r.id)}
                  onChange={(e) => {
                    const next = new Set(chosen);
                    if (e.target.checked) next.add(r.id); else next.delete(r.id);
                    set([...next].join(","));
                  }}
                />
                {ctx.label(table, r.id)}
              </label>
            ))
          )}
        </div>
      );
    }
    if (f.type === "ref" && f.ref) {
      const table = f.ref;
      return (
        <select id={id} value={value} onChange={(e) => set(e.target.value)} {...aria}>
          <option value="">{f.required ? t("Choisir…") : "—"}</option>
          {ctx.rows(table).map((r) => <option key={r.id} value={r.id}>{ctx.label(table, r.id)}</option>)}
        </select>
      );
    }
    if (f.type === "select") {
      return (
        <select id={id} value={value} onChange={(e) => set(e.target.value)} {...aria}>
          {!f.required && <option value="">—</option>}
          {f.options?.map((o) => <option key={o.v} value={o.v}>{t(o.l)}</option>)}
        </select>
      );
    }
    if (f.type === "textarea") {
      return <textarea id={id} rows={3} value={value} placeholder={f.placeholder ? t(f.placeholder) : undefined} onChange={(e) => set(e.target.value)} {...aria} />;
    }
    return (
      <input
        id={id} type={f.type} value={value} placeholder={f.placeholder ? t(f.placeholder) : undefined}
        autoComplete={f.type === "password" ? "new-password" : undefined}
        step={f.type === "number" ? "any" : undefined}
        autoFocus={isNew && i === 0}
        onChange={(e) => set(e.target.value)} {...aria}
      />
    );
  }

  return (
    <div className="crud">
      {/* ---- liste scrollable + bouton plus ---- */}
      <section className="pane" aria-label={t("Liste : {x}", { x: t(entity.label) })}>
        <div className="pane-head">
          <h2>{t(entity.label)} <span className="count">{list.length}</span></h2>
          <button type="button" className="add-btn" onClick={startNew}
            aria-label={addLabel} title={addLabel}>
            <Icon name="plus" />
          </button>
        </div>
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Filtrer la liste")} aria-label={t("Filtrer la liste")} />
        </label>
        <div className="pane-body">
          {visible.length === 0 ? (
            <p className="empty">
              {list.length === 0
                ? t("Aucun élément pour l’instant. Utilisez le bouton + pour ajouter {x}.", { x: t(entity.singular) })
                : t("Aucun résultat pour ce filtre.")}
            </p>
          ) : (
            <ul className="items">
              {visible.map((r) => {
                const { title, sub, badge, tone } = viewOf(entity, r, ctx);
                return (
                  <li key={r.id}>
                    <button type="button" className="item" aria-current={selected === r.id} onClick={() => open(r)}>
                      <span className="item-main">
                        <span className="item-title">{title}</span>
                        {sub && <span className="item-sub">{sub}</span>}
                      </span>
                      {badge && <span className="badge" data-tone={tone}>{badge}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {/* ---- formulaire ---- */}
      <section className="pane" aria-label={t("Détail")}>
        {selected === null ? (
          <div className="pane-body">
            <p className="empty">{t("Sélectionnez un élément dans la liste, ou cliquez sur + pour en créer un.")}</p>
          </div>
        ) : (
          <form key={selected} className="form" onSubmit={submit} noValidate>
            <div className="pane-head">
              <h2>{heading}</h2>
              <button type="button" className="btn ghost" onClick={() => reset(null, {})}>{t("Fermer")}</button>
            </div>
            <div className="pane-body">
              <div className="grid">
                {shown.map((f, i) => {
                  const id = `${entity.key}-${f.name}`;
                  const wide = f.type === "textarea" || f.type === "multiref";
                  return (
                    <div key={f.name} className={`field${wide ? " wide" : ""}`}>
                      {f.type === "multiref" ? (
                        <span className="lbl" id={`${id}-lbl`}>{t(f.label)}</span>
                      ) : (
                        <label htmlFor={id}>
                          {t(f.label)}
                          {f.required && !f.readonly && <span className="req"> *</span>}
                        </label>
                      )}
                      {control(f, i)}
                      {f.hint && !errors[f.name] && <p className="hint">{t(f.hint)}</p>}
                      {errors[f.name] && <p className="error" id={`${id}-err`}>{t(errors[f.name])}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="form-foot">
              <button type="submit" className="btn primary">{t(isNew ? "Créer" : "Enregistrer les modifications")}</button>
              {!isNew && (
                <button type="button" className={`btn ${confirming ? "danger" : "ghost"}`} onClick={destroy}>
                  {t(confirming ? "Confirmer la suppression" : "Supprimer")}
                </button>
              )}
              <span className="notice" role="status">{notice ? t(notice) : ""}</span>
              {deleteError && <p className="error foot-error" role="alert">{deleteError}</p>}
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
