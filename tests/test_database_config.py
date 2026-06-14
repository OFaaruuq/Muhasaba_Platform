"""Verify app uses database from .env configuration."""

from config import Config, _database_uri, _postgres_uri_from_env


def test_database_uri_from_env():
    uri = Config.SQLALCHEMY_DATABASE_URI
    assert "postgresql" in uri
    assert "muhasaba" in uri


def test_postgres_fallback_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "testuser")
    monkeypatch.setenv("POSTGRES_PASSWORD", "testpass")
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    assert "testuser" in _postgres_uri_from_env()
    assert "testdb" in _postgres_uri_from_env()


def test_postgres_url_normalization(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    assert _database_uri().startswith("postgresql://")


def test_engine_options_configured():
    assert Config.SQLALCHEMY_ENGINE_OPTIONS.get("pool_pre_ping") is True
