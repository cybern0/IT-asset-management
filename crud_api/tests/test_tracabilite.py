"""Tracabilite des materiels : le parcours est reconstitue a partir du circuit, des affectations et du journal."""
from tests.test_api import make_agent, make_materiel, post


async def test_parcours_of_a_material(client):
    holder = await make_agent(client, "TR1")
    chef = await make_agent(client, "TR2")
    await client.patch(f"/services/{holder['service_id']}", json={"chef_agent_id": chef["id"]})
    m = await make_materiel(client, "ORD-TR", date_acquisition="2026-01-10", provenance="ACHAT")

    # materiel neuf : acquisition + enregistrement, aucun detenteur
    p = (await client.get(f"/tracabilite/{m['id']}")).json()
    assert [e["type"] for e in p["evenements"]] == ["ACQUISITION", "ENREGISTREMENT"]
    assert p["materiel"]["detenteur"] is None and p["materiel"]["code_inventaire"] == "ORD-TR"

    # circuit complet (API ouverte : le meme compte fait chaque etape)
    d = await post(client, "/demandes", {"type_demande": "ATTRIBUTION", "agent_id": holder["id"], "besoin": "PC"})
    await post(client, f"/demandes/{d['id']}/approuver", {"materiel_id": m["id"]}, 200)
    for step in ("signer-agent", "signer-chef"):
        await post(client, f"/demandes/{d['id']}/{step}", {}, 200)
    await post(client, f"/demandes/{d['id']}/remettre", {}, 200)
    await post(client, f"/demandes/{d['id']}/approuver-reception", {}, 200)

    p = (await client.get(f"/tracabilite/{m['id']}")).json()
    types = [e["type"] for e in p["evenements"]]
    assert types[:2] == ["ACQUISITION", "ENREGISTREMENT"] or set(types[:2]) == {"ACQUISITION", "ENREGISTREMENT"}
    circuit = [t for t in types if t in ("DEMANDE", "APPROBATION", "SIGNATURE_AGENT", "SIGNATURE_CHEF", "REMISE", "RECEPTION")]
    assert circuit == ["DEMANDE", "APPROBATION", "SIGNATURE_AGENT", "SIGNATURE_CHEF", "REMISE", "RECEPTION"]
    assert "AFFECTATION_DIRECTE" not in types  # l'affectation est portee par le dossier : pas de doublon
    remise = next(e for e in p["evenements"] if e["type"] == "REMISE")
    assert remise["agent"] == "Jean Rakoto" and remise["reference"] == d["reference"]
    assert p["materiel"]["detenteur"] == "Jean Rakoto" and p["materiel"]["depuis"] is not None

    # retour du materiel
    aff = next(a for a in (await client.get("/affectations")).json() if a["materiel_id"] == m["id"])
    await client.patch(f"/affectations/{aff['id']}", json={"date_retour": aff["date_remise"], "etat_retour": "BON"})
    p = (await client.get(f"/tracabilite/{m['id']}")).json()
    assert any(e["type"] == "RETOUR" and e["etat"] == "BON" for e in p["evenements"])
    assert p["materiel"]["detenteur"] is None

    # liste resumee
    row = next(r for r in (await client.get("/tracabilite")).json() if r["id"] == m["id"])
    assert row["nb_detenteurs"] == 1 and row["detenteur"] is None


async def test_direct_assignment_and_unknown_material(client):
    agent = await make_agent(client, "TR3")
    m = await make_materiel(client, "ORD-TD")
    await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": agent["id"], "etat_remise": "NEUF"})
    await client.patch(f"/materiels/{m['id']}", json={"localisation": "Bureau 2"})
    p = (await client.get(f"/tracabilite/{m['id']}")).json()
    types = [e["type"] for e in p["evenements"]]
    # une affectation directe cree un dossier de regularisation : elle apparait comme une remise, sans doublon
    assert "REMISE" in types and "AFFECTATION_DIRECTE" not in types and "MODIFICATION" in types
    modif = next(e for e in p["evenements"] if e["type"] == "MODIFICATION")
    assert "localisation" in modif["champs"]
    row = next(r for r in (await client.get("/tracabilite")).json() if r["id"] == m["id"])
    assert row["detenteur"] == "Jean Rakoto" and row["nb_detenteurs"] == 1
    assert (await client.get("/tracabilite/999999")).status_code == 404
