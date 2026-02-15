"""
Django settings for math_server project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-^c3$zf4hl4d$#=vezx7z*o_!pc_w&@a7y(#!$*q%l@*gvvm&2j'

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'corsheaders',
    'questions',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

# CORS 配置 - 允许前端开发服务器访问
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'math_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'math_server.wsgi.application'

# 不使用 Django ORM 数据库（题目数据存 MongoDB）
DATABASES = {}

# MongoDB 配置（使用 mongoengine 直连）
MONGO_DB_NAME = "math_questions"
MONGO_HOST = "localhost"
MONGO_PORT = 27017

# 静态文件
STATIC_URL = 'static/'

# 媒体文件（上传的 docx 和提取的资源）
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# 文件上传限制：50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
