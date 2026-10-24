# Stockage des fichiers envoyes (images du materiel, scans des fiches signees)
import uuid
from pathlib import Path

from fastapi import UploadFile

from crud_api.config import get_settings
from crud_api.core.errors import NotFoundError, UnprocessableError

IMAGE_TYPES = {"jpg", "png", "webp"}
SCAN_TYPES = IMAGE_TYPES | {"pdf"}
MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf"}


def root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def detect_type(head: bytes) -> str | None:
    """Type reel du fichier d'apres ses premiers octets (on ne se fie pas a l'extension)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"%PDF-"):
        return "pdf"
    return None


async def save(file: UploadFile, subdir: str, prefix: str, allowed: set[str], max_mb: int) -> str:
    """Enregistre le fichier et renvoie son chemin relatif (a stocker en base)."""
    limit = max_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > limit:
            raise UnprocessableError(f"Fichier trop volumineux (maximum {max_mb} Mo).", field="file")
    kind = detect_type(bytes(data[:16]))
    if kind is None or kind not in allowed:
        formats = ", ".join(sorted(t.upper() if t == "pdf" else t.upper().replace("JPG", "JPEG") for t in allowed))
        raise UnprocessableError(f"Format non accepté (formats : {formats}).", field="file")
    rel = f"{subdir}/{prefix}-{uuid.uuid4().hex[:10]}.{kind}"
    target = root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(data))
    return rel


def path_of(rel: str) -> Path:
    """Chemin absolu d'un fichier stocke ; refuse toute sortie du dossier d'envoi."""
    base = root()
    p = (base / rel).resolve()
    if base not in p.parents or not p.is_file():
        raise NotFoundError("Fichier introuvable.")
    return p


def media_type(rel: str) -> str:
    return MIME.get(rel.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def remove(rel: str | None) -> None:
    if not rel:
        return
    try:
        p = (root() / rel).resolve()
        if root() in p.parents:
            p.unlink(missing_ok=True)
    except OSError:
        pass  # fichier deja absent ou verrouille : sans consequence pour la base
