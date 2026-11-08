"""Attribution en une saisie, affectation directe (transfert) et options des formulaires."""
from tests.test_api import make_agent, make_materiel, post


async def test_direct_attribution_in_one_go(client):
    """Demande, equipement, fiche, signature et remise enregistres ensemble : le dossier est termine."""
    agent = await make_agent(client, "D1")
    m = await make_materiel(client, "ORD-D1")
    d = await post(client, "/attributions/directe", {
        "agent_id": agent["id"], "materiel_id": m["id"], "etat_constate": "BON", "accessoires": ["Chargeur"],
        "signee": True, "mode_signature": "ELECTRONIQUE", "signe_par": "Mme Rabe",
    })
    assert d["etape"] == 6 and d["etat"] == "ATTRIBUEE" and d["statut"] == "SIGNEE"
    assert d["materiel_id"] == m["id"] and d["affectation_id"] is not None and d["accessoires"] == ["Chargeur"]
    assert (await client.get(f"/materiels/{m['id']}")).json()["statut"] == "ATTRIBUE"
    assert (await client.get(f"/attributions/{d['id']}/pdf")).status_code == 200  # meme fiche PDF que le pas a pas
    # le meme materiel n'est plus en stock : deuxieme attribution refusee, rien n'est cree
    other = await make_agent(client, "D2")
    n = len((await client.get("/attributions")).json())
    r = await client.post("/attributions/directe", json={"agent_id": other["id"], "materiel_id": m["id"]})
    assert r.status_code == 409
    assert len((await client.get("/attributions")).json()) == n


async def test_direct_attribution_unsigned_stays_to_sign(client):
    agent = await make_agent(client, "D3")
    m = await make_materiel(client, "ORD-D3")
    d = await post(client, "/attributions/directe", {"agent_id": agent["id"], "materiel_id": m["id"]})
    assert d["statut"] != "SIGNEE" and d["etat"] == "ATTRIBUEE"
    # la signature peut etre notee plus tard, comme pour les autres dossiers
    f = await post(client, f"/attributions/{d['id']}/signature", {"signee": True}, 200)
    assert f["statut"] == "SIGNEE"


async def test_direct_attribution_rejects_bad_input(client):
    agent = await make_agent(client, "D4")
    m = await make_materiel(client, "ORD-D4")
    assert (await client.post("/attributions/directe", json={"agent_id": 999999, "materiel_id": m["id"]})).status_code == 422
    assert (await client.post("/attributions/directe", json={"agent_id": agent["id"], "materiel_id": 999999})).status_code == 422
    r = await client.post("/attributions/directe", json={
        "agent_id": agent["id"], "materiel_id": m["id"], "date_remise": "2026-01-10", "date_demande": "2026-02-01"})
    assert r.status_code == 422  # demande posterieure a la remise
    assert (await client.get(f"/materiels/{m['id']}")).json()["statut"] == "EN_STOCK"


async def test_attributions_list_exposes_type(client):
    """Les onglets Attributions / Affectations de l'interface filtrent sur `type_demande`."""
    holder, newcomer = await make_agent(client, "L1"), await make_agent(client, "L2")
    m = await make_materiel(client, "ORD-L1")
    d1 = await post(client, "/attributions/directe", {"agent_id": holder["id"], "materiel_id": m["id"]})
    aff = await post(client, "/transferts", {"materiel_id": m["id"], "agent_id": newcomer["id"]})
    rows = (await client.get("/attributions")).json()
    by_id = {r["id"]: r for r in rows}
    assert by_id[d1["id"]]["type_demande"] == "ATTRIBUTION"
    transfer_dossier = next(r for r in rows if r["affectation_id"] == aff["id"])
    assert transfer_dossier["type_demande"] == "AFFECTATION" and transfer_dossier["ancien_agent_id"] == holder["id"]


async def test_transfer_moves_item_between_agents(client):
    """Affectation directe : le materiel est retire a son detenteur et donne a un autre (ancienne affectation close)."""
    holder, newcomer = await make_agent(client, "T1"), await make_agent(client, "T2")
    m = await make_materiel(client, "ORD-T")
    old = await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": holder["id"]})
    new = await post(client, "/transferts", {"materiel_id": m["id"], "agent_id": newcomer["id"], "etat": "BON"})
    assert new["agent_id"] == newcomer["id"] and new["date_retour"] is None
    assert (await client.get(f"/affectations/{old['id']}")).json()["date_retour"] is not None
    assert (await client.get(f"/materiels/{m['id']}")).json()["statut"] == "ATTRIBUE"
    # on ne transfere pas un materiel a son detenteur actuel, ni un materiel libre
    assert (await client.post("/transferts", json={"materiel_id": m["id"], "agent_id": newcomer["id"]})).status_code in (409, 422)
    free = await make_materiel(client, "ORD-T2")
    assert (await client.post("/transferts", json={"materiel_id": free["id"], "agent_id": newcomer["id"]})).status_code in (409, 422)


async def test_options_list_stock_and_held_items(client):
    holder = await make_agent(client, "O1")
    stock, held = await make_materiel(client, "ORD-O1"), await make_materiel(client, "ORD-O2")
    await post(client, "/affectations", {"materiel_id": held["id"], "agent_id": holder["id"]})
    o = (await client.get("/circuit/options")).json()
    assert stock["id"] in [x["id"] for x in o["stock"]] and held["id"] not in [x["id"] for x in o["stock"]]
    assert held["id"] in [x["id"] for x in o["detenus"]] and o["categories"]
