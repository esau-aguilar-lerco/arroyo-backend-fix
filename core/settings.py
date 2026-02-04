import os
from pathlib import Path
from datetime import timedelta

from corsheaders.defaults import default_headers
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv
import dj_database_url
load_dotenv()



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", default='')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

IS_LOCAL = os.environ.get("IS_LOCAL", 'True').lower() in ['true', 'yes', '1']
ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1']
CORS_ALLOW_HEADERS = list(default_headers) + [
    'authorization',
]

# Application definition

INSTALLED_APPS = [
    #'jazzmin',
    'corsheaders',  # 👈 AQUI
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_yasg',
    'drf_spectacular'
]
default_app_config = 'apps.inventario.apps.InventarioConfig'

MY_APPS =[
    'apps.logger',
    'apps.base',
    'apps.contabilidad',
    'apps.erp',
    'apps.credito',
    'apps.inventario',
    'apps.usuarios',
    'apps.direccion',
]
INSTALLED_APPS += MY_APPS

AUTH_USER_MODEL = 'usuarios.Usuario'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.logger.middleware.middleware.RequestLoggingMiddleware',
]


ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {'default':  dj_database_url.config(default=os.getenv('DATABASE_URL'))}



# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/


LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    #'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',  # ✅ cambia esto
    'DEFAULT_AUTHENTICATION_CLASSES': (
         'rest_framework.authentication.SessionAuthentication',  # Para interfaz web
            #'rest_framework_simplejwt.authentication.JWTTokenUserAuthentication',
            'rest_framework_simplejwt.authentication.JWTAuthentication', 
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        #'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ),

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    #'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 5,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=20),
    "TOKEN_OBTAIN_SERIALIZER": "apps.base.token_jwt.MyTokenObtainPairSerializer",
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'APIS ARROYO',
    'VERSION': '2.0',

    # 🔥 Ignorar warnings y errores no críticos
    'DISABLE_ERRORS_AND_WARNINGS': True,
}



CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]


# Carga automática de datos SEPOMEX
APPLY_LOAD_SEPOMEX = True
