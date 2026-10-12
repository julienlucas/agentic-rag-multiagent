"""
Originaux des documents déposés (PDF, DOCX…), et leur copie PDF pour le visualiseur.

Rangés par hash de contenu dans DOCUMENT_STORAGE_DIR : un volume Railway en production
(ex. /data/documents), un dossier local en développement. `<hash><extension>` est l'original ;
un format converti en PDF (DOCX, PPTX…) a son `<hash>.pdf` à côté.

Un même fichier déposé par deux utilisateurs n'est stocké qu'une fois ; l'accès se contrôle à la
lecture, par l'espace qui l'indexe (endpoints), et le fichier n'est effacé que lorsque plus aucun
espace ne l'indexe.
"""
import os
import re
from pathlib import Path
from typing import List, Optional

from ..config.settings import settings

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SUFFIX_RE = re.compile(r"^\.[a-z0-9]{1,8}$")


def _root() -> Path:
    root = Path(settings.DOCUMENT_STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _name(file_hash: str, suffix: str) -> str:
    suffix = suffix.lower()
    if not _HASH_RE.match(file_hash or ""):
        raise ValueError(f"hash de document invalide: {file_hash!r}")
    if not _SUFFIX_RE.match(suffix):
        raise ValueError(f"extension invalide: {suffix!r}")
    return f"{file_hash}{suffix}"


def save(file_hash: str, suffix: str, content: bytes) -> str:
    """Écrit un fichier (une seule fois par contenu) et renvoie son nom. Écriture atomique."""
    name = _name(file_hash, suffix)
    path = _root() / name
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, path)
    return name


def path_of(name: str) -> Optional[Path]:
    """Le chemin d'un fichier stocké, s'il existe (nom contrôlé : jamais hors du dossier)."""
    if not name or "/" in name or "\\" in name or not _HASH_RE.match(name.split(".")[0]):
        return None
    path = Path(settings.DOCUMENT_STORAGE_DIR) / name
    return path if path.is_file() else None


def read(name: str) -> Optional[bytes]:
    path = path_of(name)
    return path.read_bytes() if path else None


def _names(file_hash: str) -> List[str]:
    root = Path(settings.DOCUMENT_STORAGE_DIR)
    if not _HASH_RE.match(file_hash or "") or not root.is_dir():
        return []
    return [p.name for p in root.glob(f"{file_hash}.*") if not p.name.endswith(".tmp")]


def find(file_hash: str) -> Optional[Path]:
    """L'original d'un document, s'il a été stocké (les documents antérieurs au stockage n'en ont pas)."""
    names = _names(file_hash)
    return path_of(names[0]) if names else None


def find_pdf(file_hash: str) -> Optional[Path]:
    """Le PDF d'un document (l'original ou sa conversion), s'il a été stocké."""
    return path_of(f"{file_hash}.pdf") if _HASH_RE.match(file_hash or "") else None


def remove(file_hash: str) -> None:
    """Efface l'original et sa conversion."""
    for name in _names(file_hash):
        (Path(settings.DOCUMENT_STORAGE_DIR) / name).unlink(missing_ok=True)


def api_url(file_hash: str) -> str:
    """Chemin de l'endpoint de la démo qui sert l'original (le frontend y ajoute session_id)."""
    return f"/api/documents/{file_hash}/file"
