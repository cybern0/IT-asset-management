"""Tableau de bord : calcul pur (sans base) et exports. Ne necessite pas TEST_DATABASE_URL."""
from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from crud_api.config import Settings
from crud_api.services import dashboard_export, dashboard_service as ds

pytestmark = pytest.mark.nodb

TODAY = date(2026, 10, 25)
CFG = Settings(objectif_stock_min=2, objectif_maintenance_max=1, objectif_anciens_max=0, age_ancien_ans=5)


def mat(i, statut, cat=1, etat="BON", acq=date(2025, 1, 10)):
    return {"id": i, "code_inventaire": f"EQ-{i}", "designation": f"Eq {i}", "categorie_id": cat, "etat": etat,
            "statut": statut, "provenance": "ACHAT", "date_acquisition": acq, "valeur_acquisition": 100,
            "cree_le": datetime(2025, 1, 10)}


def sample():
    return {
        "categories": [{"id": 1, "libelle": "Ordinateur"}, {"id": 2, "libelle": "Écran"}],
        "materiels": [
            mat(1, "ATTRIBUE"), mat(2, "ATTRIBUE", acq=date(2019, 5, 1)), mat(3, "EN_STOCK"),
            mat(4, "EN_MAINTENANCE", etat="EN_PANNE"), mat(5, "REFORME", cat=2, acq=date(2015, 1, 1)),
        ],
        "affectations": [
            {"id": 1, "materiel_id": 1, "agent_id": 1, "date_remise": date(2026, 8, 3), "date_retour": None},
            {"id": 2, "materiel_id": 2, "agent_id": 1, "date_remise": date(2026, 9, 1), "date_retour": None},
            {"id": 3, "materiel_id": 3, "agent_id": 1, "date_remise": date(2026, 7, 1), "date_retour": date(2026, 7, 20)},
        ],
        "agents": [{"id": 1, "nom": "Rakoto", "prenom": "Jean", "service_id": 1}],
        "services": [{"id": 1, "nom": "Informatique", "direction_id": 1}],
        "directions": [{"id": 1, "nom": "Direction générale"}],
        "fiches": [{"id": 1, "valide_par": None, "materiel_id": None, "affectation_id": None, "statut": "NON_SIGNEE",
                    "cloture": None, "date_demande": date(2026, 8, 1), "date_signature": None, "date_remise": None}],
        "articles": [{"id": 1, "designation": "Toner", "unite": "unité", "seuil_alerte": 5, "actif": True}],
        "stocks": [{"article_id": 1, "quantite": 2}],
        "mouvements": [{"type_mouvement": "ENTREE", "quantite": 10, "cree_le": datetime(2026, 10, 2)},
                       {"type_mouvement": "SORTIE", "quantite": 4, "cree_le": datetime(2026, 10, 9)}],
        "logiciels": [{"id": 1, "nom": "Office", "type_licence": "ABONNEMENT"}],
        "licences": [{"logiciel_id": 1, "nombre_postes": 5, "date_expiration": date(2026, 10, 1)}],
    }


def test_overview_values_and_status():
    r = ds.compute(sample(), TODAY, 12, CFG)
    o = {x["code"]: x for x in r["overview"]}
    assert o["total"]["value"] == 5
    assert o["attribution"]["value"] == 50.0  # 2 attribues / 4 equipements actifs (hors reformes)
    assert o["attribution"]["tone"] == "bad" and o["attribution"]["ecart"] == -30.0
    assert o["stock"]["value"] == 1 and o["stock"]["tone"] == "bad"
    assert o["maintenance"]["tone"] == "ok"
    assert o["anciens"]["value"] == 1  # le reforme de 2015 n'est pas compte
    assert ds.fmt(o["anciens"]["label"]) == "Équipements > 5 ans"


def test_category_table_adds_up():
    r = ds.compute(sample(), TODAY, 12, CFG)
    cat = next(t for t in r["tables"] if t["code"] == "categories")
    assert cat["total"]["total"] == sum(x["total"] for x in cat["rows"]) == 5
    for x in cat["rows"]:
        assert x["total"] == x["attribue"] + x["stock"] + x["maintenance"] + x["hors_service"]


def test_alerts_sorted_by_priority_and_translatable():
    r = ds.compute(sample(), TODAY, 12, CFG)
    prios = [a["priorite"] for a in r["alerts"]]
    assert prios == sorted(prios, key=ds.PRIORITE_ORDRE.get) and "Haute" in prios
    for a in r["alerts"]:  # modele + parametres : l'interface traduit le modele
        assert set(a["alerte"]) == {"t", "p"} and "{" not in ds.fmt(a["alerte"])


def test_evolution_series_cover_requested_months():
    r = ds.compute(sample(), TODAY, 6, CFG)
    ev = r["evolution"]
    assert ev["labels"] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    for c in ev["charts"]:
        for s in c["series"]:
            assert len(s["values"]) == 6
    aff = next(c for c in ev["charts"] if c["code"] == "affectations")
    assert aff["series"][0]["values"] == [0, 0, 1, 1, 1, 0] and aff["series"][1]["values"] == [0, 0, 1, 0, 0, 0]
    mouv = next(c for c in ev["charts"] if c["code"] == "mouvements")
    assert mouv["series"][0]["values"][-1] == 10 and mouv["series"][1]["values"][-1] == 4


def test_empty_database_does_not_crash():
    empty = {k: [] for k in sample()}
    r = ds.compute(empty, TODAY, 12, CFG)
    assert r["overview"][0]["value"] == 0
    assert dashboard_export.build_pdf(r)[:4] == b"%PDF"
    assert load_workbook(BytesIO(dashboard_export.build_xlsx(r))).sheetnames


def test_exports():
    r = ds.compute(sample(), TODAY, 12, CFG)
    assert dashboard_export.build_pdf(r)[:4] == b"%PDF"
    wb = load_workbook(BytesIO(dashboard_export.build_xlsx(r)))
    assert {"Synthèse", "Alertes", "Évolution"} <= set(wb.sheetnames)
    assert len(wb["Évolution"]._charts) == 5
