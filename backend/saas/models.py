"""
Le produit : un workspace par utilisateur, ses documents, son registre de crédits, ses conversations.

Postgres fait foi pour la liste des documents ; Qdrant en est l'index, sous le tenant
`Workspace.tenant_id`. Le solde de crédits n'est stocké nulle part : c'est la somme du registre
(CreditEntry, en ajout seul), lue sous verrou du workspace (credits.py).
"""
import uuid

from django.conf import settings
from django.db import models

from . import pricing


class Workspace(models.Model):
    PLAN_CHOICES = [("free", "Gratuit"), ("paid", "À la carte")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace")
    plan = models.CharField(max_length=16, choices=PLAN_CHOICES, default="free")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def tenant_id(self) -> str:
        """L'espace Qdrant. Préfixe « ws- » : la démo publique, elle, vit sous « demo-… »."""
        return f"ws-{self.id.hex}"

    @property
    def limits(self) -> dict:
        return pricing.PLANS[self.plan]

    def __str__(self):
        return f"{self.owner} ({self.plan})"


class Document(models.Model):
    STATUS_CHOICES = [
        ("queued", "En attente"), ("processing", "En cours"), ("ready", "Prêt"), ("error", "Erreur"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="documents")
    name = models.CharField(max_length=255)  # unique dans le workspace : c'est la « source » dans Qdrant
    kind = models.CharField(max_length=16)  # famille de formats.py : pdf, office, image, text, html, sheet
    extension = models.CharField(max_length=12)
    size = models.PositiveBigIntegerField()
    file_hash = models.CharField(max_length=64)
    pages = models.PositiveIntegerField(default=0)  # estimées à la réception, exactes après indexation
    chunks = models.PositiveIntegerField(default=0)
    has_pdf = models.BooleanField(default=False)  # un PDF (original ou converti) s'ouvre dans le visualiseur
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued", db_index=True)
    error = models.TextField(blank=True, default="")
    credits = models.IntegerField(default=0)  # crédits facturés pour l'indexation (net des ajustements)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "file_hash"], name="unique_document_per_workspace"),
            models.UniqueConstraint(fields=["workspace", "name"], name="unique_document_name_per_workspace"),
        ]

    def __str__(self):
        return self.name


class CreditEntry(models.Model):
    REASONS = [
        ("welcome", "Crédits de bienvenue"), ("purchase", "Achat"), ("question", "Question"),
        ("indexing", "Indexation"), ("refund", "Remboursement"), ("adjustment", "Ajustement"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="credit_entries")
    delta = models.IntegerField()
    reason = models.CharField(max_length=16, choices=REASONS)
    label = models.CharField(max_length=255, blank=True, default="")
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    reference = models.CharField(max_length=255, blank=True, default="")  # paiement Stripe, run LangSmith
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    question = models.TextField()
    answer = models.TextField()
    verification_report = models.TextField(blank=True, default="")
    citations = models.JSONField(default=list)
    credits = models.IntegerField(default=0)
    run_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Purchase(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="purchases")
    pack = models.CharField(max_length=32)
    price_eur = models.DecimalField(max_digits=8, decimal_places=2)
    credits = models.IntegerField()
    stripe_session_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=16, default="pending")  # pending | paid
    created_at = models.DateTimeField(auto_now_add=True)
