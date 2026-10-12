"""Tests de la configuration de mise en ligne (Vercel + PostgreSQL Supabase).

Aucune connexion réelle : les adresses ci-dessous sont fictives.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

import app as application

URL_FICTIVE = "utilisateur:motdepasse@exemple.invalid:6543/base"


@pytest.mark.parametrize("url", [
    f"postgres://{URL_FICTIVE}",
    f"postgresql://{URL_FICTIVE}",
    f"postgresql+psycopg://{URL_FICTIVE}",
])
def test_url_postgres_convertie_pour_psycopg(url):
    assert application.normaliser_url_base(url) == f"postgresql+psycopg://{URL_FICTIVE}"


def test_url_sqlite_inchangee():
    assert application.normaliser_url_base("sqlite:///:memory:") == "sqlite:///:memory:"


def test_options_moteur_sqlite_local():
    assert application.options_moteur("sqlite:///:memory:") == {"pool_pre_ping": True}


def test_options_moteur_postgres_pour_le_transaction_pooler():
    options = application.options_moteur(f"postgresql+psycopg://{URL_FICTIVE}")
    assert options["poolclass"] is NullPool
    assert options["connect_args"] == {"prepare_threshold": None}


def test_moteur_postgres_utilise_psycopg_sans_pool():
    url = application.normaliser_url_base(f"postgres://{URL_FICTIVE}")
    moteur = create_engine(url, **application.options_moteur(url))  # ne se connecte pas
    assert moteur.dialect.name == "postgresql"
    assert moteur.dialect.driver == "psycopg"
    assert isinstance(moteur.pool, NullPool)
    moteur.dispose()


def test_base_obligatoire_sur_vercel(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(application, "EN_PRODUCTION", True)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        application.adresse_base()


def test_cle_secrete_depuis_l_environnement(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "cle-de-test")
    assert application.cle_secrete() == "cle-de-test"


def test_cle_secrete_de_secours_en_local(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(application, "EN_PRODUCTION", False)
    assert application.cle_secrete() == application.CLE_SECRETE_LOCALE


def test_cle_secrete_obligatoire_sur_vercel(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(application, "EN_PRODUCTION", True)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        application.cle_secrete()


@pytest.mark.parametrize("fichier", ["style.css", "app.js", "statistiques.js"])
def test_fichiers_statiques_servis_depuis_public(fichier):
    reponse = application.app.test_client().get(f"/static/{fichier}")
    assert reponse.status_code == 200
    reponse.close()


def test_page_pointe_vers_les_fichiers_statiques():
    page = application.app.test_client().get("/").get_data(as_text=True)
    assert 'href="/static/style.css?v=' in page
    assert 'src="/static/app.js?v=' in page
