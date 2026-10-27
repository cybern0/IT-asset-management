"""Circuit d'attribution de bout en bout (service + affectation), sur SQLite : aucune base PostgreSQL requise."""
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from crud_api import models as M
from crud_api.core.database import Base
from crud_api.core.errors import ConflictError, UnprocessableError
from crud_api.models.user import role_permission
from crud_api.schemas.fiche import AttributionCreate, AvancerIn
from crud_api.services import audit_service, fiche_service as fs

pytestmark = pytest.mark.nodb


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw):  # cle auto-incrementee sous SQLite
    return "INTEGER"


@pytest_asyncio.fixture
async def db(monkeypatch):
    async def no_audit(*a, **k):  # le journal utilise des types PostgreSQL (JSONB, INET)
        return None

    monkeypatch.setattr(audit_service, "record", no_audit)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:").execution_options(schema_translate_map={"eparc": None})
    tables = [m.__table__ for m in (
        M.Permission, M.Role, M.Utilisateur, M.CategorieMateriel, M.Direction, M.Service, M.Agent, M.Materiel,
        M.Affectation, M.FicheDetention)] + [role_permission]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all([
            M.CategorieMateriel(id=1, code="ORDINATEUR", libelle="Ordinateur"),
            M.Direction(id=1, code="DG", nom="Direction"), M.Service(id=1, direction_id=1, code="SI", nom="Informatique"),
            M.Agent(id=1, matricule="M1", nom="Rakoto", prenom="Jean", service_id=1),
        ])
        await session.flush()
        session.add_all([M.Materiel(id=i, code_inventaire=f"ORD-{i}", categorie_id=1, designation=f"PC {i}", statut="EN_STOCK",
                                    etat="NEUF", provenance="ACHAT") for i in (1, 2)])
        await session.commit()
        yield session
    await engine.dispose()


async def new_request(db, **over):
    return await fs.create_request(db, AttributionCreate(agent_id=1, besoin="PC", **over))


async def test_full_circuit_with_human_steps_only_recorded(db):
    f = await new_request(db)
    assert (f["etape"], f["etat"]) == (1, "EN_COURS") and f["reference"].endswith("-0001")

    with pytest.raises(UnprocessableError):  # le manager doit etre nomme
        await fs.advance(db, f["id"], AvancerIn())
    f = await fs.advance(db, f["id"], AvancerIn(valide_par="Mme Rabe"))
    assert f["etape"] == 2 and f["valide_par"] == "Mme Rabe" and f["date_validation"] == date.today()

    with pytest.raises(UnprocessableError):  # equipement obligatoire
        await fs.advance(db, f["id"], AvancerIn())
    f = await fs.advance(db, f["id"], AvancerIn(materiel_id=1))
    assert f["etape"] == 4 and f["date_generation"] and f["materiel_code"] == "ORD-1"

    # signature : enregistree sans fichier ni controle de date ; defaut = papier, aujourd'hui
    f = await fs.advance(db, f["id"], AvancerIn(signe_par="Resp. Info"))
    assert (f["etape"], f["statut"], f["mode_signature"]) == (5, "SIGNEE", "MANUSCRITE") and f["date_signature"] == date.today()

    f = await fs.back(db, f["id"])  # signature a refaire
    assert (f["etape"], f["statut"], f["date_signature"], f["signe_par"]) == (4, "NON_SIGNEE", None, None)
    f = await fs.advance(db, f["id"], AvancerIn(mode_signature="ELECTRONIQUE", date=date(2026, 1, 5)))
    assert f["mode_signature"] == "ELECTRONIQUE" and f["date_signature"] == date(2026, 1, 5)

    f = await fs.advance(db, f["id"], AvancerIn(accessoires=["Chargeur", "Souris"], accessoires_autre="Casque"))
    assert (f["etape"], f["etat"]) == (6, "ATTRIBUEE") and f["affectation_id"] and f["etat_constate"] == "NEUF"
    assert f["accessoires"] == ["Chargeur", "Souris"]
    assert (await db.get(M.Materiel, 1, populate_existing=True)).statut == "ATTRIBUE"

    for action in (lambda: fs.advance(db, f["id"], AvancerIn()), lambda: fs.back(db, f["id"]),
                   lambda: fs.close(db, f["id"], None)):
        with pytest.raises(ConflictError):  # termine : plus rien a faire ici
            await action()


async def test_back_steps_release_what_they_undo(db):
    f = await new_request(db, valide_par="Mme Rabe")
    assert f["etape"] == 2
    f = await fs.advance(db, f["id"], AvancerIn(materiel_id=1))
    # un autre dossier ne peut pas prendre l'equipement reserve...
    g = await new_request(db, valide_par="Mme Rabe")
    with pytest.raises(ConflictError):
        await fs.advance(db, g["id"], AvancerIn(materiel_id=1))
    # ...mais le peut des que le premier dossier recule
    f = await fs.back(db, f["id"])
    assert f["etape"] == 2 and f["materiel_id"] is None and f["date_generation"] is None
    assert (await fs.advance(db, g["id"], AvancerIn(materiel_id=1)))["materiel_code"] == "ORD-1"
    f = await fs.back(db, f["id"])
    assert f["etape"] == 1 and f["valide_par"] is None
    with pytest.raises(ConflictError):
        await fs.back(db, f["id"])  # deja a la premiere etape


