import {
  createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState, type ReactNode,
} from "react";
import { canReadTable } from "./access";
import { api, ApiError } from "./api";
import { useAuth } from "./auth";
import { useI18n } from "./i18n";
import { fromApi, toApi } from "./mapping";
import {
  allEntities, fieldsOfTable, isRemote, refreshAfter, tableEndpoint, tableLabel, type Ctx, type Row,
} from "./schema";

export type { Row };
type State = Record<string, Row[]>;
type Action =
  | { type: "set"; table: string; rows: Row[] }
  | { type: "save"; table: string; row: Row }
  | { type: "remove"; table: string; id: string };

export type Status = "loading" | "ready" | "error";

const remoteTables = Object.keys(tableEndpoint);

/** Tables absentes de l'API (rubriques provisoires) : donnees d'exemple en memoire. */
function init(): State {
  const state: State = {};
  for (const e of allEntities) {
    state[e.table] ??= [];
    if (isRemote(e.table)) continue; // les autres viennent de l'API
    (e.seed ?? []).forEach((v, i) => {
      state[e.table].push({ ...v, id: v.id ?? `${e.key}-seed-${i}` });
    });
  }
  return state;
}

function reducer(state: State, action: Action): State {
  const list = state[action.table] ?? [];
  if (action.type === "set") return { ...state, [action.table]: action.rows };
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
  status: Status;
  reload: () => Promise<void>;
  /** Recharge quelques tables depuis l'API (ex. apres un envoi d'image). */
  refresh: (tables: string[]) => Promise<void>;
  /** Cree (sans id) ou modifie (avec id). Leve ApiError si l'API refuse. */
  save: (table: string, values: Record<string, string>, id?: string) => Promise<Row>;
  /** Retourne un message si la suppression est refusee (ex. element utilise ailleurs), sinon null. */
  remove: (table: string, id: string) => Promise<string | null>;
};

const StoreCtx = createContext<Store | null>(null);
const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [rows, dispatch] = useReducer(reducer, undefined, init);
  const [status, setStatus] = useState<Status>("loading");
  const { t } = useI18n();
  const { role } = useAuth();

  /** Recharge des tables depuis l'API (seulement celles que le role a le droit de lire). Retourne le nombre d'echecs. */
  const loadTables = useCallback(async (tables: string[]): Promise<number> => {
    const allowed = tables.filter((table) => role !== null && canReadTable(role, table));
    const results = await Promise.allSettled(
      allowed.map(async (table) => {
        const data = await api.list(tableEndpoint[table]);
        const fields = fieldsOfTable(table);
        dispatch({ type: "set", table, rows: data.map((j) => fromApi(fields, j)) });
      }),
    );
    return results.filter((r) => r.status === "rejected").length;
  }, [role]);

  const reload = useCallback(async () => {
    setStatus("loading");
    setStatus((await loadTables(remoteTables)) > 0 ? "error" : "ready");
  }, [loadTables]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo<Store>(() => {
    const find = (table: string, id: string) => rows[table]?.find((r) => r.id === id);
    const ctx: Ctx = {
      find,
      t,
      rows: (table) => rows[table] ?? [],
      label: (table, id) => {
        const r = find(table, id);
        return r ? (tableLabel[table]?.(r) ?? r.id) : "";
      },
    };
    const refresh = (table: string) => {
      // effets de bord cote serveur + nouvelle ligne du journal d'audit
      void loadTables([...(refreshAfter[table] ?? []), "journal_audit"]);
    };

    return {
      rows,
      ctx,
      status,
      reload,
      async refresh(tables) {
        await loadTables(tables.filter(isRemote));
      },
      async save(table, values, id) {
        if (!isRemote(table)) {
          const row: Row = { ...values, id: id ?? newId() };
          dispatch({ type: "save", table, row });
          return row;
        }
        const fields = fieldsOfTable(table);
        const body = toApi(fields, values);
        const json = id
          ? await api.update(tableEndpoint[table], id, body)
          : await api.create(tableEndpoint[table], body);
        const row = fromApi(fields, json);
        dispatch({ type: "save", table, row });
        refresh(table);
        return row;
      },
      async remove(table, id) {
        if (isRemote(table)) {
          try {
            await api.remove(tableEndpoint[table], id);
          } catch (err) {
            if (err instanceof ApiError && err.status >= 400 && err.status < 500) return err.message;
            throw err;
          }
          refresh(table);
        }
        dispatch({ type: "remove", table, id });
        return null;
      },
    };
  }, [rows, status, t, reload, loadTables]);

  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}

export function useStore(): Store {
  const v = useContext(StoreCtx);
  if (!v) throw new Error("useStore doit être utilisé sous <StoreProvider>");
  return v;
}
