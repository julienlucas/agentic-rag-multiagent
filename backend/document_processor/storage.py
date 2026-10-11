"""
Originaux des documents déposés (PDF, DOCX…), gardés pour être rouverts depuis une citation.

Rangés par hash de contenu dans DOCUMENT_STORAGE_DIR : un volume persistant en production
(Railway), un dossier local en développement. Un même fichier déposé par deux utilisateurs
n'est stocké qu'une fois ; l'accès se contrôle à la lecture, par l'espace du tenant
(endpoints.document_file), et le fichier n'est effacé que lorsque plus aucun espace ne l'indexe.
"""
import os
import re
from pathlib import Path
from typing import Optional

from ..config.settings import settings

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _root() -> Path:
    root = Path(settings.DOCUMENT_STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save(file_hash: str, name: str, content: bytes) -> Path:
    """Écrit l'original (une seule fois par contenu). Écriture atomique : jamais de fichier tronqué."""
    if not _HASH_RE.match(file_hash):
        raise ValueError(f"hash de document invalide: {file_hash!r}")
    path = _root() / f"{file_hash}{Path(name).suffix.lower()}"
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, path)
    return path


def find(file_hash: str) -> Optional[Path]:
    """L'original d'un document, s'il a été stocké (les documents antérieurs au stockage n'en ont pas)."""
    if not _HASH_RE.match(file_hash or ""):
        return None
    root = Path(settings.DOCUMENT_STORAGE_DIR)
    if not root.is_dir():
        return None
    return next((p for p in root.glob(f"{file_hash}.*") if not p.name.endswith(".tmp")), None)


def remove(file_hash: str) -> None:
    path = find(file_hash)
    if path is not None:
        path.unlink(missing_ok=True)


def api_url(file_hash: str) -> str:
    """Chemin de l'endpoint qui sert l'original (relatif à l'API ; le frontend y ajoute session_id)."""
    return f"/api/documents/{file_hash}/file"
