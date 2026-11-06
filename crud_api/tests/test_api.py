import pytest

from crud_api.config import get_settings


async def post(client, path, json, status=201):
    r = await client.post(path, json=json)
    assert r.status_code == status, r.text
    return r.json()


async def make_agent(client, matricule="M1"):
    d = await post(client, "/directions", {"code": f"D{matricule}", "nom": "Direction"})
    s = await post(client, "/services", {"direction_id": d["id"], "code": f"S{matricule}", "nom": "Service"})
    return await post(client, "/agents", {"matricule": matricule, "nom": "Rakoto", "prenom": "Jean", "service_id": s["id"]})


async def make_materiel(client, code="ORD-1", **extra):
    cats = (await client.get("/categories-materiel")).json()
    cat = next(c for c in cats if c["code"] == "ORDINATEUR")
    return await post(client, "/materiels", {"code_inventaire": code, "categorie_id": cat["id"], "designation": "PC", **extra})


async def test_health_and_categories(client):
    r = await client.get("http://test/health")
    assert r.json() == {"status": "ok"}
    cats = (await client.get("/categories-materiel")).json()
    assert {c["code"] for c in cats} >= {"ORDINATEUR", "SIM"}


async def test_organisation_crud_and_constraints(client):
    d = await post(client, "/directions", {"code": "DG", "nom": "Direction générale"})
    assert d["actif"] is True
    r = await client.post("/directions", json={"code": "DG", "nom": "Doublon"})
    assert r.status_code == 409 and r.json()["field"] == "code"
    s = await post(client, "/services", {"direction_id": d["id"], "code": "SI", "nom": "Informatique", "site": ""})
    assert s["site"] is None  # chaine vide -> NULL
    r = await client.delete(f"/directions/{d['id']}")
    assert r.status_code == 409 and "utilisé" in r.json()["detail"]
    r = await client.post("/services", json={"direction_id": 9999, "code": "X", "nom": "X"})
    assert r.status_code == 422 and r.json()["field"] == "direction_id"
    r = await client.patch(f"/services/{s['id']}", json={"nom": None})
    assert r.status_code == 422 and r.json()["field"] == "nom"
    r = await client.patch(f"/services/{s['id']}", json={"nom": "SI central"})
    assert r.json()["nom"] == "SI central"
    assert (await client.delete(f"/services/{s['id']}")).status_code == 204
    assert (await client.get(f"/services/{s['id']}")).status_code == 404


