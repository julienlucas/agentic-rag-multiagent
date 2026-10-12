"""Comptes : un workspace et les crédits de bienvenue à la création ; suppression complète."""
from django.db import transaction

from ..utils.logging import logger
from ..vectorstore import get_store
from . import credits, pricing
from .models import Workspace


def create_workspace(sender, instance, created, **kwargs):
    """Signal post_save sur User : chaque compte reçoit son espace et ses crédits de bienvenue."""
    if not created:
        return
    with transaction.atomic():
        workspace = Workspace.objects.create(owner=instance)
        credits.credit(workspace, pricing.WELCOME_CREDITS, "welcome", "Crédits de bienvenue")


def workspace_of(user) -> Workspace:
    """Le workspace d'un utilisateur (créé à la volée pour un compte antérieur au produit)."""
    try:
        return user.workspace
    except Workspace.DoesNotExist:
        create_workspace(None, user, created=True)
        return Workspace.objects.get(owner=user)


def delete_account(user):
    """Efface tout : vecteurs et pages (Qdrant), originaux devenus orphelins, puis la base."""
    from .ingestion import release_original

    workspace = workspace_of(user)
    hashes = list(workspace.documents.values_list("file_hash", flat=True))
    get_store().for_tenant(workspace.tenant_id).delete_all()
    tenant_id = workspace.tenant_id
    user.delete()  # cascade : workspace, documents, crédits, conversations, achats
    for digest in hashes:
        release_original(digest)
    logger.info(f"Compte supprimé : {tenant_id}, {len(hashes)} document(s)")
