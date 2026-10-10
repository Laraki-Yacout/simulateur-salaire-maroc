"""Configuration commune des tests : base SQLite en mémoire, vidée avant chaque test."""

import os

# Doit être défini AVANT l'import de app, qui lit DATABASE_URL au démarrage
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest  # noqa: E402

from app import app  # noqa: E402
from models import db  # noqa: E402


@pytest.fixture(autouse=True)
def base_vide():
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield


@pytest.fixture
def client():
    return app.test_client()
