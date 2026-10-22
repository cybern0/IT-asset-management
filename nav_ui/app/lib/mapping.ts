// Conversion entre les lignes de l'UI (tout en chaines) et le JSON de l'API (types natifs)
import type { Field, FieldType, Row } from "./schema";
import type { FieldError, Json } from "./api";

const isBool = (f: Field) =>
  f.type === "select" && !!f.options?.length && f.options.every((o) => o.v === "true" || o.v === "false");

function text(v: unknown, type?: FieldType): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  const s = String(v);
  return type === "date" && s.length > 10 ? s.slice(0, 10) : s; // horodatage -> date
}

/** Ligne de l'API -> ligne de l'UI. Les champs inconnus (ex. categorie_code) sont conserves. */
export function fromApi(fields: Field[], json: Json): Row {
  const row: Record<string, string> = {};
  for (const [k, v] of Object.entries(json)) row[k] = text(v);
  for (const f of fields) {
    const value = json[f.api ?? f.name];
    if (f.type === "password") row[f.name] = ""; // jamais renvoye par l'API
    else if (f.type === "multiref") row[f.name] = Array.isArray(value) ? value.join(",") : "";
    else row[f.name] = text(value, f.type);
  }
  row.id = String(json.id);
  return row as Row;
}

/** Brouillon du formulaire -> corps JSON. Champs calcules (cree_le...) exclus, vide -> null. */
export function toApi(fields: Field[], draft: Record<string, string>): Json {
  const body: Json = {};
  for (const f of fields) {
    if (f.readonly || f.auto) continue;
    const raw = (draft[f.name] ?? "").trim();
    const key = f.api ?? f.name;
    if (f.type === "password") {
      if (raw) body[key] = raw; // vide = mot de passe inchange
    } else if (f.type === "multiref") {
      body[key] = raw ? raw.split(",").map(Number) : [];
    } else if (f.type === "number" || f.type === "ref") {
      body[key] = raw === "" ? null : Number(raw);
    } else if (isBool(f)) {
      body[key] = raw === "true";
    } else {
      body[key] = raw === "" ? null : raw;
    }
  }
  return body;
}

/** Erreurs par champ de l'API -> noms de champs de l'UI. */
export function uiFieldErrors(fields: Field[], errors: FieldError[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const e of errors) {
    const f = fields.find((x) => (x.api ?? x.name) === e.field);
    if (f && !out[f.name]) out[f.name] = e.message;
  }
  return out;
}
