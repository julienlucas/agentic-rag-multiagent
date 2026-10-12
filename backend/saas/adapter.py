"""E-mails d'allauth (codes de vérification, mot de passe oublié) signés du nom du produit."""
from types import SimpleNamespace
from urllib.parse import urlparse

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        # Sans ce nom, l'e-mail est signé de l'hôte de l'API (« xxx.up.railway.app »), pas du produit.
        domain = urlparse(settings.FRONTEND_URL).netloc if settings.FRONTEND_URL else ""
        site = SimpleNamespace(name=settings.PRODUCT_NAME, domain=domain or settings.PRODUCT_NAME)
        super().send_mail(template_prefix, email, {"current_site": site, **context})
