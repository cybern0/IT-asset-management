# Configuration (.env)
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables d'environnement, lues depuis l'environnement ou le fichier `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Parc informatique - API"

    # Serveur de developpement (commande `crud-api`)
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True

    # Base de donnees (pilote asyncpg obligatoire)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/parc"
    db_schema: str = "eparc"
    db_echo: bool = False

    # Origines autorisees pour le frontend, separees par des virgules
    cors_origins: str = "http://localhost:5173"

    # Authentification : desactivee par defaut (l'UI n'a pas encore d'ecran de connexion)
    auth_enabled: bool = False
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    # Si renseigne et qu'aucun utilisateur n'existe, cree le compte `admin` au demarrage
    bootstrap_admin_password: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
