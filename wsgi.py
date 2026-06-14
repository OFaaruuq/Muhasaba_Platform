"""WSGI entry for Gunicorn — loads .env then exposes Flask app."""
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from run import app  # noqa: F401
