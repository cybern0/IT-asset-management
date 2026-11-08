// Global > Matériel : tout le matériel (recherche, filtres) et, pour celui qui est choisi, son parcours (acquisition,
// demandes, signatures, remises, retours, modifications). Le parcours est reconstitué par l'API (GET /tracabilite) :
// rien n'est saisi ici. Le matériel choisi est dans l'adresse (?materiel=ID) : on peut y renvoyer depuis ailleurs.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api, ApiError } from "../lib/api";
import { fmtDate } from "../lib/detention";
import { Icon } from "../lib/icons";
import { useI18n } from "../lib/i18n";
import { useMenu } from "../lib/menu";
import { tone } from "../lib/schema";

type Row = {
  id: number; code_inventaire: string; designation: string; categorie: string; categorie_code: string; statut: string; etat: string;
  marque: string | null; modele: string | null; numero_serie: string | null; localisation: string | null;
  detenteur: string | null; service: string | null; depuis: string | null; nb_detenteurs: number; dernier_mouvement: string | null;
};
type Ev = {
  type: string; date: string; reference?: string | null; type_demande?: string | null; agent?: string | null;
  ancien_agent?: string | null; par?: string | null; signe_par?: string | null; etat?: string | null; motif?: string | null;
  besoin?: string | null; provenance?: string | null; detail?: string | null; accessoires?: string | null;
  observations?: string | null; champs?: string[] | null;
};
type Parcours = {
  materiel: {
    id: number; code_inventaire: string; designation: string; categorie: string; marque: string | null; modele: string | null;
    numero_serie: string | null; statut: string; etat: string; localisation: string | null; date_acquisition: string | null;
    detenteur: string | null; depuis: string | null;
  };
  evenements: Ev[];
};

// libellés = clés de traduction (mêmes valeurs que les listes du dictionnaire)
const STATUT: Record<string, string> = { EN_STOCK: "En stock", ATTRIBUE: "Attribué", EN_MAINTENANCE: "En maintenance", REFORME: "Réformé" };
const ETAT: Record<string, string> = { NEUF: "Neuf", BON: "Bon", A_REPARER: "À réparer", EN_PANNE: "En panne", REFORME: "Réformé" };
const PROVENANCE: Record<string, string> = { ACHAT: "Achat", DOTATION: "Dotation", AFFECTATION: "Affectation", PROJET: "Projet", DON: "Don", AUTRE: "Autre" };

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const fail = (e: unknown, fallback: string, net: string) => (e instanceof ApiError ? (e.network ? net : e.message) : fallback);

/** Couleur du point : entrée du matériel chez un agent / sortie / incident / neutre. */
const kind = (type: string) =>
  type === "REMISE" || type === "AFFECTATION_DIRECTE" ? "in" : type === "RETOUR" ? "out" : type === "REFUS" || type === "ANNULATION" ? "bad" : "neutral";

