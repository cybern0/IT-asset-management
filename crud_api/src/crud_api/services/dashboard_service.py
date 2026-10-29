# Tableau de bord : indicateurs, tableaux, alertes et series temporelles
#
# `load()` lit la base (une requete par table), `compute()` est une fonction pure :
# elle ne touche pas a la base, donc facile a tester et reutilisee telle quelle par les exports PDF / Excel.
#
# Les textes dynamiques sont renvoyes sous la forme {"t": "modele {n}", "p": {"n": 3}} : l'interface
# les traduit avec son dictionnaire, les exports (francais) font simplement modele.format(**p).
from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud_api.config import Settings, get_settings
from crud_api.models import (
    Affectation, Agent, ArticleConsommable, CategorieMateriel, Direction, FicheDetention, Licence, Logiciel,
    Materiel, MouvementConsommable, Service, StockConsommable,
)

Data = dict[str, list[dict[str, Any]]]
Report = dict[str, Any]

MOIS_MIN, MOIS_MAX, MOIS_DEFAUT = 3, 36, 12
JOURS_MIN, JOURS_MAX = 2, 62  # evolution courte : un point par jour (1 semaine = 7, 1 mois = 30)
STATUTS = ["EN_STOCK", "ATTRIBUE", "EN_MAINTENANCE", "REFORME"]
ETATS = [("NEUF", "Neuf"), ("BON", "Bon"), ("A_REPARER", "À réparer"), ("EN_PANNE", "En panne"), ("REFORME", "Réformé")]
PROVENANCES = [
    ("ACHAT", "Achat"), ("DOTATION", "Dotation"), ("AFFECTATION", "Affectation"),
    ("PROJET", "Projet"), ("DON", "Don"), ("AUTRE", "Autre"),
]
TYPES_LICENCE = [("PERPETUELLE", "Perpétuelle"), ("ABONNEMENT", "Abonnement"), ("SANS_LICENCE", "Sans licence")]
PRIORITE_ORDRE = {"Haute": 0, "Moyenne": 1, "Basse": 2}


# ----------------------------------------------------------------- lecture
def _rows(result) -> list[dict[str, Any]]:
    return [dict(r) for r in result.mappings().all()]


async def load(db: AsyncSession) -> Data:
    """Charge les donnees brutes necessaires au calcul (colonnes utiles seulement)."""
    m = Materiel
    return {
        "categories": _rows(await db.execute(select(CategorieMateriel.id, CategorieMateriel.libelle))),
        "materiels": _rows(await db.execute(select(
            m.id, m.code_inventaire, m.designation, m.categorie_id, m.etat, m.statut, m.provenance,
            m.date_acquisition, m.valeur_acquisition, m.cree_le,
        ))),
        "affectations": _rows(await db.execute(select(
            Affectation.id, Affectation.materiel_id, Affectation.agent_id, Affectation.date_remise,
            Affectation.date_retour,
        ))),
        "agents": _rows(await db.execute(select(Agent.id, Agent.nom, Agent.prenom, Agent.service_id))),
        "services": _rows(await db.execute(select(Service.id, Service.nom, Service.direction_id))),
        "directions": _rows(await db.execute(select(Direction.id, Direction.nom))),
        "fiches": _rows(await db.execute(select(
            FicheDetention.id, FicheDetention.valide_par, FicheDetention.materiel_id,
            FicheDetention.affectation_id, FicheDetention.statut, FicheDetention.cloture,
            FicheDetention.date_demande, FicheDetention.date_signature, FicheDetention.date_remise,
        ))),
        "articles": _rows(await db.execute(select(
            ArticleConsommable.id, ArticleConsommable.designation, ArticleConsommable.unite,
            ArticleConsommable.seuil_alerte, ArticleConsommable.actif,
        ))),
        "stocks": _rows(await db.execute(select(StockConsommable.article_id, StockConsommable.quantite))),
        "mouvements": _rows(await db.execute(select(
            MouvementConsommable.type_mouvement, MouvementConsommable.quantite, MouvementConsommable.cree_le,
        ))),
        "logiciels": _rows(await db.execute(select(Logiciel.id, Logiciel.nom, Logiciel.type_licence))),
        "licences": _rows(await db.execute(select(
            Licence.logiciel_id, Licence.nombre_postes, Licence.date_expiration,
        ))),
    }


