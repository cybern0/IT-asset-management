"""Utilisateur standard : demande pour lui-meme, signe, approuve la reception ; pas d'acces au reste de l'application."""
from crud_api.config import get_settings
from tests.test_api import make_agent, make_materiel, post

PWD = "secret-123"


async def _setup(client, monkeypatch):
    """Un service (chef : `chef`), deux agents, un autre agent d'un autre service, un administrateur."""
    agent = await make_agent(client, "R1")
    chef = await make_agent(client, "R2")
    other = await make_agent(client, "R3")
    m = await make_materiel(client, "ORD-R")  # avant d'activer l'authentification
    await client.patch(f"/services/{agent['service_id']}", json={"chef_agent_id": chef["id"]})
    for name, ag, role in (("agent", agent, "UTILISATEUR"), ("chef", chef, "UTILISATEUR"), ("autre", other, "UTILISATEUR"), ("jacky", None, "ADMIN")):
        await post(client, "/utilisateurs", {"nom_utilisateur": name, "mot_de_passe": PWD, "role_code": role, **({"agent_id": ag["id"]} if ag else {})})
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    async def login(name):
        r = await client.post("/auth/login", json={"nom_utilisateur": name, "mot_de_passe": PWD})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return agent, chef, other, m, login


async def test_standard_user_circuit(client, monkeypatch):
    agent, chef, other, m, login = await _setup(client, monkeypatch)
    ag, ch, ot, ja = await login("agent"), await login("chef"), await login("autre"), await login("jacky")

    # l'agent demande POUR LUI (meme s'il indique un autre agent)
    r = await client.post("/demandes", json={"type_demande": "ATTRIBUTION", "agent_id": chef["id"], "besoin": "PC"}, headers=ag)
    assert r.status_code == 201
    d = r.json()
    assert d["agent_id"] == agent["id"] and d["phase"] == "A_APPROUVER" and d["role_attendu"] == "ADMIN"
    assert d["actions"] == []  # il ne peut ni approuver ni refuser
    assert (await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ag)).status_code == 403

    # visibilite : lui et son chef de service la voient ; un autre agent, non
    assert [x["id"] for x in (await client.get("/demandes", headers=ag)).json()] == [d["id"]]
    assert [x["id"] for x in (await client.get("/demandes", headers=ch)).json()] == [d["id"]]
    assert (await client.get("/demandes", headers=ot)).json() == []
    assert (await client.get(f"/demandes/{d['id']}", headers=ot)).status_code in (403, 404)

    # l'administrateur approuve ; l'agent signe, puis le chef (pas l'inverse, pas un autre agent)
    d = (await client.post(f"/demandes/{d['id']}/approuver", json={"materiel_id": m["id"]}, headers=ja)).json()
    assert d["phase"] == "A_SIGNER_AGENT" and d["role_attendu"] == "UTILISATEUR"
    assert (await client.get(f"/demandes/{d['id']}", headers=ag)).json()["actions"] == ["signer-agent"]
    assert (await client.get(f"/demandes/{d['id']}", headers=ch)).json()["actions"] == []
    assert (await client.post(f"/demandes/{d['id']}/signer-agent", headers=ch)).status_code in (403, 409, 422)
    assert (await client.post(f"/demandes/{d['id']}/signer-agent", headers=ag)).json()["phase"] == "A_SIGNER_CHEF"
    assert (await client.post(f"/demandes/{d['id']}/signer-chef", headers=ag)).status_code in (403, 409, 422)  # l'agent n'est pas le chef
    d = (await client.post(f"/demandes/{d['id']}/signer-chef", headers=ch)).json()
    assert d["phase"] == "A_REMETTRE" and d["role_attendu"] == "ADMIN" and d["signe_par"] == f"{chef['prenom']} {chef['nom']}"

    # remise par l'administrateur seul ; reception approuvee par le chef de service
    assert (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ch)).status_code == 403
    d = (await client.post(f"/demandes/{d['id']}/remettre", json={}, headers=ja)).json()
    assert d["phase"] == "A_APPROUVER_RECEPTION" and d["role_attendu"] == "UTILISATEUR"
    assert (await client.post(f"/demandes/{d['id']}/approuver-reception", headers=ag)).status_code in (403, 409, 422)
    d = (await client.post(f"/demandes/{d['id']}/approuver-reception", headers=ch)).json()
    assert d["phase"] == "TERMINEE" and d["role_attendu"] is None


async def test_standard_user_has_no_access_to_the_rest(client, monkeypatch):
    _, _, _, _, login = await _setup(client, monkeypatch)
    ag = await login("agent")
    for url in ("/materiels", "/agents", "/services", "/affectations", "/attributions", "/utilisateurs",
                "/dashboard", "/dashboard/repartition", "/tracabilite"):
        assert (await client.get(url, headers=ag)).status_code == 403, url
    opts = (await client.get("/demandes/options", headers=ag)).json()
    assert opts["stock"] == [] and opts["detenus"] == [] and opts["categories"]  # ni stock ni detenteurs
    assert (await client.post("/materiels", json={"code_inventaire": "X", "categorie_id": 1, "designation": "x"}, headers=ag)).status_code == 403
    me = (await client.get("/auth/me", headers=ag)).json()
    assert me["role_code"] == "UTILISATEUR" and "parc.lire" not in me["permissions"]
