# Taille maximale autorisée pour un seul fichier (50 MB)
MAX_FILE_SIZE: int = 50 * 1024 * 1024

# Taille maximale autorisée pour tous les fichiers téléchargés (200 MB)
MAX_TOTAL_SIZE: int = 200 * 1024 * 1024

# Types de fichiers autorisés pour le téléchargement
# Types de fichiers acceptés par la démo publique (exemples seulement, voir endpoints.load_file).
# L'espace connecté accepte tous les formats de backend/document_processor/formats.py.
ALLOWED_TYPES: list = [".pdf"]