export function TracabiliteView() {
  const { t } = useI18n();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [statut, setStatut] = useState("");
  const [categorie, setCategorie] = useState("");
  const [detention, setDetention] = useState("");
  const { tabOf } = useMenu();
  const [params, setParams] = useSearchParams();
  const asked = Number(params.get("materiel"));
  const selected: number | null = Number.isInteger(asked) && asked > 0 ? asked : null;
  const setSelected = (id: number | null) => setParams(id === null ? {} : { materiel: String(id) }, { replace: true });
  const [parcours, setParcours] = useState<Parcours | null>(null);
  const [loadingP, setLoadingP] = useState(false);
  const [errorP, setErrorP] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setRows((await api.get("/tracabilite")) as unknown as Row[]); }
    catch (e) { setError(fail(e, t("Erreur inattendue."), t("Impossible de joindre l’API."))); }
    finally { setLoading(false); }
  }, [t]);

  useEffect(() => { void load(); }, [load]);

  // parcours du matériel sélectionné (la réponse d'un clic précédent est ignorée si on a changé de matériel entre-temps)
  useEffect(() => {
    if (selected === null) { setParcours(null); return; }
    let live = true;
    setLoadingP(true);
    setErrorP("");
    api.get(`/tracabilite/${selected}`)
      .then((p) => { if (live) setParcours(p as unknown as Parcours); })
      .catch((e: unknown) => { if (live) { setParcours(null); setErrorP(fail(e, t("Erreur inattendue."), t("Impossible de joindre l’API."))); } })
      .finally(() => { if (live) setLoadingP(false); });
    return () => { live = false; };
  }, [selected, t]);

  const visible = useMemo(() => {
    const q = norm(query.trim());
    return rows.filter((r) => {
      if (statut && r.statut !== statut) return false;
      if (categorie && r.categorie !== categorie) return false;
      if (detention === "DETENU" && !r.detenteur) return false;
      if (detention === "LIBRE" && r.detenteur) return false;
      if (!q) return true;
      return norm(`${r.code_inventaire} ${r.designation} ${r.categorie} ${r.marque ?? ""} ${r.modele ?? ""} ${r.numero_serie ?? ""} ${r.localisation ?? ""} ${r.detenteur ?? ""} ${r.service ?? ""}`).includes(q);
    });
  }, [rows, query, statut, categorie, detention]);
  const categories = useMemo(() => Array.from(new Set(rows.map((r) => r.categorie))).sort((a, b) => a.localeCompare(b)), [rows]);
  const current = rows.find((r) => r.id === selected);
  const fiche = current ? tabOf(current.categorie_code) : null; // onglet Assets qui affiche la categorie du materiel

  return (
    <div className="crud">
      <section className="pane" aria-label={t("Liste : {x}", { x: t("Matériels") })}>
        <div className="pane-head">
          <h2>{t("Matériels")} <span className="count">{visible.length}</span></h2>
        </div>
        <label className="search">
          <Icon name="search" size={16} />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Code, désignation, série, détenteur…")} aria-label={t("Filtrer la liste")} />
        </label>
        <div className="filters tight">
          <select value={statut} onChange={(e) => setStatut(e.target.value)} aria-label={t("Statut")}>
            <option value="">{t("Tous les statuts")}</option>
            {Object.entries(STATUT).map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
          </select>
          <select value={categorie} onChange={(e) => setCategorie(e.target.value)} aria-label={t("Catégorie")}>
            <option value="">{t("Toutes les catégories")}</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={detention} onChange={(e) => setDetention(e.target.value)} aria-label={t("Détention")}>
            <option value="">{t("Détenus et libres")}</option>
            <option value="DETENU">{t("Détenus")}</option>
            <option value="LIBRE">{t("Libres")}</option>
          </select>
          <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>{t("Actualiser")}</button>
        </div>
        <div className="pane-body">
          {error ? <p className="error pad" role="alert">{error}</p>
            : loading && rows.length === 0 ? <p className="empty">{t("Chargement…")}</p>
            : visible.length === 0 ? (
              <p className="empty">{rows.length > 0 ? t("Aucun résultat pour ce filtre.") : t("Aucun matériel enregistré pour l’instant.")}</p>
            ) : (
              <ul className="items">
                {visible.map((r) => (
                  <li key={r.id}>
                    <button type="button" className="item" aria-current={selected === r.id} onClick={() => setSelected(r.id)}>
                      <span className="item-main">
                        <span className="item-title">{r.designation}</span>
                        <span className="item-sub">
                          {r.code_inventaire} · {r.detenteur ?? t("Aucun détenteur")}
                        </span>
                      </span>
                      <span className="badges">
                        <span className="badge" data-tone={tone(STATUT[r.statut] ?? r.statut)}>{t(STATUT[r.statut] ?? r.statut)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
        </div>
      </section>

      <section className="pane" aria-label={t("Détail")}>
        {selected === null ? (
          <div className="pane-body">
            <p className="empty">{t("Sélectionnez un matériel dans la liste pour voir son parcours.")}</p>
          </div>
        ) : (
          <div className="form" key={selected}>
            <div className="pane-head">
              <h2>{parcours ? parcours.materiel.code_inventaire : t("Parcours")}</h2>
              <span className="head-actions">
                {fiche && <Link className="btn ghost" to={`/assets/${fiche.groupSlug}/${fiche.key}`}>{t("Ouvrir la fiche")}</Link>}
                <button type="button" className="btn ghost" onClick={() => setSelected(null)}>{t("Fermer")}</button>
              </span>
            </div>
            <div className="pane-body">
              {errorP ? <p className="error pad" role="alert">{errorP}</p>
                : loadingP || !parcours ? <p className="empty">{t("Chargement…")}</p>
                : <ParcoursDetail p={parcours} />}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ParcoursDetail({ p }: { p: Parcours }) {
  const { t } = useI18n();
  const m = p.materiel;
  const dash = "—";
  return (
    <div className="pad">
      <h3 className="tl-head">{m.designation}</h3>
      <dl className="facts">
        <div><dt>{t("Catégorie")}</dt><dd>{m.categorie}</dd></div>
        <div><dt>{t("Marque / modèle")}</dt><dd>{[m.marque, m.modele].filter(Boolean).join(" ") || dash}</dd></div>
        <div><dt>{t("N° de série")}</dt><dd>{m.numero_serie ?? dash}</dd></div>
        <div><dt>{t("Statut")}</dt><dd>{t(STATUT[m.statut] ?? m.statut)}</dd></div>
        <div><dt>{t("État")}</dt><dd>{t(ETAT[m.etat] ?? m.etat)}</dd></div>
        <div><dt>{t("Localisation")}</dt><dd>{m.localisation ?? dash}</dd></div>
        <div>
          <dt>{t("Détenteur actuel")}</dt>
          <dd>{m.detenteur ? `${m.detenteur} (${t("depuis le {x}", { x: fmtDate(m.depuis) })})` : t("Aucun détenteur")}</dd>
        </div>
      </dl>

      <h3 className="tl-head">{t("Parcours")} <span className="count">{p.evenements.length}</span></h3>
      {p.evenements.length === 0 ? <p className="empty">{t("Aucun événement enregistré pour ce matériel.")}</p> : (
        <ol className="tl">
          {p.evenements.map((e, i) => <Event key={`${e.type}-${e.date}-${i}`} e={e} />)}
        </ol>
      )}
    </div>
  );
}

function Event({ e }: { e: Ev }) {
  const { t } = useI18n();
  const who = e.agent ?? dash;
  const demande = e.type_demande === "AFFECTATION" ? t("Demande d’affectation") : t("Demande d’attribution");
  const title: Record<string, string> = {
    ACQUISITION: t("Acquisition du matériel"),
    ENREGISTREMENT: t("Enregistré dans le parc"),
    DEMANDE: demande,
    APPROBATION: t("Demande approuvée par le dépositaire comptable"),
    SIGNATURE_AGENT: t("Fiche signée par l’agent"),
    SIGNATURE_CHEF: t("Fiche signée par le chef de service"),
    SIGNATURE: t("Fiche de détention signée"),
    REMISE: t("Matériel remis à {x}", { x: who }),
    AFFECTATION_DIRECTE: t("Matériel affecté à {x}", { x: who }),
    RETOUR: t("Matériel rendu par {x}", { x: who }),
    RECEPTION: t("Réception approuvée"),
    REFUS: t("Demande refusée"),
    ANNULATION: t("Demande annulée"),
    MODIFICATION: t("Fiche du matériel modifiée"),
  };
  // ligne de détail : seules les informations présentes sont affichées
  const sub = [
    e.type === "DEMANDE" && e.agent ? t("Pour {x}", { x: e.agent }) : null,
    e.type === "REMISE" && e.ancien_agent ? t("Repris de {x}", { x: e.ancien_agent }) : null,
    e.type === "ACQUISITION" && e.provenance ? t(PROVENANCE[e.provenance] ?? e.provenance) : null,
    e.detail,
    e.type === "SIGNATURE_CHEF" && e.signe_par ? e.signe_par : null,
    e.etat ? `${t("État")} : ${t(ETAT[e.etat] ?? e.etat)}` : null,
    e.accessoires,
    e.motif ? `${t("Motif")} : ${e.motif}` : null,
    e.champs && e.champs.length > 0 ? e.champs.join(", ") : null,
    e.observations,
    e.reference,
    e.par ? t("Par {x}", { x: e.par }) : null,
  ].filter(Boolean);
  return (
    <li className="tl-item" data-kind={kind(e.type)}>
      <span className="tl-date">{fmtDate(e.date)}</span>
      <span className="tl-title">{title[e.type] ?? e.type}</span>
      {sub.length > 0 && <span className="tl-sub">{sub.join(" · ")}</span>}
    </li>
  );
}

const dash = "—";
