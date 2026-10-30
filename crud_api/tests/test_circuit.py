"""Circuit de demande (RBAC) : demande -> approbation -> signature agent -> signature chef -> remise -> reception."""
from crud_api.config import get_settings
from crud_api.services.notification_service import phone_digits, sms_link, whatsapp_link
from tests.test_api import make_agent, make_materiel, post


def test_links_without_server():
    assert phone_digits("034 81 780 14") == "261348178014"
    assert sms_link("261348178014", "Bonjour à vous").startswith("sms:+261348178014?body=Bonjour%20%C3%A0")
    assert whatsapp_link("261348178014", "a b").endswith("?text=a%20b")


async def test_full_circuit(client, monkeypatch):
    roles = {x["code"]: x["id"] for x in (await client.get("/roles")).json()}
    agent = await make_agent(client, "C1")
    chef = await make_agent(client, "C2")
    jacky = await make_agent(client, "C3")
    await client.patch(f"/services/{agent['service_id']}", json={"chef_agent_id": chef["id"]})  # chef du service de l'agent
    for name, code, ag in (("agent", "LECTURE", agent), ("chef", "GESTIONNAIRE", chef), ("jacky", "ADMIN", jacky)):
        await post(client, "/utilisateurs", {"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_id": roles[code], "agent_id": ag["id"]})
    m = await make_materiel(client, "ORD-C")
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    async def login(name):
        r = await client.post("/auth/login", json={"nom_utilisateur": name, "mot_de_passe": "secret-123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    ag, ch, ja = await login("agent"), await login("chef"), await login("jacky")
    d = (await client.post("/demandes", json={"type_demande": "ATTRIBUTION"}, headers=ag)).json()
    assert d["phase"] == "A_APPROUVER" and d["role_attendu"] == "ADMIN" and d["actions"] == []
    assert (await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ag)).status_code == 403
    d = (await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ja)).json()
    assert d["phase"] == "A_SIGNER_AGENT"
    assert (await client.post(f"/demandes/{d['id']}/signer-agent", headers=ch)).status_code == 403
    assert (await client.post(f"/demandes/{d['id']}/signer-agent", headers=ag)).json()["phase"] == "A_SIGNER_CHEF"
    assert (await client.post(f"/demandes/{d['id']}/signer-chef", headers=ag)).status_code == 403
    assert (await client.post(f"/demandes/{d['id']}/signer-chef", headers=ch)).json()["phase"] == "A_REMETTRE"
    assert (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ja)).json()["phase"] == "A_APPROUVER_RECEPTION"
    assert (await client.post(f"/demandes/{d['id']}/approuver-reception", headers=ag)).status_code == 403
    assert (await client.post(f"/demandes/{d['id']}/approuver-reception", headers=ch)).json()["phase"] == "TERMINEE"


async def test_affectation_transfers_item_from_holder(client, monkeypatch):
    """Affectation : le materiel est retire a son detenteur et affecte a un autre (ancienne affectation close)."""
    roles = {x["code"]: x["id"] for x in (await client.get("/roles")).json()}
    holder, newcomer, chef, jacky = (await make_agent(client, k) for k in ("T1", "T2", "T3", "T4"))
    await client.patch(f"/services/{newcomer['service_id']}", json={"chef_agent_id": chef["id"]})
    for name, code, ag in (("new", "LECTURE", newcomer), ("chef", "GESTIONNAIRE", chef), ("jacky", "ADMIN", jacky)):
        await post(client, "/utilisateurs", {"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_id": roles[code], "agent_id": ag["id"]})
    m = await make_materiel(client, "ORD-T")
    aff = await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": holder["id"]})
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    async def login(name):
        r = await client.post("/auth/login", json={"nom_utilisateur": name, "mot_de_passe": "secret-123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    nw, ch, ja = await login("new"), await login("chef"), await login("jacky")
    d = (await client.post("/demandes", json={"type_demande": "AFFECTATION"}, headers=nw)).json()
    ok = await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ja)
    assert ok.status_code == 200 and ok.json()["ancien_agent_id"] == holder["id"]
    await client.post(f"/demandes/{d['id']}/signer-agent", headers=nw)
    await client.post(f"/demandes/{d['id']}/signer-chef", headers=ch)
    assert (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ja)).json()["phase"] == "A_APPROUVER_RECEPTION"
    old = (await client.get(f"/affectations/{aff['id']}", headers=ja)).json()
    assert old["date_retour"] is not None  # ancien detenteur : affectation close
    mats = (await client.get(f"/materiels/{m['id']}", headers=ja)).json()
    assert mats["statut"] == "ATTRIBUE"
