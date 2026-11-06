"""Circuit de demande (RBAC) : demande -> approbation -> signature agent -> signature chef -> remise -> reception."""
from crud_api.config import get_settings
from crud_api.services.notification_service import phone_digits, sms_link, whatsapp_link
from tests.test_api import make_agent, make_materiel, post


def test_links_without_server():
    assert phone_digits("034 81 780 14") == "261348178014"
    assert sms_link("261348178014", "Bonjour à vous").startswith("sms:+261348178014?body=Bonjour%20%C3%A0")
    assert whatsapp_link("261348178014", "a b").endswith("?text=a%20b")


async def test_full_circuit(client, monkeypatch):
    """Un seul role (ADMIN) : un administrateur fait chaque etape, au nom de l'agent puis du chef de service."""
    agent = await make_agent(client, "C1")
    chef = await make_agent(client, "C2")
    jacky = await make_agent(client, "C3")
    await client.patch(f"/services/{agent['service_id']}", json={"chef_agent_id": chef["id"]})  # chef du service de l'agent
    for name, ag in (("agent", agent), ("chef", chef), ("jacky", jacky)):
        await post(client, "/utilisateurs", {"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_code": "ADMIN", "agent_id": ag["id"]})
    m = await make_materiel(client, "ORD-C")
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    async def login(name):
        r = await client.post("/auth/login", json={"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_code": "ADMIN"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    ja = await login("jacky")
    # sans connexion : refuse
    assert (await client.post("/demandes", json={"type_demande": "ATTRIBUTION", "agent_id": agent["id"]})).status_code == 401
    d = (await client.post("/demandes", json={"type_demande": "ATTRIBUTION", "agent_id": agent["id"]}, headers=ja)).json()
    assert d["phase"] == "A_APPROUVER" and d["role_attendu"] == "ADMIN" and d["actions"] == ["approuver", "refuser"]
    d = (await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ja)).json()
    assert d["phase"] == "A_SIGNER_AGENT" and d["role_attendu"] == "ADMIN" and d["actions"] == ["signer-agent"]
    # l'administrateur signe au nom de l'agent, puis au nom du chef de service
    d = (await client.post(f"/demandes/{d['id']}/signer-agent", headers=ja)).json()
    assert d["phase"] == "A_SIGNER_CHEF" and d["actions"] == ["signer-chef"]
    d = (await client.post(f"/demandes/{d['id']}/signer-chef", headers=ja)).json()
    assert d["phase"] == "A_REMETTRE" and d["signe_par"] == f"{chef['prenom']} {chef['nom']}"  # nom du chef de service du demandeur
    d = (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ja)).json()
    assert d["phase"] == "A_APPROUVER_RECEPTION" and d["actions"] == ["approuver-reception"]
    d = (await client.post(f"/demandes/{d['id']}/approuver-reception", headers=ja)).json()
    assert d["phase"] == "TERMINEE" and d["role_attendu"] is None and d["actions"] == []
    # un autre administrateur voit la meme demande
    assert (await client.get(f"/demandes/{d['id']}", headers=await login("agent"))).status_code == 200


async def test_attributions_list_exposes_type_phase_and_who_is_expected(client):
    """La liste « Attributions et affectations » s'appuie sur ces champs : type, phase, role attendu."""
    holder = await make_agent(client, "L1")
    d1 = await post(client, "/demandes", {"type_demande": "ATTRIBUTION", "agent_id": holder["id"]})
    d2 = await post(client, "/demandes", {"type_demande": "AFFECTATION", "agent_id": holder["id"]})
    rows = {r["id"]: r for r in (await client.get("/attributions")).json()}
    assert rows[d1["id"]]["type_demande"] == "ATTRIBUTION" and rows[d2["id"]]["type_demande"] == "AFFECTATION"
    assert rows[d1["id"]]["phase"] == "A_APPROUVER" and rows[d1["id"]]["role_attendu"] == "ADMIN"
    one = (await client.get(f"/attributions/{d2['id']}")).json()
    assert one["type_demande"] == "AFFECTATION"


async def test_affectation_transfers_item_from_holder(client, monkeypatch):
    """Affectation : le materiel est retire a son detenteur et affecte a un autre (ancienne affectation close)."""
    holder, newcomer, chef, jacky = [await make_agent(client, k) for k in ("T1", "T2", "T3", "T4")]
    await client.patch(f"/services/{newcomer['service_id']}", json={"chef_agent_id": chef["id"]})
    for name, ag in (("new", newcomer), ("chef", chef), ("jacky", jacky)):
        await post(client, "/utilisateurs", {"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_code": "ADMIN", "agent_id": ag["id"]})
    m = await make_materiel(client, "ORD-T")
    aff = await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": holder["id"]})
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    async def login(name):
        r = await client.post("/auth/login", json={"nom_utilisateur": name, "mot_de_passe": "secret-123", "role_code": "ADMIN"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    ja = await login("jacky")  # tous les comptes sont ADMIN : un seul suffit pour faire chaque etape
    d = (await client.post("/demandes", json={"type_demande": "AFFECTATION", "agent_id": newcomer["id"]}, headers=ja)).json()
    ok = await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ja)
    assert ok.status_code == 200 and ok.json()["ancien_agent_id"] == holder["id"]
    await client.post(f"/demandes/{d['id']}/signer-agent", headers=ja)
    await client.post(f"/demandes/{d['id']}/signer-chef", headers=ja)
    assert (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ja)).json()["phase"] == "A_APPROUVER_RECEPTION"
    old = (await client.get(f"/affectations/{aff['id']}", headers=ja)).json()
    assert old["date_retour"] is not None  # ancien detenteur : affectation close
    mats = (await client.get(f"/materiels/{m['id']}", headers=ja)).json()
    assert mats["statut"] == "ATTRIBUE"
