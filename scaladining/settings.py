"""Django settings for Scala Dining."""

import os
from email.utils import getaddresses

from environs import Env

# Include Scala settings
# noinspection PyUnresolvedReferences
from scaladining.scala_settings import *  # noqa: F403 F401

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = Env()


@env.parser_for('file')
def file_parser(value):
    if not value:
        return ''
    with open(value) as f:
        return f.read()


env.read_env(path=os.path.join(BASE_DIR, '.env'), recurse=False)

DEBUG = env.bool('DINING_DEBUG', default=False)

SECRET_KEY = env.str('DINING_SECRET_KEY', default='') or env.file('DINING_SECRET_KEY_FILE')

ALLOWED_HOSTS = env.list('DINING_ALLOWED_HOSTS', default='')

AUTH_USER_MODEL = 'userdetails.User'

# django.contrib.admin is replaced by scaladining.apps.MyAdminConfig
INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',  # For static files

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',

    'dining.apps.DiningConfig',
    'creditmanagement.apps.CreditManagementConfig',
    'general.apps.GeneralConfig',
    'groceries.apps.GroceriesConfig',
    'directdebit.apps.DirectDebitConfig',
    'scaladining.apps.MyAdminConfig',

    'allauth.account',  # This needs to be before userdetails due to admin.site.unregister
    'userdetails.apps.UserDetailsConfig',

    'dal',
    'dal_select2',
    'widget_tweaks',
    'allauth',
    'allauth.socialaccount',
    'allauthproviders.quadrivium',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'scaladining.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'assets/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'scaladining.context_processors.dining'
            ],
        },
    },
]

WSGI_APPLICATION = 'scaladining.wsgi.application'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

STATIC_ROOT = env.str('DINING_STATIC_ROOT', default=os.path.join(BASE_DIR, 'static'))
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'assets/static')]
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_ROOT = env.str('DINING_MEDIA_ROOT', default=os.path.join(BASE_DIR, 'uploads'))
MEDIA_URL = env.str('DINING_MEDIA_URL', default='/media/')

DATABASES = {'default': env.dj_db_url('DINING_DATABASE_URL', default='sqlite:///db.sqlite3')}
if not DATABASES['default'].get('PASSWORD'):
    DATABASES['default']['PASSWORD'] = env.file('DINING_DATABASE_PASSWORD_FILE', default='')

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
TIME_ZONE = 'Europe/Amsterdam'
USE_TZ = True
# This imports Dutch date/time formats but turns off localization and internationalization so that dates use English
# names for months/weekdays, but Dutch format.
from django.conf.locale.nl.formats import *

# Use English format for numbers because the Dutch format is just stupid
DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','
USE_L10N = False
USE_I18N = False
USE_THOUSAND_SEPARATOR = True

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

# See https://github.com/migonzalvar/dj-email-url
email_config = env.dj_email_url('DINING_EMAIL_URL', default='console:')
EMAIL_HOST = email_config['EMAIL_HOST']
EMAIL_PORT = email_config['EMAIL_PORT']
EMAIL_HOST_USER = email_config['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = email_config['EMAIL_HOST_PASSWORD'] or env.file('DINING_EMAIL_PASSWORD_FILE', default='')
EMAIL_BACKEND = email_config['EMAIL_BACKEND']
EMAIL_USE_TLS = email_config['EMAIL_USE_TLS']
EMAIL_USE_SSL = email_config['EMAIL_USE_SSL']

DEFAULT_FROM_EMAIL = env.str('DINING_DEFAULT_FROM_EMAIL', default='webmaster@localhost')
SERVER_EMAIL = env.str('DINING_SERVER_EMAIL', default='root@localhost')
ADMINS = getaddresses(env.list('DINING_ADMINS', default=''))

# Allauth configuration
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_FORMS = {
    'change_password': 'userdetails.forms_allauth.CustomChangePasswordForm',
    'reset_password_from_key': 'userdetails.forms_allauth.CustomResetPasswordKeyForm',
}
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
# Set to None to ask the user ("Remember me?")
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_ADAPTER = "userdetails.externalaccounts.SocialAccountAdapter"

# HTTP security
if env.bool('DINING_COOKIE_SECURE', default=False):
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True

# We're running behind a proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# The message given here will be shown at the top of every page.
#
# Use it for instance when running a staging deployment, to notify the users
# about this.
SITE_NOTICE = env.str('SITE_NOTICE', default='Development version')
