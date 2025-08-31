from .base import *  # noqa
import dj_database_url
import os

# Security
DEBUG = True
SECRET_KEY = 'django-insecure-development-key-12345-change-this-in-production'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.onrender.com']

# Database configuration
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://rewardhub_ni1h_user:YId1iZ9BJvIbRdz5R6lsqpr2chp2Fm4o@dpg-d2q04jje5dus73bh8h3g-a.oregon-postgres.render.com/rewardhub_ni1h',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# SSL configuration for PostgreSQL
DATABASES['default']['OPTIONS'] = {
    'sslmode': 'require',
}

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Static files settings for development
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Media files settings (for development, in production you should use a cloud service)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"