import os
import hashlib
import pickle
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from mistralai import Mistral
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from ..config import constants
from ..config.settings import settings
from ..utils.logging import logger
from .chunkers import get_chunking_strategy
from ..retriever.embeddings import get_embeddings

class DocumentProcessor:
    def __init__(self):
        self.headers = [("#", "Header 1"), ("##", "Header 2")]
        self.cache_dir = Path(settings.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = Mistral(api_key=settings.MISTRALAI_API_KEY)
        self.batch_size = 3  # Traiter 3 pages à la fois
        # Markdown OCR page par page, par source : alimente le PageStore (outils grep /
        # read_page de l'agent de recherche). Rempli par process(), cache compris.
        self.pages: dict = {}

    def _validate_files(self, files: List) -> None:
        """Valider la taille totale des fichiers téléchargés."""
        total_size = 0
        for f in files:
            if hasattr(f, 'file_obj'):
                # Fichier uploadé - utiliser la taille du file_obj
                f.file_obj.seek(0, 2)  # Aller à la fin
                total_size += f.file_obj.tell()
                f.file_obj.seek(0)  # Remettre au début
            else:
                # Fichier local - utiliser os.path.getsize
                total_size += os.path.getsize(f.name)

        if total_size > constants.MAX_TOTAL_SIZE:
            raise ValueError(f"La taille totale dépasse la limite de {constants.MAX_TOTAL_SIZE//1024//1024}MB")

    def process(self, files: List) -> List:
        """Traiter les fichiers avec mise en cache pour les requêtes suivantes"""
        self._validate_files(files)
        all_chunks = []
        seen_hashes = set()

        logger.info(f"Début du traitement de {len(files)} fichiers")

        for file in files:
            try:
                logger.info(f"Traitement du fichier: {file.name}")

                # Générer un hachage basé sur le contenu pour la mise en cache
                if hasattr(file, 'file_obj'):
                    # Fichier uploadé - lire depuis file_obj
                    file.file_obj.seek(0)
                    content = file.file_obj.read()
                    file_hash = self._generate_hash(content)
                else:
                    # Fichier local - lire depuis le chemin
                    with open(file.name, "rb") as f:
                        file_hash = self._generate_hash(f.read())
                # v3 : le cache porte aussi les pages OCR (v2 : metadata["page"] sur les
                # chunks). La version dans la clé invalide les caches antérieurs.
                cache_path = self.cache_dir / f"{file_hash}-v3.pkl"

                if self._is_cache_valid(cache_path):
                    logger.info(f"Chargement depuis le cache: {file.name}")
                    chunks, pages = self._load_from_cache(cache_path)
                else:
                    logger.info(f"Traitement et mise en cache: {file.name}")
                    chunks, pages = self._process_file(file)
                    logger.info(f"Chunks générés pour {file.name}: {len(chunks)}")

                    if chunks:
                        self._save_to_cache(chunks, pages, cache_path)
                        logger.info(f"Chunks sauvegardés en cache pour {file.name}")
                    else:
                        logger.warning(f"Aucun chunk généré pour {file.name}")
                if pages:
                    self.pages[file.name] = pages

                # Dédupliquer les chunks entre les fichiers
                for chunk in chunks:
                    chunk_hash = self._generate_hash(chunk.page_content.encode())
                    if chunk_hash not in seen_hashes:
                        all_chunks.append(chunk)
                        seen_hashes.add(chunk_hash)

            except Exception as e:
                logger.error(f"Échec du traitement de {file.name}: {str(e)}")
                continue

        logger.info(f"Total des chunks uniques: {len(all_chunks)}")
        return all_chunks

    def _process_file(self, file) -> tuple:
        """Logique de traitement avec Mistral OCR. Retourne (chunks, pages)."""
        if not file.name.endswith(('.pdf', '.docx', '.txt', '.md')):
            logger.warning(f"Ignorer le type de fichier non supporté: {file.name}")
            return [], []

        # Lire le contenu du fichier en bytes
        if hasattr(file, 'file_obj'):
            # Fichier uploadé - lire depuis file_obj
            file.file_obj.seek(0)
            file_content = file.file_obj.read()
        else:
            # Fichier local - lire depuis le chemin
            with open(file.name, "rb") as f:
                file_content = f.read()

        logger.info(f"Fichier lu, taille: {len(file_content)} bytes")

        # Encoder le contenu en base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')

        # Traiter le document entier d'un coup
        try:
            response = self.client.ocr.process(
                model=settings.MODEL_OCR_ID,
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{file_base64}"
                },
                include_image_base64=True
            )

            total_pages = len(response.pages)
            logger.info(f"Document traité avec {total_pages} pages")

            # Collecter tout le markdown
            all_markdown = [page.markdown for page in response.pages]

            # Assembler le markdown en gardant la trace des frontières de page :
            # le chunking reste sémantique sur le document entier (qualité préservée),
            # et chaque chunk est ensuite rattaché à sa page par correspondance d'offset.
            separator = "\n\n"
            page_spans = []
            cursor = 0
            for page_idx, page_md in enumerate(all_markdown):
                page_spans.append((cursor, cursor + len(page_md), page_idx))
                cursor += len(page_md) + len(separator)
            markdown = separator.join(all_markdown)

            # Utiliser la stratégie de chunking configurée
            if settings.CHUNKING_STRATEGY == "semantic" or settings.PARENT_CHILD_ENABLED:
                # Passer les embeddings pour le chunking sémantique
                embeddings = get_embeddings() if settings.CHUNKING_STRATEGY == "semantic" else None
                chunker = get_chunking_strategy(embeddings=embeddings)
                metadata = {"source": file.name}
                chunks = chunker.split(markdown, metadata)
                self._attach_pages(chunks, markdown, page_spans)
                logger.info(f"Chunking avec stratégie '{settings.CHUNKING_STRATEGY}': {len(chunks)} chunks")
                return chunks, all_markdown
            else:
                # Fallback vers la méthode originale (header-aware + recursive)
                header_splitter = MarkdownHeaderTextSplitter(self.headers)
                header_chunks = header_splitter.split_text(markdown)
                chunk_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP,
                )
                return chunk_splitter.split_documents(header_chunks), all_markdown

        except Exception as e:
            logger.error(f"Erreur lors du traitement OCR: {str(e)}")
            return [], []

    @staticmethod
    def _attach_pages(chunks, markdown: str, page_spans) -> None:
        """
        Rattache chaque chunk à sa page d'origine (metadata["page"], zero-indexed).

        Le chunker sémantique découpe le markdown assemblé sans le réécrire : on retrouve
        donc chaque chunk par recherche de ses premiers caractères. Le curseur avance de
        façon monotone (les chunks sortent dans l'ordre du document), avec repli sur une
        recherche globale. Un chunk introuvable reste simplement sans page, comme avant.
        """
        import bisect

        if not page_spans:
            return
        starts = [span[0] for span in page_spans]
        cursor = 0
        located = 0
        for chunk in chunks:
            probe = (chunk.page_content or "")[:120].strip()
            if not probe:
                continue
            pos = markdown.find(probe, cursor)
            if pos == -1:
                pos = markdown.find(probe)
            if pos == -1:
                continue
            cursor = pos
            located += 1
            idx = bisect.bisect_right(starts, pos) - 1
            if idx >= 0:
                chunk.metadata["page"] = page_spans[idx][2]

        logger.info(
            f"Pages rattachées: {located}/{len(chunks)} chunks "
            f"({len(page_spans)} pages OCRisées)"
        )

    def _generate_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _save_to_cache(self, chunks: List, pages: List, cache_path: Path):
        with open(cache_path, "wb") as f:
            pickle.dump({
                "timestamp": datetime.now().timestamp(),
                "chunks": chunks,
                "pages": pages,
            }, f)

    def _load_from_cache(self, cache_path: Path) -> tuple:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data["chunks"], data.get("pages") or []

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return cache_age < timedelta(days=settings.CACHE_EXPIRE_DAYS)