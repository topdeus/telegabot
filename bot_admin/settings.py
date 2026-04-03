import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env файла
load_dotenv(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

allowed_hosts = {'127.0.0.1', 'localhost'}
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname:
    allowed_hosts.add(render_hostname)

extra_hosts = os.environ.get('ALLOWED_HOSTS', '')
for host in extra_hosts.split(','):
    host = host.strip()
    if host:
        allowed_hosts.add(host)

ALLOWED_HOSTS = sorted(allowed_hosts)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'telegram_bot',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bot_admin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'bot_admin.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки бота (будут браться из .env на хостинге)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')

if not DEBUG:
    STORAGES = {
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
    }

csrf_trusted_origins = []
render_external_url = os.environ.get('RENDER_EXTERNAL_URL')
if render_external_url:
    csrf_trusted_origins.append(render_external_url)

extra_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
for origin in extra_csrf.split(','):
    origin = origin.strip()
    if origin:
        csrf_trusted_origins.append(origin)

CSRF_TRUSTED_ORIGINS = csrf_trusted_origins

if os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    INSTALLED_APPS.append('storages')
    aws_custom_domain = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
    aws_options = {
        'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
        'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        'bucket_name': os.environ.get('AWS_STORAGE_BUCKET_NAME'),
        'region_name': os.environ.get('AWS_S3_REGION_NAME'),
        'endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL'),
        'default_acl': None,
        'querystring_auth': False,
        'file_overwrite': False,
    }
    if aws_custom_domain:
        aws_options['custom_domain'] = aws_custom_domain

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': aws_options,
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    if aws_custom_domain:
        MEDIA_URL = f'https://{aws_custom_domain}/'