async def test_refuse_then_cancel_and_closed_is_final(db):
    f = await new_request(db)
    assert (await fs.close(db, f["id"], "Pas de budget"))["etat"] == "REFUSEE"
    for action in (lambda: fs.advance(db, f["id"], AvancerIn(valide_par="X")), lambda: fs.back(db, f["id"]),
                   lambda: fs.close(db, f["id"], None)):
        with pytest.raises(ConflictError):
            await action()
    g = await new_request(db, valide_par="X")
    assert (await fs.close(db, g["id"], None))["etat"] == "ANNULEE"


async def test_equipment_must_be_in_stock(db):
    f = await new_request(db, valide_par="X")
    m = await db.get(M.Materiel, 2)
    m.statut = "EN_MAINTENANCE"
    await db.commit()
    with pytest.raises(ConflictError):
        await fs.advance(db, f["id"], AvancerIn(materiel_id=2))
    with pytest.raises(UnprocessableError):
        await fs.advance(db, f["id"], AvancerIn(materiel_id=999))


async def test_direct_affectation_creates_a_regularisation_dossier(db):
    from crud_api.schemas.materiel import AffectationCreate
    from crud_api.services.materiel_service import affectation_service

    a = await affectation_service.create(db, AffectationCreate(materiel_id=2, agent_id=1))
    d = await fs.get_by_affectation(db, a.id)
    assert d["etape"] == 6 and d["valide_par"] == fs.REGULARISATION and d["etat"] == "ATTRIBUEE"


async def test_admin_sets_the_signature_state_by_hand(db):
    from crud_api.schemas.fiche import SignatureIn

    f = await new_request(db, valide_par="Mme Rabe")
    with pytest.raises(ConflictError):  # pas de fiche tant qu'aucun equipement n'est choisi
        await fs.set_signature(db, f["id"], SignatureIn(signee=True))
    f = await fs.advance(db, f["id"], AvancerIn(materiel_id=1))
    assert (f["etape"], f["statut"]) == (4, "NON_SIGNEE") and f["signature_modifiee_le"] is None

    # « Signee » : date, mode et signataire sont enregistres, avec la date de la mise a jour
    f = await fs.set_signature(db, f["id"], SignatureIn(signee=True, date=date(2026, 5, 2), mode_signature="ELECTRONIQUE", signe_par="Resp. Info"))
    assert (f["etape"], f["statut"], f["date_signature"], f["mode_signature"], f["signe_par"]) == (
        5, "SIGNEE", date(2026, 5, 2), "ELECTRONIQUE", "Resp. Info")
    assert f["signature_modifiee_le"] is not None

    # « A signer » : tout est efface et le dossier revient a l'etape 4
    f = await fs.set_signature(db, f["id"], SignatureIn(signee=False))
    assert (f["etape"], f["statut"], f["date_signature"], f["mode_signature"], f["signe_par"]) == (4, "NON_SIGNEE", None, None, None)

    # par defaut : manuscrite, aujourd'hui
    f = await fs.set_signature(db, f["id"], SignatureIn(signee=True))
    assert (f["mode_signature"], f["date_signature"]) == ("MANUSCRITE", date.today())

    # la remise exige la signature, mais l'etat reste modifiable apres elle (signature en retard ou a refaire)
    f = await fs.advance(db, f["id"], AvancerIn())
    assert (f["etape"], f["etat"]) == (6, "ATTRIBUEE")
    f = await fs.set_signature(db, f["id"], SignatureIn(signee=False))
    assert (f["etape"], f["etat"], f["statut"]) == (6, "ATTRIBUEE", "NON_SIGNEE")


async def test_signature_state_remembers_who_set_it(db):
    from crud_api.schemas.fiche import SignatureIn

    db.add_all([M.Role(id=1, code="ADMIN", libelle="Administrateur"),
                M.Utilisateur(id=1, nom_utilisateur="admin", mot_de_passe_hash="x", role_id=1)])
    await db.commit()
    db.info["actor_id"] = 1
    f = await new_request(db, valide_par="Mme Rabe")
    f = await fs.advance(db, f["id"], AvancerIn(materiel_id=1))
    f = await fs.set_signature(db, f["id"], SignatureIn(signee=True))
    assert f["signature_modifiee_par"] == "admin"


async def test_closed_dossier_signature_is_frozen(db):
    from crud_api.schemas.fiche import SignatureIn

    f = await new_request(db, valide_par="Mme Rabe")
    f = await fs.advance(db, f["id"], AvancerIn(materiel_id=1))
    await fs.close(db, f["id"], "Abandon")
    with pytest.raises(ConflictError):
        await fs.set_signature(db, f["id"], SignatureIn(signee=True))


async def test_only_admin_can_set_signature_when_auth_is_on(db):
    from crud_api.core.deps import require_admin
    from crud_api.core.errors import ForbiddenError

    db.add_all([M.Role(id=1, code="ADMIN", libelle="Administrateur"), M.Role(id=2, code="LECTURE", libelle="Consultation"),
                M.Utilisateur(id=1, nom_utilisateur="admin", mot_de_passe_hash="x", role_id=1),
                M.Utilisateur(id=2, nom_utilisateur="lecteur", mot_de_passe_hash="x", role_id=2)])
    await db.commit()
    assert await require_admin(None, db) is None  # authentification desactivee : ouvert, comme le reste de l'API
    admin = await db.get(M.Utilisateur, 1)
    assert await require_admin(admin, db) is admin
    with pytest.raises(ForbiddenError):
        await require_admin(await db.get(M.Utilisateur, 2), db)
