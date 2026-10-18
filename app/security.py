"""Application security middleware and login rate limiting."""

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix


def init_security(app: Flask) -> Limiter:
    """Install trusted-proxy handling, headers, and request limiting."""
    proxy_hops = int(app.config.get("TRUSTED_PROXY_HOPS", 0))
    if proxy_hops:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_hops,
            x_proto=proxy_hops,
            x_host=proxy_hops,
            x_port=proxy_hops,
            x_prefix=proxy_hops,
        )

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        storage_uri=app.config["RATE_LIMIT_STORAGE_URI"],
        enabled=app.config["RATELIMIT_ENABLED"],
        default_limits=[],
    )

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; img-src 'self' data:; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        if app.config["APP_ENV"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    return limiter
