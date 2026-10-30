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

    # Fichiers envoyes (relatif au dossier de lancement, ou chemin absolu)
    upload_dir: str = "uploads"
    max_image_mb: int = 5

    # Nom de la structure imprime sur les fiches de detention (PDF)
    structure_name: str = ""

    # Notifications sans serveur (liens mailto:, sms:, wa.me) : adresse publique de l'interface et indicatif pays
    app_url: str = ""  # ex. https://parc.exemple.mg ; ajoute un lien vers la demande dans les messages
    country_code: str = "261"  # indicatif ajoute aux numeros locaux commencant par 0 (261 = Madagascar)

    # Tableau de bord : objectifs et seuils (les statuts OK / Alerte en decoulent)
    objectif_attribution_min: float = 75  # taux d'attribution cible, en %
    objectif_attribution_max: float = 85
    objectif_stock_min: int = 50  # equipements en stock
    objectif_maintenance_max: int = 15
    objectif_age_moyen_max: float = 3.5  # ans
    objectif_anciens_max: int = 40  # equipements de plus de `age_ancien_ans`
    age_ancien_ans: int = 5
    stock_categorie_alerte_pct: float = 10  # stock faible si < x % du total de la categorie
    stock_categorie_cible_pct: float = 15  # on recommande de recompleter jusqu'a x %
    licence_alerte_jours: int = 60  # licence bientot expiree
    dossier_retard_jours: int = 30  # dossier d'attribution ouvert depuis trop longtemps

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
