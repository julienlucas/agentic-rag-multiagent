from docling.document_converter import DocumentConverter
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
import os

### 🔹 Analyse PDF avec Docling
### Un OCR très capable - tableaux, diagrammes bien décryptés, ect... mais très lent)
def parse_with_docling(pdf_path):
    """
    Analyse un PDF en utilisant Docling, extrait le contenu markdown,
    et affiche le contenu extrait complet.
    """
    try:
        # S'assurer que le fichier existe
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Fichier non trouvé: {pdf_path}")

        # Initialiser le convertisseur Docling
        converter = DocumentConverter()
        markdown_document = converter.convert(pdf_path).document.export_to_markdown()

        # Définir les en-têtes pour la division (modifier selon les besoins)
        headers_to_split_on = [
            ("#", "En-tête 1"),
            ("##", "En-tête 2"),
            ("###", "En-tête 3"),
        ]

        # Initialiser le diviseur Markdown
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        docs_list = markdown_splitter.split_text(markdown_document)

        # Afficher les sections extraites complètes
        print("\n✅ Contenu Extrait Complet (Docling):")
        for idx, doc in enumerate(docs_list):
            print(f"\n🔹 Section {idx + 1}:\n{doc}\n" + "-"*80)

        return docs_list

    except Exception as e:
        print(f"\n❌ Erreur lors du traitement Docling: {e}")
        return []

### 🔹 Analyse PDF avec LangChain
def parse_with_langchain(pdf_path):
    """
    Analyse un PDF en utilisant PyPDFLoader de LangChain et affiche le texte extrait complet.
    """
    try:
        # S'assurer que le fichier existe
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Fichier non trouvé: {pdf_path}")

        # Charger le PDF en utilisant PyPDFLoader
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        # Extraire le texte de toutes les pages
        text = "\n\n".join([page.page_content for page in pages])

        # Afficher le contenu extrait complet
        print("\n✅ Contenu Extrait Complet (LangChain):\n")
        print(text)
        print("\n" + "="*100)

        return text

    except Exception as e:
        print(f"\n❌ Erreur lors du traitement LangChain: {e}")
        return ""

### 🔹 Exécution Principale
def main():
    ocr_path = "test/ocr_test.pdf"
    scanned_pdf_path = "test/sample.png"

    print("\n🔍 Exécution de l'extraction Docling pour OCR...")
    docling_docs = parse_with_docling(ocr_path)

    print("\n🔍 Exécution de l'extraction LangChain pour OCR...")
    langchain_text = parse_with_langchain(ocr_path)

    print("\n🔍 Exécution de l'extraction Docling pour PDF scanné...")
    docling_docs = parse_with_docling(scanned_pdf_path)

    print("\n🔍 Exécution de l'extraction LangChain pour PDF scanné...")
    langchain_text = parse_with_langchain(scanned_pdf_path)

if __name__ == "__main__":
    main()
