import { useState, type FormEvent, type ReactNode } from "react";
import { ApiError } from "../lib/api";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { uiFieldErrors } from "../lib/mapping";
import { matches, showValue, viewOf, type Entity, type Field, type Row } from "../lib/schema";
import { useStore } from "../lib/store";

const today = () => new Date().toISOString().slice(0, 10);

export function CrudPanel({ entity }: { entity: Entity }) {
  const { rows, save, remove, ctx } = useStore();
  const { t } = useI18n();
  const tableRows = rows[entity.table] ?? [];
  const list = tableRows.filter((r) => matches(entity, r));
  const addLabel = t("Ajouter {x}", { x: t(entity.singular) });

  // le champ filtre par l'onglet (ex. categorie_id) est pre-rempli et masque
  const w = entity.where;
  const hiddenName = w && !w.negate ? (w.via?.setField ?? w.field) : null;
  const shown = entity.fields.filter((f) => f.name !== hiddenName);

  const canCreate = !entity.readOnly;
  const canEdit = !entity.readOnly && !entity.immutable;

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null); // id | "new" | null
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState("");
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const q = query.trim().toLowerCase();
  const visible = q
    ? list.filter((r) => shown.some((f) => showValue(f, r[f.name], ctx).toLowerCase().includes(q)))
    : list;

  function blank(): Record<string, string> {
    const v: Record<string, string> = {};
    for (const f of entity.fields) {
      let d = f.default ?? "";
      if (d === "today" || f.auto === "today") d = today();
      if (!d && f.type === "select" && f.required && f.options) d = f.options[0].v;
      v[f.name] = d;
    }
    if (w && !w.negate) {
      if (w.via) {
        const via = w.via;
        v[via.setField] = ctx.rows(via.table).find((r) => r[via.key] === w.value)?.id ?? "";
      } else {
        v[w.field] = w.value;
      }
    }
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
    setFormError("");
    setNotice(message);
  }

  const open = (row: Row) => reset(row.id, draftFrom(row));
  const startNew = () => reset("new", blank());

  /** Erreur renvoyee par l'API : par champ quand c'est possible, sinon message general. */
  function showApiError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setFormError(t("Erreur inattendue."));
      return;
    }
    if (err.network) {
      setFormError(t("Impossible de joindre l’API."));
      return;
    }
    const byField = uiFieldErrors(shown, err.fieldErrors);
    setErrors(byField);
    if (Object.keys(byField).length === 0) setFormError(err.message);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || (selected !== "new" && !canEdit)) return;
    const creating = selected === "new";
    const selfId = creating ? null : selected;
    const errs: Record<string, string> = {};
    setFormError("");

    if (hiddenName && w && !draft[hiddenName]) {
      setFormError(t("Catégorie introuvable : {code}", { code: w.value }));
      return;
    }
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

    setBusy(true);
    try {
      const row = await save(entity.table, draft, selfId ?? undefined);
      reset(row.id, draftFrom(row), creating ? "Élément créé." : "Modifications enregistrées.");
    } catch (err) {
      showApiError(err);
    } finally {
      setBusy(false);
    }
  }

  async function destroy() {
    if (!confirming) return setConfirming(true);
    if (!selected || selected === "new" || busy) return;
    setBusy(true);
    try {
      const refused = await remove(entity.table, selected);
      if (refused) {
        setConfirming(false);
        setFormError(refused);
      } else {
        reset(null, {});
      }
    } catch (err) {
      setConfirming(false);
      showApiError(err);
    } finally {
      setBusy(false);
    }
  }

  const isNew = selected === "new";
  const viewOnly = !isNew && !canEdit;
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
      return (
        <textarea id={id} rows={3} value={value} placeholder={f.placeholder ? t(f.placeholder) : undefined}
          onChange={(e) => set(e.target.value)} {...aria} />
      );
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
          {canCreate && (
            <button type="button" className="add-btn" onClick={startNew} aria-label={addLabel} title={addLabel}>
              <Icon name="plus" />
            </button>
          )}
        </div>
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Filtrer la liste")} aria-label={t("Filtrer la liste")} />
        </label>
        <div className="pane-body">
          {visible.length === 0 ? (
            <p className="empty">
              {list.length > 0
                ? t("Aucun résultat pour ce filtre.")
                : canCreate
                  ? t("Aucun élément pour l’instant. Utilisez le bouton + pour ajouter {x}.", { x: t(entity.singular) })
                  : t("Aucun élément pour l’instant.")}
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
            <p className="empty">
              {t(canCreate
                ? "Sélectionnez un élément dans la liste, ou cliquez sur + pour en créer un."
                : "Sélectionnez un élément dans la liste.")}
            </p>
          </div>
        ) : (
          <form key={selected} className="form" onSubmit={submit} noValidate>
            <div className="pane-head">
              <h2>{heading}</h2>
              <button type="button" className="btn ghost" onClick={() => reset(null, {})}>{t("Fermer")}</button>
            </div>
            <div className="pane-body">
              {viewOnly && <p className="hint view-only">{t("Cet élément ne peut plus être modifié.")}</p>}
              <fieldset className="fieldset" disabled={viewOnly || busy}>
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
                            {f.required && !f.readonly && !viewOnly && <span className="req"> *</span>}
                          </label>
                        )}
                        {control(f, i)}
                        {f.hint && !errors[f.name] && !viewOnly && <p className="hint">{t(f.hint)}</p>}
                        {errors[f.name] && <p className="error" id={`${id}-err`}>{t(errors[f.name])}</p>}
                      </div>
                    );
                  })}
                </div>
              </fieldset>
            </div>
            <div className="form-foot">
              {!viewOnly && (
                <button type="submit" className="btn primary" disabled={busy}>
                  {busy ? t("Enregistrement…") : t(isNew ? "Créer" : "Enregistrer les modifications")}
                </button>
              )}
              {!isNew && canEdit && (
                <button type="button" className={`btn ${confirming ? "danger" : "ghost"}`} onClick={() => void destroy()} disabled={busy}>
                  {t(confirming ? "Confirmer la suppression" : "Supprimer")}
                </button>
              )}
              <span className="notice" role="status">{notice ? t(notice) : ""}</span>
              {formError && <p className="error foot-error" role="alert">{formError}</p>}
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
