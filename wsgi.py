"""Production WSGI entry point for Gunicorn and hosting platforms."""

from app import create_app


app = create_app()
