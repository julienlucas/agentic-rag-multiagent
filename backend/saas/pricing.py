"""
Grille tarifaire : la seule source des prix, servie au frontend par GET /api/pricing.

1 crédit = 0,01 € TTC. Coûts mesurés (docs/plan-produit.md §1) :
- une question ≈ 0,06 € (Sonnet 4.6 + Haiku + rerank) → 20 crédits, marge brute ≈ 70 % ;
- une page indexée ≈ 0,001 € (Mistral OCR + Cohere Embed v4) → 1 crédit.
Changer une valeur ici change le prix affiché et le prix facturé.
"""
from ..document_processor import formats

CREDIT_VALUE_EUR = 0.01
QUESTION_CREDITS = 20
PAGE_CREDITS = 1

PLANS = {
    # Gratuit : 20 documents, 1 000 pages, indexation offerte, 300 crédits de bienvenue (15 questions).
    "free": {"documents": 20, "pages": 1000, "indexing_free": True},
    # À la carte : dès le premier achat.
    "paid": {"documents": 500, "pages": 20000, "indexing_free": False},
}
WELCOME_CREDITS = 300

# Passages Qdrant par page, plafond de RAM : ~10 en moyenne sur FinanceBench, large marge.
CHUNKS_PER_PAGE = 15

PACKS = [
    {"id": "pack_10", "price_eur": 10, "credits": 1000},
    {"id": "pack_25", "price_eur": 25, "credits": 2600},
    {"id": "pack_50", "price_eur": 50, "credits": 5400},
    {"id": "pack_100", "price_eur": 100, "credits": 11000},
]
PACKS_BY_ID = {p["id"]: p for p in PACKS}


def public() -> dict:
    return {
        "credit_value_eur": CREDIT_VALUE_EUR,
        "question_credits": QUESTION_CREDITS,
        "page_credits": PAGE_CREDITS,
        "free": {"documents": PLANS["free"]["documents"], "pages": PLANS["free"]["pages"],
                 "welcome_credits": WELCOME_CREDITS},
        "paid": {"documents": PLANS["paid"]["documents"], "pages": PLANS["paid"]["pages"]},
        "packs": PACKS,
        "formats": formats.EXTENSIONS,
    }
