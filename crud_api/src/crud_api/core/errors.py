# Erreurs metier : le service les leve, main.py les convertit en reponses HTTP
class ServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str, field: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.field = field


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    """Violation d'unicite, d'etat ou de cle etrangere (409)."""

    status_code = 409


class UnprocessableError(ServiceError):
    """Donnee refusee par une regle metier (422)."""

    status_code = 422


class UnauthorizedError(ServiceError):
    status_code = 401


class ForbiddenError(ServiceError):
    """Action reservee a un role (403)."""

    status_code = 403