# ----------------------------------------------------------------- utilitaires
def _day(v: Any) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v


def _msg(template: str, **params: Any) -> dict[str, Any]:
    return {"t": template, "p": params}


def _num(v: Any) -> float:
    return float(v) if v is not None else 0.0


def _round(v: float, n: int = 1) -> float:
    return round(v + 0.0, n)


def _month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def _month_list(today: date, n: int) -> list[tuple[int, int]]:
    """Les n derniers mois, du plus ancien au mois courant."""
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _table(code: str, title: str, columns: list[tuple[str, str]], rows: list[dict], *,
           total: dict | None = None, note: str | None = None, align: dict[str, str] | None = None) -> dict:
    """Tableau generique : l'interface et les exports le dessinent sans connaitre son contenu."""
    return {
        "code": code,
        "title": title,
        "columns": [{"key": k, "label": label, "align": (align or {}).get(k, "left" if i == 0 else "right")}
                    for i, (k, label) in enumerate(columns)],
        "rows": rows,
        "total": total,
        "note": note,
    }


def _statut(ok: bool) -> tuple[str, str]:
    return ("OK", "ok") if ok else ("Alerte", "bad")


# ----------------------------------------------------------------- calcul
def compute(data: Data, today: date, months: int = MOIS_DEFAUT, cfg: Settings | None = None,
            days: int | None = None) -> Report:
    """`days` : evolution sur les n derniers jours (un point par jour) ; sinon sur `months` mois (un point par mois)."""
    cfg = cfg or get_settings()
    months = max(MOIS_MIN, min(MOIS_MAX, months))
    if days is not None:
        days = max(JOURS_MIN, min(JOURS_MAX, days))

    cat_label = {c["id"]: c["libelle"] for c in data["categories"]}
    agents = {a["id"]: a for a in data["agents"]}
    services = {s["id"]: s for s in data["services"]}
    directions = {d["id"]: d["nom"] for d in data["directions"]}
    materiels = data["materiels"]
    by_id = {x["id"]: x for x in materiels}
    affectations = data["affectations"]
    active_aff = [a for a in affectations if a["date_retour"] is None]

    for x in materiels:  # date de reference pour l'age : acquisition, a defaut creation de la fiche
        x["_acq"] = _day(x["date_acquisition"]) or _day(x["cree_le"])
        x["_age"] = (today - x["_acq"]).days / 365.25 if x["_acq"] else None

    total = len(materiels)
    count = {s: sum(1 for x in materiels if x["statut"] == s) for s in STATUTS}
    actifs = [x for x in materiels if x["statut"] != "REFORME"]  # parc actif : hors reformes
    taux = _round(100 * count["ATTRIBUE"] / len(actifs)) if actifs else 0.0
    ages = [x["_age"] for x in actifs if x["_age"] is not None]
    age_moyen = _round(sum(ages) / len(ages)) if ages else 0.0
    anciens = sum(1 for a in ages if a > cfg.age_ancien_ans)
    valeur = sum(_num(x["valeur_acquisition"]) for x in materiels)

    # ---- vue d'ensemble : indicateur / valeur / objectif / ecart / statut
    tmin, tmax = cfg.objectif_attribution_min, cfg.objectif_attribution_max
    overview = []

    def line(code, label, value, unit, objective, ecart, ok):
        row = {"code": code, "label": label, "value": value, "unit": unit, "objective": objective, "ecart": ecart}
        if ok is None:
            row.update(statut="—", tone="none")
        else:
            row["statut"], row["tone"] = _statut(ok)
        overview.append(row)

    line("total", "Total équipements", total, "", None, None, None)
    line("attribution", "Taux d’attribution", taux, "%",
         {"op": "between", "min": tmin, "max": tmax}, _round(taux - (tmin + tmax) / 2), tmin <= taux <= tmax)
    line("stock", "Stock disponible", count["EN_STOCK"], "",
         {"op": ">=", "value": cfg.objectif_stock_min}, count["EN_STOCK"] - cfg.objectif_stock_min,
         count["EN_STOCK"] >= cfg.objectif_stock_min)
    line("maintenance", "Équipements en maintenance", count["EN_MAINTENANCE"], "",
         {"op": "<=", "value": cfg.objectif_maintenance_max}, count["EN_MAINTENANCE"] - cfg.objectif_maintenance_max,
         count["EN_MAINTENANCE"] <= cfg.objectif_maintenance_max)
    line("age_moyen", "Âge moyen du parc (ans)", age_moyen, "",
         {"op": "<=", "value": cfg.objectif_age_moyen_max}, _round(age_moyen - cfg.objectif_age_moyen_max),
         age_moyen <= cfg.objectif_age_moyen_max)
    line("anciens", _msg("Équipements > {ans} ans", ans=cfg.age_ancien_ans), anciens, "",
         {"op": "<=", "value": cfg.objectif_anciens_max}, anciens - cfg.objectif_anciens_max,
         anciens <= cfg.objectif_anciens_max)
    line("attribues", "Équipements attribués", count["ATTRIBUE"], "", None, None, None)
    line("valeur", "Valeur d’acquisition du parc", _round(valeur, 0), "", None, None, None)

    tables: list[dict] = []

    # ---- repartition par categorie
    rows = []
    for cid in sorted({x["categorie_id"] for x in materiels}, key=lambda c: cat_label.get(c, "")):
        grp = [x for x in materiels if x["categorie_id"] == cid]
        rows.append({
            "categorie": cat_label.get(cid, "—"), "total": len(grp),
            **{k: sum(1 for x in grp if x["statut"] == s)
               for k, s in (("attribue", "ATTRIBUE"), ("stock", "EN_STOCK"),
                            ("maintenance", "EN_MAINTENANCE"), ("hors_service", "REFORME"))},
        })
    rows.sort(key=lambda r: -r["total"])
    tables.append(_table(
        "categories", "Répartition par catégorie",
        [("categorie", "Catégorie"), ("total", "Total"), ("attribue", "Attribué"), ("stock", "En stock"),
         ("maintenance", "Maintenance"), ("hors_service", "Hors service")],
        rows,
        total={"categorie": "Total", "total": total, "attribue": count["ATTRIBUE"], "stock": count["EN_STOCK"],
               "maintenance": count["EN_MAINTENANCE"], "hors_service": count["REFORME"]},
        note="Hors service = matériel réformé.",
    ))

    # ---- etat physique
    rows = []
    for code, label in ETATS:
        grp = [x for x in materiels if x["etat"] == code]
        rows.append({"etat": label, "nombre": len(grp), "part": _round(100 * len(grp) / total) if total else 0.0,
                     "valeur": _round(sum(_num(x["valeur_acquisition"]) for x in grp), 0)})
    tables.append(_table("etats", "Répartition par état",
                         [("etat", "État"), ("nombre", "Nombre"), ("part", "Part (%)"), ("valeur", "Valeur d’acquisition")],
                         rows, total={"etat": "Total", "nombre": total, "part": 100.0 if total else 0.0,
                                      "valeur": _round(valeur, 0)}))

    # ---- age du parc actif
    tranches = [("Moins de 1 an", 0, 1), ("1 à 3 ans", 1, 3), ("3 à 5 ans", 3, 5), ("Plus de 5 ans", 5, math.inf)]
    rows = []
    for label, lo, hi in tranches:
        n = sum(1 for a in ages if lo <= a < hi)
        rows.append({"tranche": label, "nombre": n, "part": _round(100 * n / len(actifs)) if actifs else 0.0})
    n_sans = sum(1 for x in actifs if x["_age"] is None)
    if n_sans:
        rows.append({"tranche": "Date inconnue", "nombre": n_sans, "part": _round(100 * n_sans / len(actifs))})
    tables.append(_table("ages", "Âge du parc actif", [("tranche", "Tranche d’âge"), ("nombre", "Nombre"), ("part", "Part (%)")],
                         rows, note="Parc actif = matériel non réformé. Âge calculé depuis la date d’acquisition."))

    # ---- provenance
    rows = []
    for code, label in PROVENANCES:
        grp = [x for x in materiels if x["provenance"] == code]
        if grp:
            rows.append({"provenance": label, "nombre": len(grp),
                         "valeur": _round(sum(_num(x["valeur_acquisition"]) for x in grp), 0)})
    tables.append(_table("provenances", "Provenance du matériel",
                         [("provenance", "Provenance"), ("nombre", "Nombre"), ("valeur", "Valeur d’acquisition")], rows))

    # ---- detention par service
    per_service: dict[int | None, dict] = {}
    for a in active_aff:
        ag = agents.get(a["agent_id"])
        sid = ag["service_id"] if ag else None
        e = per_service.setdefault(sid, {"equipements": 0, "agents": set()})
        e["equipements"] += 1
        e["agents"].add(a["agent_id"])
    rows = []
    for sid, e in per_service.items():
        sv = services.get(sid)
        rows.append({"service": sv["nom"] if sv else "Sans service",
                     "direction": directions.get(sv["direction_id"], "—") if sv else "—",
                     "agents": len(e["agents"]), "equipements": e["equipements"]})
    rows.sort(key=lambda r: (-r["equipements"], r["service"]))
    tables.append(_table("services", "Matériel détenu par service",
                         [("service", "Service"), ("direction", "Direction"), ("agents", "Agents équipés"),
                          ("equipements", "Équipements détenus")],
                         rows[:20], align={"direction": "left"},
                         total={"service": "Total", "direction": "", "agents": len({a["agent_id"] for a in active_aff}),
                                "equipements": len(active_aff)},
                         note=("20 premiers services." if len(rows) > 20 else None)))

    # ---- detentions les plus anciennes
    rows = []
    for a in sorted(active_aff, key=lambda a: a["date_remise"])[:10]:
        x, ag = by_id.get(a["materiel_id"]), agents.get(a["agent_id"])
        rows.append({"code": x["code_inventaire"] if x else "—", "designation": x["designation"] if x else "—",
                     "agent": f"{ag['prenom']} {ag['nom']}" if ag else "—",
                     "depuis": a["date_remise"].isoformat(), "jours": (today - a["date_remise"]).days})
    tables.append(_table("detentions", "Détentions les plus anciennes",
                         [("code", "Code d’inventaire"), ("designation", "Désignation"), ("agent", "Agent"),
                          ("depuis", "Depuis le"), ("jours", "Jours")],
                         rows, align={"designation": "left", "agent": "left", "depuis": "left"}))

    # ---- dossiers d'attribution (processus en 6 etapes)
    def etape(f: dict) -> str:
        if f["cloture"]:
            return "Refusé" if f["cloture"] == "REFUSEE" else "Annulé"
        if f["affectation_id"]:
            return "Terminé (matériel attribué)"
        if not f["valide_par"]:
            return "1 · En attente de validation"
        if f["materiel_id"] is None:
            return "2 · Équipement à sélectionner"
        if f["statut"] != "SIGNEE":
            return "4 · En attente de signature"
        return "5 · Remise à faire"

    ordre = ["1 · En attente de validation", "2 · Équipement à sélectionner", "4 · En attente de signature",
             "5 · Remise à faire", "Terminé (matériel attribué)", "Refusé", "Annulé"]
    rows, fiches = [], data["fiches"]
    for label in ordre:
        grp = [f for f in fiches if etape(f) == label]
        if not grp:
            continue
        open_ = label[0].isdigit()
        jours = [(today - _day(f["date_demande"])).days for f in grp if f["date_demande"]]
        rows.append({"etape": label, "nombre": len(grp),
                     "anciennete": _round(sum(jours) / len(jours)) if jours and open_ else None})
    remises = [(f["date_remise"] - f["date_demande"]).days for f in fiches
               if f["affectation_id"] and f["date_remise"] and f["date_demande"]]
    tables.append(_table("dossiers", "Dossiers d’attribution par étape",
                         [("etape", "Étape"), ("nombre", "Dossiers"), ("anciennete", "Ancienneté moyenne (jours)")],
                         rows, total={"etape": "Total", "nombre": len(fiches), "anciennete": None},
                         note=(_msg("Délai moyen demande → remise : {n} jours.", n=_round(sum(remises) / len(remises)))
                               if remises else None)))
    en_retard = [f for f in fiches if etape(f)[0].isdigit() and f["date_demande"]
                 and (today - _day(f["date_demande"])).days > cfg.dossier_retard_jours]

    # ---- consommables sous le seuil d'alerte
    stock_by_article: dict[int, float] = {}
    for s in data["stocks"]:
        stock_by_article[s["article_id"]] = stock_by_article.get(s["article_id"], 0.0) + _num(s["quantite"])
    low = []
    for art in data["articles"]:
        if not art["actif"]:
            continue
        qte, seuil = stock_by_article.get(art["id"], 0.0), _num(art["seuil_alerte"])
        if qte <= seuil and seuil > 0:
            low.append({"article": art["designation"], "unite": art["unite"], "stock": _round(qte, 3),
                        "seuil": _round(seuil, 3), "manque": _round(seuil - qte, 3)})
    low.sort(key=lambda r: -r["manque"])
    tables.append(_table("consommables", "Consommables sous le seuil d’alerte",
                         [("article", "Article"), ("unite", "Unité"), ("stock", "Stock total"),
                          ("seuil", "Seuil"), ("manque", "Manque")],
                         low[:15], align={"unite": "left"},
                         note=("15 premiers articles." if len(low) > 15 else None)))

    # ---- licences
    soft = {s["id"]: s for s in data["logiciels"]}
    rows = []
    for code, label in TYPES_LICENCE:
        ids = {s["id"] for s in data["logiciels"] if s["type_licence"] == code}
        lic = [l for l in data["licences"] if l["logiciel_id"] in ids]
        rows.append({"type": label, "logiciels": len(ids), "licences": len(lic),
                     "postes": sum(l["nombre_postes"] for l in lic),
                     "expirees": sum(1 for l in lic if l["date_expiration"] and l["date_expiration"] < today)})
    tables.append(_table("licences", "Logiciels et licences",
                         [("type", "Type de licence"), ("logiciels", "Logiciels"), ("licences", "Licences"),
                          ("postes", "Postes couverts"), ("expirees", "Expirées")], rows))
    horizon = cfg.licence_alerte_jours
    expirantes = sorted(
        (l for l in data["licences"] if l["date_expiration"] and (l["date_expiration"] - today).days <= horizon),
        key=lambda l: l["date_expiration"])
    rows = [{"logiciel": soft[l["logiciel_id"]]["nom"] if l["logiciel_id"] in soft else "—",
             "postes": l["nombre_postes"], "expiration": l["date_expiration"].isoformat(),
             "jours": (l["date_expiration"] - today).days} for l in expirantes[:15]]
    tables.append(_table("licences_echeance", "Licences expirées ou bientôt expirées",
                         [("logiciel", "Logiciel"), ("postes", "Postes"), ("expiration", "Expiration"), ("jours", "Jours restants")],
                         rows, align={"expiration": "left"},
                         note=_msg("Échéance dans {n} jours ou moins ; un nombre négatif indique une licence expirée.", n=horizon)))

    # ---- alertes et actions recommandees
    alerts: list[dict] = []

    def alert(prio: str, message: dict, action: dict):
        alerts.append({"priorite": prio, "alerte": message, "action": action})

    by_code = {r["code"]: r for r in overview}
    if by_code["anciens"]["tone"] == "bad":
        alert("Haute", _msg("Équipements de plus de {ans} ans : {n}", n=anciens, ans=cfg.age_ancien_ans),
              _msg("Planifier le renouvellement {a}-{b}", a=str(today.year), b=str(today.year + 1)))
    if by_code["attribution"]["tone"] == "bad":
        alert("Moyenne" if taux > tmax else "Haute",
              _msg("Taux d’attribution de {n} % hors de la cible ({lo}-{hi} %)", n=taux, lo=tmin, hi=tmax),
              _msg("Réaffecter le matériel disponible") if taux < tmin else _msg("Prévoir du matériel supplémentaire"))
    if by_code["maintenance"]["tone"] == "bad":
        alert("Haute", _msg("Équipements en maintenance : {n} (objectif ≤ {max})",
                            n=count["EN_MAINTENANCE"], max=cfg.objectif_maintenance_max),
              _msg("Accélérer les réparations ou remplacer les équipements"))
    elif count["EN_MAINTENANCE"]:
        alert("Basse", _msg("Équipements en maintenance : {n}", n=count["EN_MAINTENANCE"]),
              _msg("Suivre les délais de réparation"))
    if by_code["stock"]["tone"] == "bad":
        alert("Moyenne", _msg("Stock disponible faible ({n}, objectif ≥ {min})", n=count["EN_STOCK"], min=cfg.objectif_stock_min),
              _msg("Commander du matériel pour reconstituer le stock"))
    for r in tables[0]["rows"]:  # stock faible par categorie
        if r["total"] >= 5 and r["stock"] < r["total"] * cfg.stock_categorie_alerte_pct / 100:
            cible = math.ceil(r["total"] * cfg.stock_categorie_cible_pct / 100) - r["stock"]
            alert("Moyenne", _msg("Stock faible : {cat} ({n} en stock)", cat=r["categorie"], n=r["stock"]),
                  _msg("Commander {n} unités de sécurité", n=cible))
    hs = [x for x in materiels if x["etat"] in ("EN_PANNE", "A_REPARER") and x["statut"] in ("EN_STOCK", "ATTRIBUE")]
    if hs:
        alert("Moyenne", _msg("Équipements en panne ou à réparer, hors maintenance : {n}", n=len(hs)),
              _msg("Les passer en maintenance ou les réformer"))
    if en_retard:
        alert("Moyenne", _msg("Dossiers d’attribution ouverts depuis plus de {j} jours : {n}", n=len(en_retard), j=cfg.dossier_retard_jours),
              _msg("Relancer les validations, signatures et remises en attente"))
    expirees = [l for l in expirantes if l["date_expiration"] < today]
    if expirees:
        alert("Haute", _msg("Licences expirées : {n}", n=len(expirees)), _msg("Renouveler ou retirer les logiciels concernés"))
    if len(expirantes) - len(expirees):
        alert("Moyenne", _msg("Licences expirant d’ici {j} jours : {n}", n=len(expirantes) - len(expirees), j=horizon),
              _msg("Préparer le renouvellement"))
    if low:
        alert("Moyenne", _msg("Consommables sous le seuil d’alerte : {n}", n=len(low)), _msg("Réapprovisionner les articles concernés"))
    alerts.sort(key=lambda a: PRIORITE_ORDRE[a["priorite"]])

    # ---- evolution : les seules donnees representees par des graphiques
    if days:  # un point par jour, du plus ancien a aujourd'hui
        ends = [today - timedelta(days=days - 1 - i) for i in range(days)]
        labels = [e.isoformat() for e in ends]

        def bucket(d: date) -> str:
            return d.isoformat()

        per, fin = "par jour", "fin de journée"
    else:  # un point par mois, du plus ancien au mois courant
        mois = _month_list(today, months)
        labels = [f"{y}-{m:02d}" for y, m in mois]
        ends = [_month_end(y, m) for y, m in mois]

        def bucket(d: date) -> str:
            return f"{d.year}-{d.month:02d}"

        per, fin = "par mois", "fin de mois"

    def per_month(dates: list[date | None]) -> list[int]:
        c = {lab: 0 for lab in labels}
        for d in dates:
            if d and bucket(d) in c:
                c[bucket(d)] += 1
        return [c[lab] for lab in labels]

    parc_fin = [sum(1 for x in materiels if x["_acq"] and x["_acq"] <= e) for e in ends]
    actives_fin = [sum(1 for a in affectations if a["date_remise"] <= e and (a["date_retour"] is None or a["date_retour"] > e))
                   for e in ends]
    taux_fin = [_round(100 * a / p) if p else 0.0 for a, p in zip(actives_fin, parc_fin)]
    mv = data["mouvements"]

    def qty(kind: str) -> list[float]:
        c = {lab: 0.0 for lab in labels}
        for x in mv:
            d = _day(x["cree_le"])
            if x["type_mouvement"] == kind and d and bucket(d) in c:
                c[bucket(d)] += _num(x["quantite"])
        return [_round(c[lab], 3) for lab in labels]

    charts = [
        {"code": "parc", "title": "Évolution du parc", "kind": "line", "unit": "",
         "note": f"Équipements acquis, cumul en {fin}.",
         "series": [{"name": "Équipements", "values": parc_fin}, {"name": "Équipements attribués", "values": actives_fin}]},
        {"code": "taux", "title": "Taux d’attribution", "kind": "line", "unit": "%", "band": [tmin, tmax],
         "note": "Reconstitué à partir des dates de remise et de retour ; la bande indique l’objectif.",
         "series": [{"name": "Taux d’attribution", "values": taux_fin}]},
        {"code": "affectations", "title": f"Affectations et retours {per}", "kind": "bar", "unit": "",
         "series": [{"name": "Affectations", "values": per_month([a["date_remise"] for a in affectations])},
                    {"name": "Retours", "values": per_month([a["date_retour"] for a in affectations])}]},
        {"code": "dossiers", "title": f"Dossiers d’attribution {per}", "kind": "bar", "unit": "",
         "series": [{"name": "Demandes", "values": per_month([_day(f["date_demande"]) for f in fiches])},
                    {"name": "Signatures", "values": per_month([_day(f["date_signature"]) for f in fiches])},
                    {"name": "Remises", "values": per_month([_day(f["date_remise"]) for f in fiches])}]},
        {"code": "mouvements", "title": f"Mouvements de consommables {per}", "kind": "line", "unit": "",
         "note": "Quantités entrées et sorties.",
         "series": [{"name": "Entrées", "values": qty("ENTREE")}, {"name": "Sorties", "values": qty("SORTIE")}]},
    ]

    return {
        "generated_at": today.isoformat(),
        "months": None if days else months,
        "days": days,
        "overview": overview,
        "tables": tables,
        "alerts": alerts,
        "evolution": {"labels": labels, "charts": charts},
    }


async def build(db: AsyncSession, months: int = MOIS_DEFAUT, days: int | None = None) -> Report:
    return compute(await load(db), date.today(), months, days=days)


def fmt(cell: Any) -> str:
    """Texte francais d'une cellule : valeur simple ou {"t": modele, "p": parametres}."""
    if isinstance(cell, dict) and "t" in cell:
        return cell["t"].format(**{k: _fr_num(v) for k, v in cell["p"].items()})
    return "" if cell is None else _fr_num(cell) if isinstance(cell, (int, float)) else str(cell)


def _fr_num(v: Any) -> Any:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", "\u00a0")
    return f"{v:,.1f}".replace(",", "\u00a0").replace(".", ",")
