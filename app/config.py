"""Configuration defaults for StudySprint Agent."""

import os


class Config:
    """Base configuration shared by development and production."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///studysprint.db")
    SEED_SAMPLE_DATA = os.environ.get("SEED_SAMPLE_DATA", "true").lower() == "true"
    APP_ENV = os.environ.get("APP_ENV", "development")
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    RATE_LIMIT_STORAGE_URI = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = APP_ENV == "production"
    TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
    PREFERRED_URL_SCHEME = "https" if APP_ENV == "production" else "http"
    SQLALCHEMY_POOL_PRE_PING = True
