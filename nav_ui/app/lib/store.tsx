import { createContext, useContext, useMemo, useReducer, type ReactNode } from "react";
import { allEntities, tableLabel, type Ctx, type Row } from "./schema";

export type { Row };
type State = Record<string, Row[]>;
type Action =
  | { type: "save"; table: string; row: Row }
  | { type: "remove"; table: string; id: string };

/** Les lignes sont rangées par table SQL ; plusieurs onglets peuvent partager une table. */
function init(): State {
  const state: State = {};
  for (const e of allEntities) {
    state[e.table] ??= [];
    const preset = e.where && !e.where.negate ? { [e.where.field]: e.where.value } : {};
    (e.seed ?? []).forEach((v, i) => {
      state[e.table].push({ ...preset, ...v, id: v.id ?? `${e.key}-seed-${i}` });
    });
  }
  return state;
}

function reducer(state: State, action: Action): State {
  const list = state[action.table] ?? [];
  if (action.type === "remove") {
    return { ...state, [action.table]: list.filter((r) => r.id !== action.id) };
  }
  const exists = list.some((r) => r.id === action.row.id);
  const next = exists ? list.map((r) => (r.id === action.row.id ? action.row : r)) : [action.row, ...list];
  return { ...state, [action.table]: next };
}

type Store = {
  rows: State;
  ctx: Ctx;
  save: (table: string, values: Record<string, string>, id?: string) => Row;
  /** Retourne un message d'erreur si la suppression est refusée (clé étrangère), sinon null. */
  remove: (table: string, id: string) => string | null;
};

const StoreCtx = createContext<Store | null>(null);
const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [rows, dispatch] = useReducer(reducer, undefined, init);

  const value = useMemo<Store>(() => {
    const find = (table: string, id: string) => rows[table]?.find((r) => r.id === id);
    const ctx: Ctx = {
      find,
      rows: (table) => rows[table] ?? [],
      label: (table, id) => {
        const r = find(table, id);
        return r ? (tableLabel[table]?.(r) ?? r.id) : "";
      },
    };
    return {
      rows,
      ctx,
      save(table, values, id) {
        const row: Row = { ...values, id: id ?? newId() };
        dispatch({ type: "save", table, row });
        return row;
      },
      remove(table, id) {
        // équivalent de ON DELETE RESTRICT sur les clés étrangères
        const seen = new Set<string>();
        const used: string[] = [];
        let total = 0;
        for (const e of allEntities) {
          for (const f of e.fields) {
            const k = `${e.table}.${f.name}`;
            if (f.type !== "ref" || f.ref !== table || seen.has(k)) continue;
            seen.add(k);
            const n = (rows[e.table] ?? []).filter((r) => r[f.name] === id).length;
            if (n > 0) { total += n; used.push(e.table); }
          }
        }
        if (total > 0) {
          return `Suppression impossible : cet élément est utilisé par ${total} enregistrement(s) (${used.join(", ")}).`;
        }
        dispatch({ type: "remove", table, id });
        return null;
      },
    };
  }, [rows]);

  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}

export function useStore(): Store {
  const v = useContext(StoreCtx);
  if (!v) throw new Error("useStore doit être utilisé sous <StoreProvider>");
  return v;
}