async def test_validation_errors_use_pydantic_format(client):
    r = await client.post("/directions", json={"code": "", "nom": "x"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "code"
    r = await client.post("/agents", json={"matricule": "A", "nom": "n", "prenom": "p", "email": "pas-un-email"})
    assert r.status_code == 422


async def test_single_admin_role(client):
    """Un seul role : ADMIN, tous les droits. Pas de routes /roles ni /permissions ; tout compte cree est administrateur."""
    assert (await client.get("/roles")).status_code == 404
    assert (await client.get("/permissions")).status_code == 404
    u = await post(client, "/utilisateurs", {"nom_utilisateur": "a1", "mot_de_passe": "secret-123"})  # role facultatif
    assert u["role_code"] == "ADMIN"
    r = await client.post("/auth/login", json={"nom_utilisateur": "a1", "mot_de_passe": "secret-123"})
    me = r.json()["user"]
    assert r.status_code == 200 and me["role_code"] == "ADMIN" and me["role_id"] == u["role_id"]
    assert {"fiche.signer_agent", "fiche.signer_chef", "reception.approuver", "demande.creer", "demande.voir_toutes",
            "demande.approuver", "fiche.remettre", "parc.lire", "parc.ecrire", "affectation.transferer", "acces.gerer",
            "audit.lire", "dashboard.voir"} <= set(me["permissions"])
    # aucun autre role n'est accepte
    r = await client.post("/utilisateurs", json={"nom_utilisateur": "a2", "mot_de_passe": "secret-123", "role_code": "UTILISATEUR"})
    assert r.status_code == 422
    r = await client.patch(f"/utilisateurs/{u['id']}", json={"role_code": "UTILISATEUR"})
    assert r.status_code == 422


async def test_users_password_and_last_admin(client):
    u = await post(client, "/utilisateurs", {"nom_utilisateur": "admin", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert "mot_de_passe" not in u and "mot_de_passe_hash" not in u
    r = await client.post("/utilisateurs", json={"nom_utilisateur": "admin", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert r.status_code == 409 and r.json()["field"] == "nom_utilisateur"
    r = await client.post("/utilisateurs", json={"nom_utilisateur": "x", "mot_de_passe": "court"})
    assert r.status_code == 422
    # dernier administrateur actif protege
    assert (await client.patch(f"/utilisateurs/{u['id']}", json={"actif": False})).status_code == 409
    assert (await client.delete(f"/utilisateurs/{u['id']}")).status_code == 409
    other = await post(client, "/utilisateurs", {"nom_utilisateur": "autre", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert (await client.delete(f"/utilisateurs/{other['id']}")).status_code == 204
    # login
    r = await client.post("/auth/login", json={"nom_utilisateur": "admin", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert r.status_code == 200 and r.json()["access_token"] and r.json()["user"]["derniere_connexion"]
    r = await client.post("/auth/login", json={"nom_utilisateur": "admin", "mot_de_passe": "faux"})
    assert r.status_code == 401


async def test_materiel_rules(client):
    m = await make_materiel(client, numero_serie="SN1", valeur_acquisition="1500.50")
    assert m["categorie_code"] == "ORDINATEUR" and m["statut"] == "EN_STOCK" and m["etat"] == "BON"
    r = await client.post("/materiels", json={"code_inventaire": "ORD-1", "categorie_id": m["categorie_id"], "designation": "x"})
    assert r.status_code == 409 and r.json()["field"] == "code_inventaire"
    r = await client.post("/materiels", json={"code_inventaire": "ORD-2", "categorie_id": m["categorie_id"], "designation": "x", "numero_serie": "SN1"})
    assert r.status_code == 409 and r.json()["field"] == "numero_serie"
    r = await client.post("/materiels", json={"code_inventaire": "ORD-3", "categorie_id": m["categorie_id"], "designation": "x", "statut": "ATTRIBUE"})
    assert r.status_code == 422 and r.json()["field"] == "statut"
    r = await client.post("/materiels", json={"code_inventaire": "ORD-4", "categorie_id": m["categorie_id"], "designation": "x", "valeur_acquisition": -1})
    assert r.status_code == 422
    r = await client.patch(f"/materiels/{m['id']}", json={"categorie_id": m["categorie_id"], "etat": "EN_PANNE", "statut": "EN_MAINTENANCE"})
    assert r.json()["statut"] == "EN_MAINTENANCE"
    # deux materiels sans numero de serie ne se bloquent pas entre eux
    await make_materiel(client, "ORD-5")
    await make_materiel(client, "ORD-6")


async def test_affectation_lifecycle(client):
    agent = await make_agent(client)
    m = await make_materiel(client)
    a = await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": agent["id"]})
    assert a["date_retour"] is None and a["etat_remise"] == "BON"
    assert (await client.get(f"/materiels/{m['id']}")).json()["statut"] == "ATTRIBUE"
    # deja affecte
    r = await client.post("/affectations", json={"materiel_id": m["id"], "agent_id": agent["id"]})
    assert r.status_code == 409 and r.json()["field"] == "materiel_id"
    # le statut ne se change pas a la main tant qu'il est affecte
    r = await client.patch(f"/materiels/{m['id']}", json={"statut": "EN_STOCK"})
    assert r.status_code == 409
    # retour avec materiel en panne -> maintenance
    r = await client.patch(f"/affectations/{a['id']}", json={"date_retour": a["date_remise"], "etat_retour": "EN_PANNE"})
    assert r.status_code == 200 and r.json()["etat_retour"] == "EN_PANNE"
    mat = (await client.get(f"/materiels/{m['id']}")).json()
    assert mat["statut"] == "EN_MAINTENANCE" and mat["etat"] == "EN_PANNE"
    # impossible de rouvrir
    r = await client.patch(f"/affectations/{a['id']}", json={"date_retour": None})
    assert r.status_code == 409
    # impossible d'affecter un materiel en maintenance
    r = await client.post("/affectations", json={"materiel_id": m["id"], "agent_id": agent["id"]})
    assert r.status_code == 409
    # retour avant remise refuse
    m2 = await make_materiel(client, "ORD-2")
    r = await client.post("/affectations", json={"materiel_id": m2["id"], "agent_id": agent["id"], "date_remise": "2026-05-10", "date_retour": "2026-05-01"})
    assert r.status_code == 422 and r.json()["field"] == "date_retour"
    # supprimer une affectation en cours remet le materiel en stock
    a2 = await post(client, "/affectations", {"materiel_id": m2["id"], "agent_id": agent["id"]})
    assert (await client.delete(f"/affectations/{a2['id']}")).status_code == 204
    assert (await client.get(f"/materiels/{m2['id']}")).json()["statut"] == "EN_STOCK"
    # agent inactif refuse
    await client.patch(f"/agents/{agent['id']}", json={"actif": False})
    r = await client.post("/affectations", json={"materiel_id": m2["id"], "agent_id": agent["id"]})
    assert r.status_code == 422 and r.json()["field"] == "agent_id"


async def test_stock_movements(client):
    user = await post(client, "/utilisateurs", {"nom_utilisateur": "gest", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    d = await post(client, "/directions", {"code": "D", "nom": "D"})
    s1 = await post(client, "/services", {"direction_id": d["id"], "code": "S1", "nom": "S1"})
    art = await post(client, "/articles-consommables", {"reference": "PAP", "designation": "Papier", "seuil_alerte": "5"})
    base = {"article_id": art["id"], "effectue_par": user["id"], "motif": "test"}

    await post(client, "/mouvements", {**base, "type_mouvement": "ENTREE", "quantite": "10", "provenance": "ACHAT"})
    await post(client, "/mouvements", {**base, "type_mouvement": "TRANSFERT", "quantite": "4", "service_destination_id": s1["id"]})
    stocks = {x["service_id"]: x["quantite"] for x in (await client.get("/stocks")).json()}
    assert float(stocks[None]) == 6 and float(stocks[s1["id"]]) == 4

    r = await client.post("/mouvements", json={**base, "type_mouvement": "SORTIE", "quantite": "7"})
    assert r.status_code == 409 and r.json()["field"] == "quantite"
    await post(client, "/mouvements", {**base, "type_mouvement": "SORTIE", "quantite": "2", "service_source_id": s1["id"]})
    await post(client, "/mouvements", {**base, "type_mouvement": "AJUSTEMENT", "quantite": "1"})
    stocks = {x["service_id"]: x["quantite"] for x in (await client.get("/stocks")).json()}
    assert float(stocks[None]) == 7 and float(stocks[s1["id"]]) == 2

    # regles de coherence
    bad = [
        {**base, "type_mouvement": "ENTREE", "quantite": "1", "service_source_id": s1["id"]},
        {**base, "type_mouvement": "SORTIE", "quantite": "1", "provenance": "DON"},
        {**base, "type_mouvement": "TRANSFERT", "quantite": "1"},
        {**base, "type_mouvement": "ENTREE", "quantite": "0"},
    ]
    for body in bad:
        assert (await client.post("/mouvements", json=body)).status_code == 422, body
    # un mouvement refuse n'a laisse aucune trace
    assert len((await client.get("/mouvements")).json()) == 4
    # mouvements immuables
    assert (await client.patch("/mouvements/1", json={"motif": "x"})).status_code == 405
    assert (await client.delete("/mouvements/1")).status_code == 405
    # un seul stock par (article, service), central compris
    r = await client.post("/stocks", json={"article_id": art["id"], "quantite": "1"})
    assert r.status_code == 409


async def test_software_and_licences(client):
    free = await post(client, "/logiciels", {"nom": "LibreOffice", "version": "24.8", "type_licence": "SANS_LICENCE"})
    paid = await post(client, "/logiciels", {"nom": "Office", "version": "2021"})
    r = await client.post("/logiciels", json={"nom": "office", "version": "2021"})
    assert r.status_code == 409 and r.json()["field"] == "nom"
    await post(client, "/logiciels", {"nom": "Office"})  # autre version (NULL)
    r = await client.post("/logiciels", json={"nom": "OFFICE"})
    assert r.status_code == 409
    r = await client.post("/licences", json={"logiciel_id": free["id"], "nombre_postes": 3})
    assert r.status_code == 409 and r.json()["field"] == "logiciel_id"
    lic = await post(client, "/licences", {"logiciel_id": paid["id"], "nombre_postes": 10, "date_expiration": "2027-01-01"})
    assert lic["nombre_postes"] == 10
    assert (await client.post("/licences", json={"logiciel_id": paid["id"], "nombre_postes": 0})).status_code == 422
    r = await client.patch(f"/logiciels/{paid['id']}", json={"type_licence": "SANS_LICENCE"})
    assert r.status_code == 409 and r.json()["field"] == "type_licence"


async def test_audit_log_is_written_and_read_only(client):
    d = await post(client, "/directions", {"code": "DG", "nom": "DG"})
    await client.patch(f"/directions/{d['id']}", json={"nom": "DG2"})
    await client.delete(f"/directions/{d['id']}")
    entries = (await client.get("/journal-audit")).json()
    actions = [(e["action"], e["table_cible"], e["identifiant_cible"]) for e in entries]
    assert ("CREATE", "direction", d["id"]) in actions
    assert ("UPDATE", "direction", d["id"]) in actions
    assert ("DELETE", "direction", d["id"]) in actions
    created = next(e for e in entries if e["action"] == "CREATE")
    assert created["details"] == {"champs": ["code", "nom"]}
    assert (await client.post("/journal-audit", json={"action": "X"})).status_code == 405
    assert (await client.delete(f"/journal-audit/{entries[0]['id']}")).status_code in (404, 405)
    # un secret n'est jamais journalise
    await post(client, "/utilisateurs", {"nom_utilisateur": "u", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert "secret-123" not in (await client.get("/journal-audit")).text


async def test_authentication_when_enabled(client, monkeypatch):
    await post(client, "/utilisateurs", {"nom_utilisateur": "admin", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    r = await client.get("/materiels")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    r = await client.post("/auth/login", json={"nom_utilisateur": "admin", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/materiels", headers=auth)).status_code == 200
    assert (await client.get("/auth/me", headers=auth)).json()["nom_utilisateur"] == "admin"
    assert (await client.get("/materiels", headers={"Authorization": "Bearer faux"})).status_code == 401
    # l'auteur est journalise
    await client.post("/directions", json={"code": "DG", "nom": "DG"}, headers=auth)
    entries = (await client.get("/journal-audit", headers=auth)).json()
    assert any(e["action"] == "CREATE" and e["utilisateur_id"] is not None for e in entries)


async def test_authorization_admin_only(client, monkeypatch):
    """Un seul role : sans connexion tout est refuse (401) ; un ADMIN connecte a acces a tout."""
    await post(client, "/utilisateurs", {"nom_utilisateur": "adm", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    m = await make_materiel(client, "ORD-A")
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)

    for url in ("/materiels", "/agents", "/utilisateurs", "/journal-audit", "/dashboard", "/dashboard/repartition"):
        assert (await client.get(url)).status_code == 401, url

    r = await client.post("/auth/login", json={"nom_utilisateur": "adm", "mot_de_passe": "secret-123", "role_code": "ADMIN"})
    assert r.status_code == 200 and r.json()["user"]["role_code"] == "ADMIN"
    adm = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/auth/me", headers=adm)).json()["role_code"] == "ADMIN"
    for url in ("/materiels", "/agents", "/utilisateurs", "/journal-audit", "/dashboard", "/dashboard/repartition"):
        assert (await client.get(url, headers=adm)).status_code == 200, url
    assert (await client.post("/directions", json={"code": "DG", "nom": "DG"}, headers=adm)).status_code == 201
    assert (await client.patch(f"/materiels/{m['id']}", json={"designation": "PC 2"}, headers=adm)).status_code == 200
    assert (await client.delete(f"/materiels/{m['id']}", headers=adm)).status_code == 204


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


async def test_attribution_workflow(client):
    agent = await make_agent(client, "M9")
    m = await make_materiel(client, "ORD-9", caracteristiques="RAM: 16 Go, Stockage: 512 Go, OS: Windows 11")
    step = lambda f, body=None, code=200: post(client, f"/attributions/{f['id']}/avancer", body or {}, code)  # noqa: E731

    # etape 1 : demande, puis validation du manager (geste humain : on enregistre qu'elle a eu lieu)
    f = await post(client, "/attributions", {"agent_id": agent["id"], "besoin": "PC portable", "canal": "TICKET"})
    assert f["etape"] == 1 and f["etat"] == "EN_COURS" and f["reference"].startswith("FD-")
    r = await client.post(f"/attributions/{f['id']}/avancer", json={})
    assert r.status_code == 422 and r.json()["field"] == "valide_par"  # le manager doit etre nomme
    f = await step(f, {"valide_par": "Mme Rabe"})
    assert f["etape"] == 2 and f["valide_par"] == "Mme Rabe"

    # etapes 2-3 : equipement choisi, fiche generee (PDF disponible)
    r = await client.post(f"/attributions/{f['id']}/avancer", json={})
    assert r.status_code == 422 and r.json()["field"] == "materiel_id"
    f = await step(f, {"materiel_id": m["id"]})
    assert f["etape"] == 4 and f["date_generation"] and f["materiel_code"] == "ORD-9"
    pdf = await client.get(f"/attributions/{f['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # le materiel est reserve par ce dossier
    other = await post(client, "/attributions", {"agent_id": agent["id"], "valide_par": "Mme Rabe"})
    r = await client.post(f"/attributions/{other['id']}/avancer", json={"materiel_id": m["id"]})
    assert r.status_code == 409 and r.json()["field"] == "materiel_id"

    # etape 4 : signature enregistree (papier par defaut) ; on peut la defaire puis la refaire
    f = await step(f, {"signe_par": "Resp. Info"})
    assert f["statut"] == "SIGNEE" and f["mode_signature"] == "MANUSCRITE" and f["etape"] == 5
    f = await post(client, f"/attributions/{f['id']}/reculer", {})
    assert f["statut"] == "NON_SIGNEE" and f["date_signature"] is None and f["etape"] == 4
    f = await step(f, {"mode_signature": "ELECTRONIQUE", "signe_par": "Resp. Info"})
    assert f["mode_signature"] == "ELECTRONIQUE" and f["etape"] == 5

    # etapes 5-6 : remise -> affectation creee, materiel « Attribue »
    f = await step(f, {"etat_constate": "BON", "accessoires": ["Chargeur", "Souris"], "accessoires_autre": "Casque"})
    assert f["etape"] == 6 and f["etat"] == "ATTRIBUEE" and f["affectation_id"]
    assert f["accessoires"] == ["Chargeur", "Souris"]
    assert (await client.get(f"/materiels/{m['id']}")).json()["statut"] == "ATTRIBUE"
    assert len((await client.get("/affectations")).json()) == 1  # une seule affectation, pas de doublon

    # dossier termine : plus d'avancement ni de retour en arriere, et la fiche signee protege l'affectation
    assert (await client.post(f"/attributions/{f['id']}/avancer", json={})).status_code == 409
    assert (await client.post(f"/attributions/{f['id']}/reculer")).status_code == 409
    assert (await client.delete(f"/affectations/{f['affectation_id']}")).status_code == 409


async def test_attribution_signature_fixee_a_la_main(client):
    agent = await make_agent(client, "M7")
    m = await make_materiel(client, "ORD-7")
    f = await post(client, "/attributions", {"agent_id": agent["id"], "valide_par": "Mme Rabe"})
    put = lambda body, code=200: post(client, f"/attributions/{f['id']}/signature", body, code)  # noqa: E731
    await put({"signee": True}, 409)  # fiche non generee : aucun equipement choisi
    f = await post(client, f"/attributions/{f['id']}/avancer", {"materiel_id": m["id"]}, 200)
    s = await put({"signee": True, "date": "2026-05-02", "mode_signature": "ELECTRONIQUE", "signe_par": "Resp. Info"})
    assert (s["etape"], s["statut"], s["date_signature"], s["mode_signature"]) == (5, "SIGNEE", "2026-05-02", "ELECTRONIQUE")
    assert s["signature_modifiee_le"]
    s = await put({"signee": False})
    assert (s["etape"], s["statut"], s["date_signature"]) == (4, "NON_SIGNEE", None)


async def test_attribution_refus_et_regularisation(client):
    agent = await make_agent(client, "M8")
    f = await post(client, "/attributions", {"agent_id": agent["id"]})
    r = await client.post(f"/attributions/{f['id']}/clore", json={"motif": "Pas de budget"})
    assert r.json()["etat"] == "REFUSEE"  # refuse : le manager n'avait pas valide
    assert (await client.post(f"/attributions/{f['id']}/avancer", json={"valide_par": "X"})).status_code == 409

    # apres validation, la cloture devient une annulation
    g = await post(client, "/attributions", {"agent_id": agent["id"], "valide_par": "X"})
    assert (await client.post(f"/attributions/{g['id']}/clore", json={})).json()["etat"] == "ANNULEE"

    # affectation saisie directement : un dossier de regularisation est cree
    m = await make_materiel(client, "ORD-8")
    a = await post(client, "/affectations", {"materiel_id": m["id"], "agent_id": agent["id"]})
    d = (await client.get(f"/affectations/{a['id']}/attribution")).json()
    assert d["etape"] == 6 and d["valide_par"] == "Régularisation" and d["statut"] == "NON_SIGNEE"
    assert (await client.delete(f"/affectations/{a['id']}")).status_code in (204, 409)


async def test_image_materiel(client, tmp_path):
    get_settings().upload_dir = str(tmp_path)
    m = await make_materiel(client, "ORD-IMG")
    assert m["a_image"] is False
    assert (await client.get(f"/materiels/{m['id']}/image")).status_code == 404

    bad = await client.post(f"/materiels/{m['id']}/image", files={"file": ("x.png", b"pas une image", "image/png")})
    assert bad.status_code == 422 and bad.json()["field"] == "file"

    ok = await client.post(f"/materiels/{m['id']}/image", files={"file": ("x.png", PNG, "image/png")})
    assert ok.status_code == 200 and ok.json()["a_image"] is True
    assert (await client.get(f"/materiels/{m['id']}/image")).content == PNG
    assert (await client.delete(f"/materiels/{m['id']}/image")).status_code == 204
    assert (await client.get(f"/materiels/{m['id']}")).json()["a_image"] is False
