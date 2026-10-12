"""
Registre des crédits : chaque mouvement est une écriture (CreditEntry), le solde en est la somme.

Toute dépense passe par `charge()`, sous verrou du workspace (SELECT … FOR UPDATE) : deux
questions simultanées ne peuvent pas dépenser deux fois le même solde. Une action qui échoue
est remboursée par une écriture inverse (`refund()`), jamais par un effacement.
"""
from django.db import transaction
from django.db.models import Sum

from .models import CreditEntry, Workspace


class InsufficientCredits(Exception):
    def __init__(self, needed: int, balance: int):
        self.needed, self.balance = needed, balance
        super().__init__(f"Crédits insuffisants : {needed} nécessaires, {balance} disponibles.")


def balance(workspace: Workspace) -> int:
    return CreditEntry.objects.filter(workspace=workspace).aggregate(s=Sum("delta"))["s"] or 0


def _locked(workspace: Workspace) -> Workspace:
    return Workspace.objects.select_for_update().get(pk=workspace.pk)


def charge(workspace: Workspace, amount: int, reason: str, label: str = "", document=None,
           reference: str = "") -> CreditEntry:
    """Débite `amount` crédits, ou lève InsufficientCredits sans rien écrire."""
    with transaction.atomic():
        _locked(workspace)
        current = balance(workspace)
        if amount > current:
            raise InsufficientCredits(amount, current)
        return CreditEntry.objects.create(workspace=workspace, delta=-amount, reason=reason, label=label,
                                          document=document, reference=reference)


def credit(workspace: Workspace, amount: int, reason: str, label: str = "", document=None,
           reference: str = "") -> CreditEntry:
    return CreditEntry.objects.create(workspace=workspace, delta=amount, reason=reason, label=label,
                                      document=document, reference=reference)


def refund(workspace: Workspace, amount: int, label: str, document=None, reference: str = ""):
    if amount > 0:
        credit(workspace, amount, "refund", label, document=document, reference=reference)


def settle(workspace: Workspace, reserved: int, actual: int, label: str, document=None) -> int:
    """
    Ajuste une réservation au coût réel : rend la différence, ou débite le complément dans la
    limite du solde (une estimation trop basse ne met jamais le solde en négatif). Renvoie le
    montant finalement facturé.
    """
    if actual == reserved:
        return actual
    with transaction.atomic():
        _locked(workspace)
        if actual < reserved:
            credit(workspace, reserved - actual, "adjustment", label, document=document)
            return actual
        extra = min(actual - reserved, max(0, balance(workspace)))
        if extra:
            CreditEntry.objects.create(workspace=workspace, delta=-extra, reason="adjustment", label=label,
                                       document=document)
        return reserved + extra
