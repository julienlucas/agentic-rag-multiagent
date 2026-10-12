import os
from pathlib import Path

import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Signe aussi les jetons de vote (backend/evals/feedback/votes.py) : à définir en production.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", 'django-insecure-=cldztbc4jg&xl0!x673!*v2_=p$$eu)=7*f#d0#zs$44xx-h^')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ['*']
# Derrière le proxy de Railway (et de Vercel) : le schéma d'origine arrive dans X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Origines de confiance pour le CSRF (domaine du frontend en production, ex. https://app.exemple.fr).
# Le frontend (Vercel) relaie /api vers Railway : l'origine des requêtes est celle du frontend.
CSRF_TRUSTED_ORIGINS = [o.strip().strip('"') for o in (
    os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") + [os.getenv("CORS_ALLOWED_ORIGIN", ""), os.getenv("FRONTEND_URL", "")]
) if o.strip().strip('"')]
if DEBUG:  # le proxy Vite réécrit l'hôte : l'origine du frontend local doit être déclarée
    CSRF_TRUSTED_ORIGINS += [f"http://localhost:{p}" for p in (5173, 8080, 8081)]
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
WSGI_APPLICATION = 'backend.wsgi.app'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.headless',
    'backend.saas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Postgres en production (DATABASE_URL, fourni par Railway), SQLite en développement.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600, conn_health_checks=True,
    )
}

# --- Authentification : django-allauth en mode headless (SPA, cookie de session) ---------------
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Agentic Search")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
ACCOUNT_ADAPTER = "backend.saas.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_UNIQUE_EMAIL = True
# Un e-mail vérifié par compte : le gratuit (20 documents, 300 crédits) ne se multiplie pas.
ACCOUNT_EMAIL_VERIFICATION = os.getenv("ACCOUNT_EMAIL_VERIFICATION", "mandatory")
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/verifier-email",
    "account_reset_password": "/mot-de-passe-oublie",
    "account_reset_password_from_key": "/mot-de-passe-oublie?key={key}",
    "account_signup": "/inscription",
    "socialaccount_login_error": "/connexion?erreur=google",
}
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        }] if os.getenv("GOOGLE_CLIENT_ID") else [],
        "SCOPE": ["email", "profile"],
        "EMAIL_AUTHENTICATION": True,
    }
}
LOGIN_REDIRECT_URL = "/app"

# E-mails transactionnels (codes de vérification, mot de passe oublié) : SMTP en production
# (Resend, SES…), console en développement.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"{PRODUCT_NAME} <noreply@localhost>")
if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "frontend" / "dist",
]

# CORS - Allow frontend on Vercel to call the API
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:5173",
]
# Add your Vercel domain here, e.g.:
# CORS_ALLOWED_ORIGINS += ["https://your-app.vercel.app"]
import os
if os.environ.get("CORS_ALLOWED_ORIGIN"):
    CORS_ALLOWED_ORIGINS.append(os.environ.get("CORS_ALLOWED_ORIGIN"))

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'