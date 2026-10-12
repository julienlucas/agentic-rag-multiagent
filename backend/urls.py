from .endpoints import (
    index, process_question, load_file, list_documents, delete_document, delete_space,
    submit_feedback, document_file, document_page,
)
from django.urls import include, path, re_path
from .saas import views as app
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('', index),
    path('api/load-file', load_file),
    path('api/process-question', process_question),
    path('api/documents', list_documents),
    path('api/documents/page', document_page),
    path('api/documents/<str:file_hash>/file', document_file),
    path('api/delete-document', delete_document),
    path('api/delete-space', delete_space),
    path('api/feedback', submit_feedback),

    # Produit : comptes (allauth headless), tarifs, espace connecté, paiement.
    path('_allauth/', include('allauth.headless.urls')),
    path('accounts/', include('allauth.urls')),  # retour OAuth de Google
    path('api/pricing', app.pricing_view),
    path('api/me', app.me),
    path('api/app/documents', app.documents),
    path('api/app/documents/page', app.document_page),
    path('api/app/documents/<str:document_id>', app.document_detail),
    path('api/app/documents/<str:document_id>/file', app.document_file),
    path('api/app/ask', app.ask),
    path('api/app/conversations', app.conversations),
    path('api/app/conversations/<str:conversation_id>', app.conversation_detail),
    path('api/app/feedback', app.feedback),
    path('api/app/credits', app.credits_view),
    path('api/app/checkout', app.checkout),
    path('api/app/account', app.account),
    path('api/stripe/webhook', app.stripe_webhook),
]

# Routes du frontend (SPA) : Django sert index.html, le routeur React fait le reste.
urlpatterns += [
    re_path(r'^(?:a-propos|tarifs|connexion|inscription|verifier-email|mot-de-passe-oublie|app)(?:/.*)?$', index),
]

if settings.DEBUG:
    for static_dir in settings.STATICFILES_DIRS:
        urlpatterns += static(settings.STATIC_URL, document_root=static_dir)

    assets_dir = settings.BASE_DIR / "frontend" / "dist" / "assets"
    if assets_dir.exists():
        urlpatterns += [
            path('assets/<path:path>', serve, {'document_root': str(assets_dir)}),
        ]
