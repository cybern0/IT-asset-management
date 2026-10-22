import uvicorn

from crud_api.config import get_settings


def main() -> None:
    """Point d'entree `crud-api` : lance le serveur de developpement."""
    settings = get_settings()
    uvicorn.run(
        "crud_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
