"""Tests de la configuration de mise en ligne (Render + PostgreSQL Supabase).

Aucune connexion réelle : les adresses ci-dessous sont fictives.
"""

import pytest
from sqlalchemy import create_engine

import app as application

URL_FICTIVE = "utilisateur:motdepasse@exemple.invalid:5432/base"


@pytest.mark.parametrize("url", [
    f"postgres://{URL_FICTIVE}",
    f"postgresql://{URL_FICTIVE}",
    f"postgresql+psycopg://{URL_FICTIVE}",
])
def test_url_postgres_convertie_pour_psycopg(url):
    assert application.normaliser_url_base(url) == f"postgresql+psycopg://{URL_FICTIVE}"


def test_url_sqlite_inchangee():
    assert application.normaliser_url_base("sqlite:///:memory:") == "sqlite:///:memory:"


def test_options_moteur():
    assert application.options_moteur("sqlite:///:memory:") == {"pool_pre_ping": True}
    options = application.options_moteur(f"postgresql+psycopg://{URL_FICTIVE}")
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"prepare_threshold": None}


def test_moteur_postgres_utilise_psycopg():
    url = application.normaliser_url_base(f"postgres://{URL_FICTIVE}")
    moteur = create_engine(url, **application.options_moteur(url))  # ne se connecte pas
    assert moteur.dialect.name == "postgresql"
    assert moteur.dialect.driver == "psycopg"
    moteur.dispose()


def test_cle_secrete_depuis_l_environnement(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "cle-de-test")
    assert application.cle_secrete() == "cle-de-test"


def test_cle_secrete_de_secours_en_local(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(application, "EN_PRODUCTION", False)
    assert application.cle_secrete() == application.CLE_SECRETE_LOCALE


def test_cle_secrete_obligatoire_sur_render(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(application, "EN_PRODUCTION", True)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        application.cle_secrete()
