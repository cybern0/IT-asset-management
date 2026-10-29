"""Profil utilisateur : regles de modification du nom et du mot de passe (sans base de donnees)."""
import pytest
from pydantic import ValidationError

from crud_api.core.errors import UnprocessableError
from crud_api.core.security import hash_password, verify_password
from crud_api.models import Utilisateur
from crud_api.schemas.user import ProfileUpdate
from crud_api.services.user_service import user_service

pytestmark = pytest.mark.nodb


class FakeDB:
    def __init__(self):
        self.info, self.added, self.commits = {}, [], 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1


@pytest.fixture
def user(monkeypatch):
    u = Utilisateur(id=7, nom_utilisateur="rakoto", mot_de_passe_hash=hash_password("ancien-mdp-1"), role_id=1, actif=True)

    async def get(db, item_id):
        return u

    monkeypatch.setattr(user_service, "get", get)
    return u


async def test_wrong_current_password_is_422_not_401(user):
    with pytest.raises(UnprocessableError) as e:
        await user_service.update_profile(FakeDB(), user, ProfileUpdate(mot_de_passe_actuel="faux", nom_utilisateur="autre"))
    assert e.value.status_code == 422 and e.value.field == "mot_de_passe_actuel" and user.nom_utilisateur == "rakoto"


async def test_change_username_and_password_is_audited_without_secret(user):
    db = FakeDB()
    out = await user_service.update_profile(
        db, user, ProfileUpdate(mot_de_passe_actuel="ancien-mdp-1", nom_utilisateur="  jean  ", nouveau_mot_de_passe="nouveau-mdp-2"))
    assert out.nom_utilisateur == "jean" and verify_password("nouveau-mdp-2", user.mot_de_passe_hash)
    assert db.commits == 1 and db.added[0].action == "UPDATE_PROFIL"
    assert db.added[0].details == {"champs": ["nom_utilisateur", "mot_de_passe"]}
    assert "nouveau-mdp-2" not in str(db.added[0].details)


async def test_nothing_to_change_and_same_password_rejected(user):
    with pytest.raises(UnprocessableError):
        await user_service.update_profile(FakeDB(), user, ProfileUpdate(mot_de_passe_actuel="ancien-mdp-1", nom_utilisateur="rakoto"))
    with pytest.raises(UnprocessableError) as e:
        await user_service.update_profile(FakeDB(), user, ProfileUpdate(mot_de_passe_actuel="ancien-mdp-1", nouveau_mot_de_passe="ancien-mdp-1"))
    assert e.value.field == "nouveau_mot_de_passe"


def test_new_password_min_length():
    with pytest.raises(ValidationError):
        ProfileUpdate(mot_de_passe_actuel="x", nouveau_mot_de_passe="court")
